"""Minimal TraceRecorder implementation (docs/api-contracts.md §11).

Accumulates per-request sections in memory; the route that owns a
request flushes it into the TraceStore at the end. Phase 0 only — no
guard/retrieval/intent detail is populated yet by any real module.
"""
from __future__ import annotations


class InMemoryTraceRecorder:
    def __init__(self) -> None:
        self._sections: dict[str, dict] = {}

    def record(self, section: str, payload: dict) -> None:
        self._sections[section] = payload

    def as_dict(self) -> dict:
        return dict(self._sections)
