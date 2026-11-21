"""In-memory trace store (docs/api-contracts.md §11).

Phase 0 only: a real implementation persists to SQLite (`traces` table,
db/schema.sql). Ownership rule (O8): GET /trace/{id} is readable only by
the passenger who made the original request.
"""
from __future__ import annotations

from app.contracts.schemas import TraceRecord


class InMemoryTraceStore:
    def __init__(self) -> None:
        self._traces: dict[str, TraceRecord] = {}

    def save(self, record: TraceRecord) -> None:
        self._traces[record.trace_id] = record

    def get_owned(self, trace_id: str, passenger_id: str) -> TraceRecord | None:
        record = self._traces.get(trace_id)
        if record is None or record.passenger_id != passenger_id:
            return None
        return record
