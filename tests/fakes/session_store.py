"""In-memory FakeSessionStore (T3)."""
from __future__ import annotations

from app.contracts.schemas import SessionState


class FakeSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], SessionState] = {}

    def load(self, session_id: str, passenger_id: str) -> SessionState:
        key = (session_id, passenger_id)
        if key not in self._sessions:
            self._sessions[key] = SessionState(session_id=session_id, passenger_id=passenger_id)
        return self._sessions[key]

    def save(self, session_id: str, passenger_id: str, state: SessionState) -> None:
        self._sessions[(session_id, passenger_id)] = state
