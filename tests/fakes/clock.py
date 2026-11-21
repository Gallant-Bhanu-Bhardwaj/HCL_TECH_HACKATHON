"""Fake operational Clock (D6) — injectable, deterministic unless advanced."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 12, 3, 8, 15, 0, tzinfo=timezone.utc)

    def now_utc(self) -> datetime:
        return self._now

    def advance(self, **kwargs) -> None:
        """Move the fake clock forward, e.g. advance(minutes=20)."""
        self._now = self._now + timedelta(**kwargs)
