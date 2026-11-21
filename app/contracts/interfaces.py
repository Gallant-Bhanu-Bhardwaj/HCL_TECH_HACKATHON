"""Protocols shared between modules (docs/api-contracts.md §6–§8).

SHARED-FROZEN (architecture §8). These are interface specifications only
— Phase 0 ships no real implementation behind them, only contract-valid
fakes in tests/fakes/ (T3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from app.contracts.enums import Desk
from app.contracts.schemas import (
    Availability,
    BookingSpec,
    BookingSummary,
    BookingView,
    CancelEligibility,
    ChatResponse,
    ConfirmResult,
    FareQuote,
    HandoffRecord,
    IngestDoc,
    IngestResult,
    ParsedIntent,
    PendingAction,
    RefundQuote,
    Refusal,
    RetrievalResult,
    SessionState,
    StationMatch,
    TrainSearchResult,
)


class NotAccessible:
    """Returned in place of a booking when it is missing OR belongs to
    another passenger — the two cases are made indistinguishable here so
    that no code path can leak which one it was (R8, api-contracts §2.1).
    """

    __slots__ = ()


@dataclass(frozen=True)
class SettingValue:
    name: str
    value: int | float
    effective_from: datetime
    source_doc: str


@runtime_checkable
class TraceRecorder(Protocol):
    """Accumulates the pieces of docs/api-contracts.md §11 during a
    request; the audit module flushes it to storage at the end."""

    def record(self, section: str, payload: dict) -> None: ...


@dataclass
class PassengerContext:
    """Built by the server from X-Passenger-Id ONLY (D-principle: identity
    is injected, never inferred). Not a tool argument the LLM can fill in.
    """

    passenger_id: str
    preferred_language: str
    as_of: datetime  # business clock, resolved once per request (D6)
    trace: TraceRecorder


@runtime_checkable
class Clock(Protocol):
    """Operational clock for action expiry ONLY (D6, v1.2). Never used for
    refund/policy math — that uses PassengerContext.as_of instead. Real
    implementation wraps datetime.now(UTC); tests inject a fake."""

    def now_utc(self) -> datetime: ...


@runtime_checkable
class ToolRegistry(Protocol):
    """All deterministic. Raises typed errors or returns an explicit
    not-found/refusal value; never a partial guess (R4)."""

    def resolve_station(self, text: str) -> StationMatch: ...

    def search_trains(
        self,
        ctx: PassengerContext,
        from_code: str,
        to_code: str,
        date,
        after: time | None = None,
        before: time | None = None,
        cls: str | None = None,
    ) -> TrainSearchResult: ...

    def check_availability(
        self, ctx: PassengerContext, train_no: str, journey_date, cls: str,
        from_code: str, to_code: str,
    ) -> Availability: ...

    def get_fare(
        self, ctx: PassengerContext, train_no: str, cls: str,
        from_code: str, to_code: str, pax: int = 1,
    ) -> FareQuote: ...

    def list_my_bookings(
        self, ctx: PassengerContext, upcoming_only: bool = True
    ) -> list[BookingSummary]: ...

    def get_booking_status(
        self, ctx: PassengerContext, booking_id: str
    ) -> BookingView | NotAccessible: ...

    def refund_quote(self, ctx: PassengerContext, booking_id: str) -> RefundQuote: ...

    def can_cancel(self, ctx: PassengerContext, booking_id: str) -> CancelEligibility: ...

    def get_setting(self, name: str, as_of: datetime) -> SettingValue: ...


@runtime_checkable
class ActionService(Protocol):
    """propose_* computes the preview in code and never calls the LLM for
    arithmetic (D7). confirm() uses PassengerContext/action.as_of for the
    business recompute and a Clock for expiry — never mixed (D6)."""

    def propose_cancel(
        self, ctx: PassengerContext, booking_id: str
    ) -> PendingAction | Refusal: ...

    def propose_booking(
        self, ctx: PassengerContext, spec: BookingSpec
    ) -> PendingAction | Refusal: ...

    def propose_boarding_change(
        self, ctx: PassengerContext, booking_id: str, new_boarding_code: str
    ) -> PendingAction | Refusal: ...

    def confirm(self, ctx: PassengerContext, action_id: str) -> ConfirmResult: ...

    def cancel(self, ctx: PassengerContext, action_id: str) -> ConfirmResult: ...


@runtime_checkable
class HandoffService(Protocol):
    def create(
        self, ctx: PassengerContext, desk: Desk, summary: str,
        booking_id: str | None, session_id: str,
    ) -> HandoffRecord: ...


@runtime_checkable
class SessionStore(Protocol):
    def load(self, session_id: str, passenger_id: str) -> SessionState: ...

    def save(self, session_id: str, passenger_id: str, state: SessionState) -> None: ...


@runtime_checkable
class Retriever(Protocol):
    """RAG does not touch settings (D2) — ingest() only ever indexes
    documents; settings_changes are handled by Backend's own repository."""

    def retrieve(
        self, query: str, as_of: datetime, k: int = 5,
        language: str | None = None, doc_types: list[str] | None = None,
    ) -> RetrievalResult: ...

    def ingest(self, doc: IngestDoc) -> IngestResult: ...

    def stats(self) -> dict[str, int]: ...


@runtime_checkable
class LLMClient(Protocol):
    """Implementations: OllamaClient, an optional HostedClient, and
    MockClient (MOCK_LLM=true, §13). The LLM never writes settings or
    touches SQL directly (D7, D2)."""

    def complete_json(
        self, system: str, user: str, schema: type[BaseModel], *,
        temperature: float = 0,
    ) -> BaseModel: ...

    def complete_text(self, system: str, user: str, *, temperature: float = 0.2) -> str: ...


@runtime_checkable
class Orchestrator(Protocol):
    def handle_chat(
        self, ctx: PassengerContext, session_id: str, message: str
    ) -> ChatResponse: ...


__all__ = [
    "NotAccessible",
    "SettingValue",
    "TraceRecorder",
    "PassengerContext",
    "Clock",
    "ToolRegistry",
    "ActionService",
    "HandoffService",
    "SessionStore",
    "Retriever",
    "LLMClient",
    "Orchestrator",
    "ParsedIntent",  # re-exported for convenience (AI/LLM module import point)
]
