"""
Checks that agent.py and the backend fit together. Run from the repo root:
    python -m pytest -q
Uses mock mode, so no LLM is needed. Must pass after every backend change.
"""
import pytest
from app import agent, llm

llm.MOCK = True
AS_OF = "2026-12-03T10:00:00+05:30"

CASES = [
    ("P007", "Trains from Pune to Nagpur on 5 Dec", "answer"),
    ("P007", "Refund for UR-30418?", "answer"),
    ("P007", "Cancel UR-30418", "confirm_needed"),
    ("P007", "What's the status of UR-48213? It's my friend's.", "refusal"),
    ("P012", "Cancel UR-30418", "refusal"),
    ("P007", "Can I carry my pet dog?", "answer"),
    ("P007", "My train was cancelled and refund nahi mila, I want to complain", "handed_to_human"),
    ("P007", "Book me a hotel near New Delhi station", "refusal"),
    ("P007", "I need a ticket to Delhi", "clarification"),
]


@pytest.mark.parametrize("passenger_id, message, expected", CASES)
def test_agent_and_backend_fit(passenger_id, message, expected):
    result = agent.handle(passenger_id, message, message, AS_OF)  # new session per case
    assert result["answer_type"] == expected
