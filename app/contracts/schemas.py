"""Pydantic models for the HTTP, tool, RAG and LLM contracts.

Mirrors docs/api-contracts.md exactly. SHARED-FROZEN (architecture §8).
Phase 0 scope only: validation shapes, no business logic (T2).

Conventions enforced here (api-contracts §2):
  * datetimes are timezone-aware (naive -> ValidationError)
  * money fields are int (no floats)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.enums import (
    ActionStatus,
    ActionType,
    AnswerType,
    BookingOutcome,
    BookingStatus,
    Desk,
    DocType,
    Intent,
    Language,
    TravellerStatus,
)


# api-contracts §2: "Integer rupees (INR). No floats anywhere in money
# fields" — strict=True so a float (even a whole one, e.g. 2040.0) is
# rejected rather than silently coerced, per T7's accept criterion.
Money = Annotated[int, Field(strict=True)]


class ContractModel(BaseModel):
    """Base model: reject naive datetimes everywhere (api-contracts §2)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def _reject_naive_datetime(cls, value: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("naive datetime is not allowed; include a UTC offset")
        return value


# ---------------------------------------------------------------------------
# §2.1 Error model
# ---------------------------------------------------------------------------


class ErrorDetail(ContractModel):
    code: str
    message: str
    trace_id: str | None = None


class ErrorBody(ContractModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Shared sub-shapes used by several endpoints
# ---------------------------------------------------------------------------


class SourceRef(ContractModel):
    doc_id: str
    section: str


DocRef = SourceRef  # api-contracts §6: "DocRef (doc_id + section)"


class ToolCall(ContractModel):
    tool: str
    output: dict[str, Any]
    input: dict[str, Any] | None = None  # additive: present in trace, not in §4.1 example
    ms: float | None = None  # additive: present in trace, not in §4.1 example


class PendingActionRef(ContractModel):
    action_id: str
    type: ActionType
    booking_id: str | None = None
    expires_at: datetime


class HandoffRef(ContractModel):
    handoff_id: str
    desk: Desk
    summary: str
    booking_id: str | None = None


class Conflict(ContractModel):
    winner: SourceRef
    superseded: SourceRef
    reason: str


# ---------------------------------------------------------------------------
# §4.1 POST /chat
# ---------------------------------------------------------------------------


class ChatRequest(ContractModel):
    session_id: str
    message: str
    as_of: datetime | None = None


class ChatResponse(ContractModel):
    trace_id: str
    answer_type: AnswerType
    answer: str
    sources: list[SourceRef] = Field(default_factory=list)
    tools: list[ToolCall] = Field(default_factory=list)
    pending_action: PendingActionRef | None = None
    handed_to_human: HandoffRef | None = None
    conflicts: list[Conflict] | None = None  # additive
    language: Language | None = None  # additive


# ---------------------------------------------------------------------------
# §4.2 POST /actions/{id}/confirm
# ---------------------------------------------------------------------------


class ActionRef(ContractModel):
    action_id: str
    type: ActionType
    status: ActionStatus
    booking_id: str | None = None


class Verification(ContractModel):
    checked: bool
    booking_status: str | None = None
    refund: Money | None = None
    matches_preview: bool | None = None


class ConfirmResponse(ContractModel):
    trace_id: str
    answer_type: AnswerType
    answer: str
    action: ActionRef
    verification: Verification
    idempotent_replay: bool
    sources: list[SourceRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# §4.3 POST /actions/{id}/cancel
# ---------------------------------------------------------------------------


class ActionMini(ContractModel):
    action_id: str
    status: ActionStatus


class CancelResponse(ContractModel):
    trace_id: str
    answer_type: AnswerType
    answer: str
    action: ActionMini


# ---------------------------------------------------------------------------
# §4.4 GET /bookings/{id}
# ---------------------------------------------------------------------------


class BoardingInfo(ContractModel):
    station_code: str
    departure: datetime


class TravellerView(ContractModel):
    traveller_name: str
    age: int
    status: TravellerStatus
    coach: str | None = None
    berth: str | None = None


class PendingActionMini(ContractModel):
    action_id: str
    type: ActionType
    status: ActionStatus


class BookingView(ContractModel):
    booking_id: str
    passenger_id: str
    train_no: str
    train_name: str
    journey_date: date
    from_code: str
    to_code: str
    class_: str = Field(alias="class")
    boarding: BoardingInfo
    amount_paid: Money
    status: BookingStatus
    booked_at: datetime
    travellers: list[TravellerView]
    pending_actions: list[PendingActionMini] = Field(default_factory=list)  # additive


# ---------------------------------------------------------------------------
# §5.2 POST /ingest — document fields and settings_changes are INDEPENDENT (D2)
# ---------------------------------------------------------------------------


class DocSection(ContractModel):
    section: str
    text: str


class SettingsChange(ContractModel):
    """A single policy value update. All four fields are required (D2) —
    there is no partially-specified settings change.
    """

    name: str
    value: int | float
    effective_from: date
    source_doc: str


class IngestRequest(ContractModel):
    # Document fields (optional as a group — a settings-only call may omit them)
    doc_id: str | None = None
    doc_type: DocType | None = None
    title: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    supersedes: list[str] = Field(default_factory=list)
    language: Language | None = None
    sections: list[DocSection] | None = None
    markdown: str | None = None  # raw §5.1 file, alternative to the structured fields

    # Settings fields (optional, independent of the document fields — D2)
    settings_changes: list[SettingsChange] | None = None


class IngestResponse(ContractModel):
    doc_id: str | None = None
    action: Literal["created", "updated"] | None = None
    sections_indexed: int = 0
    settings_applied: int = 0
    settings_history_ids: list[int] = Field(default_factory=list)
    superseded_detected: list[str] = Field(default_factory=list)
    indexed_at: datetime
    trace_id: str


# ---------------------------------------------------------------------------
# §4.6 GET /health
# ---------------------------------------------------------------------------


class HealthResponse(ContractModel):
    status: Literal["ok", "degraded"]
    db: str
    index_docs: int
    llm: Literal["mock", "ollama", "hosted"]
    mock_llm: bool


# ---------------------------------------------------------------------------
# §11 Trace record (nested sections kept loose — audit module's detail)
# ---------------------------------------------------------------------------


class TraceRecord(ContractModel):
    trace_id: str
    created_at: datetime
    as_of: datetime
    endpoint: str
    session_id: str | None = None
    passenger_id: str
    request: dict[str, Any]
    language: Language | None = None
    intent: dict[str, Any] | None = None
    retrieval: dict[str, Any] | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    guards: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    handoff: dict[str, Any] | None = None
    llm: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    latency_ms: float | None = None


# ---------------------------------------------------------------------------
# §6 Domain models — tool layer
# ---------------------------------------------------------------------------


class StationMatch(ContractModel):
    kind: Literal["exact", "ambiguous", "none"]
    station_code: str | None = None
    candidates: list[str] = Field(default_factory=list)


class TrainSearchItem(ContractModel):
    train_no: str
    name: str
    from_code: str
    to_code: str
    depart_at: datetime
    arrive_at: datetime
    duration_min: int
    classes: list[str]
    runs_on_date: bool


class TrainSearchResult(ContractModel):
    trains: list[TrainSearchItem] = Field(default_factory=list)
    note: str | None = None


class Availability(ContractModel):
    train_no: str
    journey_date: date
    cls: str
    available: int
    rac: int
    waitlist: int
    outcome: BookingOutcome


class FareQuote(ContractModel):
    train_no: str
    cls: str
    from_code: str
    to_code: str
    fare_per_pax: Money
    pax: int
    total: Money
    source: str = "fares table"


class PerTravellerRefund(ContractModel):
    traveller_name: str
    status: TravellerStatus
    refund: Money
    charge: Money


class RefundQuote(ContractModel):
    """Pure function of (booking, settings as of as_of, as_of) — business
    clock only (D6, D4 inclusive-boundary convention).
    """

    booking_id: str
    amount_paid: Money
    charge: Money
    refund: Money
    hours_before_departure: float | None = None
    departure_at: datetime
    rule_basis: list[SourceRef] = Field(default_factory=list)
    per_traveller: list[PerTravellerRefund] = Field(default_factory=list)
    booking_status_effect: Literal[
        "normal", "train_cancelled_full_refund", "not_cancellable"
    ]
    can_cancel: bool
    reason: str | None = None
    next_cutoff_at: datetime | None = None


class CancelEligibility(ContractModel):
    can_cancel: bool
    reason: str | None = None
    next_cutoff_at: datetime | None = None
    hours_before_departure: float | None = None


class TravellerSpec(ContractModel):
    traveller_name: str
    age: int


class BookingSpec(ContractModel):
    train_no: str
    journey_date: date
    cls: str
    from_code: str
    to_code: str
    travellers: list[TravellerSpec]


class PendingAction(ContractModel):
    action_id: str
    type: ActionType
    booking_id: str | None = None
    expires_at: datetime  # real UTC timestamp, operational clock (D6)
    preview: dict[str, Any]  # amounts computed from settings as of as_of (business clock)
    as_of: datetime  # business clock, saved at proposal (D6) — required


class ConfirmResult(ContractModel):
    """Domain return value of ActionService.confirm()/cancel() — carries
    the full ActionRef (type, booking_id included) so the API layer can
    build ConfirmResponse/CancelResponse without reaching into the
    service's internals."""

    action: ActionRef
    verification: Verification
    idempotent_replay: bool


class Refusal(ContractModel):
    """Returned by propose_* tools instead of a PendingAction when the
    change is not allowed (Level 2/3)."""

    reason: str
    level: Literal[2, 3]


class HandoffRecord(ContractModel):
    handoff_id: str
    desk: Desk
    summary: str
    booking_id: str | None = None
    session_id: str
    created_at: datetime


class SessionState(ContractModel):
    session_id: str
    passenger_id: str
    slots: dict[str, Any] = Field(default_factory=dict)
    last_intent: Intent | None = None
    followup_count: int = 0  # D3: capped at MAX_CLARIFICATIONS (2)


# ---------------------------------------------------------------------------
# §7 RAG models
# ---------------------------------------------------------------------------


class Passage(ContractModel):
    chunk_id: str
    doc_id: str
    doc_type: DocType
    section: str
    text: str
    score: float
    effective_from: date | None = None
    effective_to: date | None = None
    language: Language
    flags: list[str] = Field(default_factory=list)  # e.g. ["suspicious"] (R9)


class ExcludedDoc(ContractModel):
    doc_id: str
    section: str | None = None
    why: Literal["not_yet_effective", "superseded", "withdrawn"]


class RetrievalResult(ContractModel):
    passages: list[Passage] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    excluded: list[ExcludedDoc] = Field(default_factory=list)


class IngestDoc(ContractModel):
    """Document half of an IngestRequest, as handed to the Retriever —
    never carries settings_changes (D2: RAG does not touch settings)."""

    doc_id: str
    doc_type: DocType
    title: str
    effective_from: date
    effective_to: date | None = None
    supersedes: list[str] = Field(default_factory=list)
    language: Language
    sections: list[DocSection]


class IngestResult(ContractModel):
    doc_id: str
    action: Literal["created", "updated"]
    sections_indexed: int
    superseded_detected: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# §8 LLM / orchestrator models
# ---------------------------------------------------------------------------


class ParsedIntentSlots(ContractModel):
    from_text: str | None = None
    to_text: str | None = None
    date_text: str | None = None
    time_of_day: str | None = None
    class_: str | None = Field(default=None, alias="class")
    pax: int | None = None
    train_no: str | None = None
    booking_id: str | None = None
    new_boarding_text: str | None = None
    topic_query: str | None = None


class ParsedIntent(ContractModel):
    intent: Intent
    language: Language
    confidence: float
    slots: ParsedIntentSlots
    missing: list[str] = Field(default_factory=list)


class BookingSummary(ContractModel):
    """Lightweight row for ToolRegistry.list_my_bookings (api-contracts §6).

    Additive: not individually named in api-contracts' model list, but
    required by the ToolRegistry.list_my_bookings signature it defines.
    """

    booking_id: str
    train_no: str
    journey_date: date
    from_code: str
    to_code: str
    status: BookingStatus
