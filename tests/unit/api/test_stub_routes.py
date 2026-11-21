"""Stub-route behaviour tests (phase0-tasks.md T4 accept criteria).

Note: the chat message used to produce a `confirm_needed` pending
action was changed from the Phase 0 placeholder "Cancel my ticket for
tomorrow" (which only ever worked because FakeOrchestrator hardcoded
UR-30418 for literally any message) to the explicit "Cancel my booking
UR-30418." now that /chat is wired to the real orchestrator
(app/llm/orchestrator.py), which resolves an actual booking ID from
the message rather than guessing one. Every assertion below is
unchanged.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(tmp_path) -> TestClient:
    """Each test gets its own isolated SQLite file (app/db/connection.py
    init_db()) instead of writing to the project's configured default
    DB_PATH on every test run."""
    return TestClient(create_app(db_path=str(tmp_path / "test.db")))


def test_health_is_200(tmp_path):
    client = make_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["mock_llm"] is True


def test_chat_returns_guide_example_shape(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/chat",
        headers={"X-Passenger-Id": "P007"},
        json={"session_id": "sess-1", "message": "Cancel my booking UR-30418."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "confirm_needed"
    assert body["pending_action"]["action_id"]
    assert body["handed_to_human"] is None


def test_chat_without_passenger_header_is_401(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/chat", json={"session_id": "sess-1", "message": "hi"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_confirm_twice_is_idempotent(tmp_path):
    client = make_client(tmp_path)
    headers = {"X-Passenger-Id": "P007"}

    chat = client.post(
        "/chat", headers=headers,
        json={"session_id": "sess-1", "message": "Cancel my booking UR-30418."},
    ).json()
    action_id = chat["pending_action"]["action_id"]

    first = client.post(f"/actions/{action_id}/confirm", headers=headers)
    assert first.status_code == 200
    assert first.json()["idempotent_replay"] is False

    second = client.post(f"/actions/{action_id}/confirm", headers=headers)
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert second.json()["action"] == first.json()["action"]


def test_confirm_unknown_action_is_404(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/actions/ACT-9999/confirm", headers={"X-Passenger-Id": "P007"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_confirm_by_different_passenger_is_same_404_as_unknown(tmp_path):
    client = make_client(tmp_path)
    chat = client.post(
        "/chat", headers={"X-Passenger-Id": "P007"},
        json={"session_id": "sess-1", "message": "Cancel my booking UR-30418."},
    ).json()
    action_id = chat["pending_action"]["action_id"]

    foreign = client.post(f"/actions/{action_id}/confirm", headers={"X-Passenger-Id": "P999"})
    unknown = client.post("/actions/ACT-0000/confirm", headers={"X-Passenger-Id": "P999"})

    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json() == unknown.json()


def test_foreign_booking_is_404_same_body_as_missing(tmp_path):
    client = make_client(tmp_path)
    headers_owner = {"X-Passenger-Id": "P007"}
    headers_other = {"X-Passenger-Id": "P999"}

    missing = client.get("/bookings/UR-00000", headers=headers_other)
    foreign = client.get("/bookings/UR-30418", headers=headers_other)  # exists, but belongs to P007
    owned = client.get("/bookings/UR-30418", headers=headers_owner)

    assert missing.status_code == foreign.status_code == 404
    assert missing.json() == foreign.json()  # byte-identical body, not just the same code (R8)
    assert owned.status_code == 200


def test_ingest_text_only_does_not_change_settings(tmp_path):
    """D2, v1.2: a text-only circular never changes a setting."""
    client = make_client(tmp_path)
    response = client.post(
        "/ingest",
        json={
            "doc_id": "CIR-2026-10",
            "doc_type": "circular",
            "title": "Revised cancellation charges",
            "effective_from": "2026-12-04",
            "language": "en",
            "sections": [
                {"section": "Revised charges", "text": "The charge for 2AC is now Rs 250."}
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["settings_applied"] == 0
    assert body["settings_history_ids"] == []


def test_ingest_rejects_unregistered_settings_key(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/ingest",
        json={
            "doc_id": "CIR-2026-11",
            "settings_changes": [
                {"name": "not_a_real_setting", "value": 1, "effective_from": "2026-12-04", "source_doc": "CIR-2026-11"}
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_ingest_with_valid_settings_change_applies_it(tmp_path):
    client = make_client(tmp_path)
    response = client.post(
        "/ingest",
        json={
            "doc_id": "CIR-2026-09",
            "settings_changes": [
                {
                    "name": "cancel_charge_2AC_over_48h",
                    "value": 250,
                    "effective_from": "2026-12-04",
                    "source_doc": "CIR-2026-09",
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["settings_applied"] == 1


def test_trace_is_readable_by_owner_only(tmp_path):
    client = make_client(tmp_path)
    chat = client.post(
        "/chat", headers={"X-Passenger-Id": "P007"},
        json={"session_id": "sess-1", "message": "Cancel my booking UR-30418."},
    ).json()
    trace_id = chat["trace_id"]

    owner = client.get(f"/trace/{trace_id}", headers={"X-Passenger-Id": "P007"})
    other = client.get(f"/trace/{trace_id}", headers={"X-Passenger-Id": "P999"})

    assert owner.status_code == 200
    assert other.status_code == 404
