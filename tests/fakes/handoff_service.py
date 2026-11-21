"""Canned FakeHandoffService (T3)."""
from __future__ import annotations

from app.contracts.enums import Desk
from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import HandoffRecord


class FakeHandoffService:
    def __init__(self, clock) -> None:
        self._clock = clock
        self._seq = 0

    def create(
        self, ctx: PassengerContext, desk: Desk, summary: str,
        booking_id: str | None, session_id: str,
    ) -> HandoffRecord:
        self._seq += 1
        return HandoffRecord(
            handoff_id=f"HND-{self._seq:04d}", desk=desk, summary=summary,
            booking_id=booking_id, session_id=session_id,
            created_at=self._clock.now_utc(),
        )
