"""Checks the API endpoints end to end in mock mode. Run: python -m pytest -q"""
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app

llm.MOCK = True
client = TestClient(app)
EARLY = "2026-12-03T10:00:00+05:30"
P007, P012 = {"X-Passenger-Id": "P007"}, {"X-Passenger-Id": "P012"}


@pytest.fixture(autouse=True)
def fresh_db():
    subprocess.run([sys.executable, "init_db.py"], check=True, capture_output=True)


def chat(message, headers=P007, as_of=EARLY):
    return client.post("/chat", headers=headers,
                       json={"session_id": message, "message": message, "as_of": as_of}).json()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_returns_trace():
    reply = chat("Refund for UR-30418?")
    assert reply["answer_type"] == "answer" and reply["trace_id"]
    trace = client.get(f"/trace/{reply['trace_id']}").json()
    assert trace["request"]["message"] == "Refund for UR-30418?"
    assert trace["response"]["tools"][0]["tool"] == "refund_quote"


def test_cancel_through_the_api():
    reply = chat("Cancel UR-30418")
    assert reply["answer_type"] == "confirm_needed"
    action_id = reply["pending_action"]["action_id"]
    url = f"/actions/{action_id}/confirm"
    first = client.post(url, headers=P007, json={"as_of": EARLY}).json()
    second = client.post(url, headers=P007, json={"as_of": EARLY}).json()
    assert first["answer_type"] == "action_done" and first["checked"]
    assert second["answer"] == "This was already done."
    assert client.get("/bookings/UR-30418", headers=P007).json()["status"] == "CANCELLED"


def test_confirm_by_someone_else():
    action_id = chat("Cancel UR-30418")["pending_action"]["action_id"]
    reply = client.post(f"/actions/{action_id}/confirm", headers=P012, json={"as_of": EARLY}).json()
    assert reply["answer_type"] == "refusal"


def test_drop_proposal():
    action_id = chat("Cancel UR-30418")["pending_action"]["action_id"]
    assert client.post(f"/actions/{action_id}/cancel", headers=P007).json()["answer_type"] == "answer"


def test_bookings_privacy():
    assert client.get("/bookings/UR-30418", headers=P007).status_code == 200
    assert client.get("/bookings/UR-48213", headers=P007).status_code == 404   # someone else's
    assert client.get("/bookings/UR-99999", headers=P007).status_code == 404   # does not exist


def test_header_is_required():
    assert client.post("/chat", json={"session_id": "s", "message": "hi"}).status_code == 422


def test_unknown_trace():
    assert client.get("/trace/nope").status_code == 404
