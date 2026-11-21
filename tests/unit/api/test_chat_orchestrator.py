"""Integration tests for the real orchestrator wired into /chat
(app/llm/orchestrator.py) — end to end through the actual FastAPI app,
real SQLite tools and real RAG retrieval. No fakes involved in the
chat path itself (action_service/handoff_service remain the Phase 0
fakes — see the task report for why that's still correctly scoped).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(tmp_path) -> TestClient:
    return TestClient(create_app(db_path=str(tmp_path / "test.db")))


def chat(client, message, passenger_id="P007"):
    return client.post(
        "/chat", headers={"X-Passenger-Id": passenger_id},
        json={"session_id": "sess-1", "message": message},
    )


# 1. Policy question through /chat -----------------------------------------

def test_policy_question_cites_real_document_and_section(tmp_path):
    client = make_client(tmp_path)
    response = chat(client, "Can I bring my pet dog on the train?")
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "answer"
    assert "1AC" in body["answer"]  # the real RUL-LUG-01/FAQ-17 answer, not an invented one
    doc_ids = {s["doc_id"] for s in body["sources"]}
    assert "FAQ-17" in doc_ids


# 2. Train search through /chat ---------------------------------------------

def test_train_search_returns_the_real_pinned_train(tmp_path):
    client = make_client(tmp_path)
    response = chat(client, "Trains from Pune to Nagpur on 2026-12-05 after 6pm?")
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "answer"
    assert "12123" in body["answer"]
    tool_names = [t["tool"] for t in body["tools"]]
    assert "search_trains" in tool_names
    search_output = next(t["output"] for t in body["tools"] if t["tool"] == "search_trains")
    assert search_output["trains"] == ["12123"]


# 3. Fare query through /chat ------------------------------------------------

def test_fare_query_returns_the_real_stored_fare(tmp_path):
    client = make_client(tmp_path)
    response = chat(client, "What is the fare for 2AC from Pune to Nagpur on train 12123?")
    assert response.status_code == 200
    body = response.json()
    assert "2040" in body["answer"]  # matches the worked example already in docs/api-contracts.md
    fare_output = next(t["output"] for t in body["tools"] if t["tool"] == "get_fare")
    assert fare_output["fare_per_pax"] == 2040


# 4. Refund query through /chat ----------------------------------------------

def test_refund_query_computes_a_real_quote_with_citation(tmp_path):
    client = make_client(tmp_path)
    response = chat(client, "If I cancel my booking UR-30418, how much refund will I get?")
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "answer"  # informational quote, not a proposed cancellation
    refund_output = next(t["output"] for t in body["tools"] if t["tool"] == "refund_quote")
    assert refund_output["amount_paid"] == 2040
    assert refund_output["charge"] == 200
    assert refund_output["refund"] == 1840
    assert any(s["doc_id"] == "CIR-2026-07" for s in body["sources"])


def test_explicit_cancel_request_proposes_a_real_action(tmp_path):
    """Distinct from the informational refund query above: an imperative
    "cancel my booking" DOES propose an action (preview -> confirm)."""
    client = make_client(tmp_path)
    response = chat(client, "Cancel my booking UR-30418.")
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "confirm_needed"
    assert body["pending_action"]["booking_id"] == "UR-30418"
    assert "1840" in body["answer"]  # the real computed refund, not a hardcoded placeholder


# 5. Unknown query ------------------------------------------------------------

def test_unknown_off_topic_query_is_a_refusal(tmp_path):
    client = make_client(tmp_path)
    response = chat(client, "What is the weather like tomorrow?")
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "refusal"
    assert body["pending_action"] is None
    assert body["handed_to_human"] is None


def test_travel_related_but_unanswerable_query_is_not_found(tmp_path):
    client = make_client(tmp_path)
    response = chat(client, "What's the status of my railway journey complaint ticket reference?")
    assert response.status_code == 200
    # Either genuinely not_found, or routed to a human — never silently
    # fabricated. Both are acceptable outcomes; a fabricated "answer" is not.
    assert response.json()["answer_type"] in ("not_found", "handed_to_human", "refusal")


# 6. Passenger privacy --------------------------------------------------------

def test_asking_about_someone_elses_booking_is_refused(tmp_path):
    client = make_client(tmp_path)
    response = chat(
        client, "What's the status of booking UR-30418? It's my friend's.",
        passenger_id="P999",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "refusal"
    assert "UR-30418" not in body["answer"]  # never confirms the booking exists
    assert body["tools"] == []  # no tool call leaked any of P007's data


def test_owner_can_ask_about_their_own_booking(tmp_path):
    client = make_client(tmp_path)
    response = chat(client, "Cancel my booking UR-30418.", passenger_id="P007")
    assert response.status_code == 200
    assert response.json()["answer_type"] == "confirm_needed"


# 7. Citation presence --------------------------------------------------------

def test_every_policy_answer_carries_a_resolvable_citation(tmp_path):
    client = make_client(tmp_path)
    response = chat(client, "What is the Tatkal surcharge for 3AC?")
    body = response.json()
    assert body["answer_type"] == "answer"
    assert len(body["sources"]) > 0
    for source in body["sources"]:
        assert source["doc_id"]
        assert source["section"]


# 8. Multiple questions in one message ---------------------------------------

def test_multiple_questions_in_one_message_are_all_answered(tmp_path):
    client = make_client(tmp_path)
    response = chat(
        client,
        "Is there a 2AC seat on 12123 on 2026-12-05, and what is the fare for "
        "2AC from Pune to Nagpur on train 12123?",
    )
    assert response.status_code == 200
    body = response.json()
    tool_names = {t["tool"] for t in body["tools"]}
    assert "check_availability" in tool_names
    assert "get_fare" in tool_names
    assert "2040" in body["answer"]
    assert "available" in body["answer"].lower()
