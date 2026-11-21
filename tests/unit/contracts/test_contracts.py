"""Contract round-trip tests (phase0-tasks.md T7).

Every JSON example quoted below is copied verbatim from
docs/api-contracts.md so a drift between the docs and the Pydantic
models fails here first.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts.enums import MAX_CLARIFICATIONS
from app.contracts.schemas import (
    BookingView,
    CancelResponse,
    ChatResponse,
    ConfirmResponse,
    IngestRequest,
    IngestResponse,
    SettingsChange,
    TraceRecord,
)

# ---------------------------------------------------------------------
# §4.1 ChatResponse — guide's own §6.1 example
# ---------------------------------------------------------------------

CHAT_RESPONSE_EXAMPLE = {
    "trace_id": "b17e40c2",
    "answer_type": "confirm_needed",
    "answer": (
        "Cancelling booking UR-30418 (12123, Pune to Nagpur, 5 Dec, "
        "2AC, 1 seat) now gives you a refund of Rs 1,840. Shall I go ahead?"
    ),
    "sources": [
        {"doc_id": "RUL-CAN-01", "section": "3. Refund table"},
        {"doc_id": "CIR-2026-07", "section": "Revised charges"},
    ],
    "tools": [
        {
            "tool": "refund_quote",
            "output": {"amount_paid": 2040, "charge": 200, "refund": 1840, "hours_before_departure": 51},
        }
    ],
    "pending_action": {
        "action_id": "ACT-0091",
        "type": "cancel_booking",
        "booking_id": "UR-30418",
        "expires_at": "2026-12-03T10:15:00+05:30",
    },
    "handed_to_human": None,
}


def test_chat_response_example_parses():
    model = ChatResponse.model_validate(CHAT_RESPONSE_EXAMPLE)
    assert model.answer_type == "confirm_needed"
    assert model.pending_action.action_id == "ACT-0091"


# ---------------------------------------------------------------------
# §4.2 ConfirmResponse example
# ---------------------------------------------------------------------

CONFIRM_RESPONSE_EXAMPLE = {
    "trace_id": "c93a1f07",
    "answer_type": "action_done",
    "answer": "Booking UR-30418 is cancelled. Refund of Rs 1,840 is recorded.",
    "action": {"action_id": "ACT-0091", "type": "cancel_booking", "status": "done", "booking_id": "UR-30418"},
    "verification": {"checked": True, "booking_status": "cancelled", "refund": 1840, "matches_preview": True},
    "idempotent_replay": False,
    "sources": [{"doc_id": "RUL-CAN-01", "section": "3. Refund table"}],
}


def test_confirm_response_example_parses():
    model = ConfirmResponse.model_validate(CONFIRM_RESPONSE_EXAMPLE)
    assert model.idempotent_replay is False
    assert model.verification.refund == 1840


# ---------------------------------------------------------------------
# §4.3 CancelResponse example
# ---------------------------------------------------------------------

CANCEL_RESPONSE_EXAMPLE = {
    "trace_id": "d41b7a90",
    "answer_type": "answer",
    "answer": "Okay, I have dropped that request. Nothing was changed.",
    "action": {"action_id": "ACT-0091", "status": "cancelled"},
}


def test_cancel_response_example_parses():
    model = CancelResponse.model_validate(CANCEL_RESPONSE_EXAMPLE)
    assert model.action.status == "cancelled"


# ---------------------------------------------------------------------
# §4.4 BookingView example
# ---------------------------------------------------------------------

BOOKING_VIEW_EXAMPLE = {
    "booking_id": "UR-30418",
    "passenger_id": "P007",
    "train_no": "12123",
    "train_name": "Ujjwal Express",
    "journey_date": "2026-12-05",
    "from_code": "PUNE",
    "to_code": "NGP",
    "class": "2AC",
    "boarding": {"station_code": "PUNE", "departure": "2026-12-05T18:40:00+05:30"},
    "amount_paid": 2040,
    "status": "confirmed",
    "booked_at": "2026-11-20T11:02:00+05:30",
    "travellers": [
        {"traveller_name": "A. Sharma", "age": 34, "status": "CNF", "coach": "B2", "berth": "21"}
    ],
    "pending_actions": [{"action_id": "ACT-0091", "type": "cancel_booking", "status": "proposed"}],
}


def test_booking_view_example_parses():
    model = BookingView.model_validate(BOOKING_VIEW_EXAMPLE)
    assert model.class_ == "2AC"
    assert model.travellers[0].traveller_name == "A. Sharma"


# ---------------------------------------------------------------------
# §5.2 IngestRequest / IngestResponse examples
# ---------------------------------------------------------------------

INGEST_REQUEST_WITH_SETTINGS = {
    "doc_id": "CIR-2026-09",
    "doc_type": "circular",
    "title": "Revised cancellation charges",
    "effective_from": "2026-12-04",
    "supersedes": ["RUL-CAN-01"],
    "language": "en",
    "sections": [
        {
            "section": "Revised charges",
            "text": "From 4 Dec 2026 the charge for 2AC cancelled 48h or more before departure is Rs 250.",
        }
    ],
    "settings_changes": [
        {"name": "cancel_charge_2AC_over_48h", "value": 250, "effective_from": "2026-12-04", "source_doc": "CIR-2026-09"}
    ],
}

INGEST_REQUEST_TEXT_ONLY = {
    "doc_id": "CIR-2026-10",
    "doc_type": "circular",
    "title": "Revised cancellation charges",
    "effective_from": "2026-12-04",
    "supersedes": ["RUL-CAN-01"],
    "language": "en",
    "sections": [
        {
            "section": "Revised charges",
            "text": "From 4 Dec 2026 the charge for 2AC cancelled 48h or more before departure is Rs 250.",
        }
    ],
}

INGEST_RESPONSE_EXAMPLE = {
    "doc_id": "CIR-2026-09",
    "action": "created",
    "sections_indexed": 1,
    "settings_applied": 1,
    "settings_history_ids": [41],
    "superseded_detected": ["RUL-CAN-01"],
    "indexed_at": "2026-12-03T09:00:00+05:30",
    "trace_id": "e5112233",
}


def test_ingest_request_with_settings_changes_parses():
    model = IngestRequest.model_validate(INGEST_REQUEST_WITH_SETTINGS)
    assert model.settings_changes[0].name == "cancel_charge_2AC_over_48h"


def test_ingest_request_text_only_has_no_settings_changes():
    """D2, v1.2: a text-only ingest carries NO settings_changes at all —
    not an empty list standing in for 'nothing changed', simply absent."""
    model = IngestRequest.model_validate(INGEST_REQUEST_TEXT_ONLY)
    assert model.settings_changes is None


def test_ingest_response_example_parses():
    model = IngestResponse.model_validate(INGEST_RESPONSE_EXAMPLE)
    assert model.settings_history_ids == [41]


# ---------------------------------------------------------------------
# §11 TraceRecord example
# ---------------------------------------------------------------------

TRACE_RECORD_EXAMPLE = {
    "trace_id": "b17e40c2",
    "created_at": "2026-12-03T08:15:02+05:30",
    "as_of": "2026-12-03T08:15:00+05:30",
    "endpoint": "/chat",
    "session_id": "sess-123",
    "passenger_id": "P007",
    "request": {"message": "Cancel my ticket for tomorrow"},
    "language": "en",
    "intent": {"intent": "cancel_booking", "confidence": 0.93, "slots": {}},
    "retrieval": {
        "query": "…",
        "passages": [{"doc_id": "RUL-CAN-01", "section": "3. Refund table", "score": 0.81}],
        "excluded": [{"doc_id": "CIR-2026-11", "why": "not_yet_effective"}],
        "conflicts": [],
    },
    "tools": [{"tool": "refund_quote", "input": {"booking_id": "UR-30418"}, "output": {}, "ms": 4}],
    "guards": {"answer_guard": "pass", "injection_flags": [], "followup_count": 0},
    "action": {"proposed": {"action_id": "ACT-0091", "type": "cancel_booking"}, "confirmed": None, "verification": None},
    "handoff": None,
    "llm": {"mode": "ollama", "model": "…", "prompt_versions": {"intent": "v1", "compose": "v1"}},
    "response": {"answer_type": "confirm_needed", "answer": "…", "sources": []},
    "latency_ms": 812,
}


def test_trace_record_example_parses():
    model = TraceRecord.model_validate(TRACE_RECORD_EXAMPLE)
    assert model.passenger_id == "P007"
    assert model.action["proposed"]["action_id"] == "ACT-0091"


# ---------------------------------------------------------------------
# Validation rules (T7 accept criteria)
# ---------------------------------------------------------------------


@pytest.mark.parametrize("missing_field", ["name", "value", "effective_from", "source_doc"])
def test_settings_change_missing_any_required_field_is_rejected(missing_field):
    payload = {
        "name": "cancel_charge_2AC_over_48h",
        "value": 250,
        "effective_from": "2026-12-04",
        "source_doc": "CIR-2026-09",
    }
    del payload[missing_field]
    with pytest.raises(ValidationError):
        SettingsChange.model_validate(payload)


def test_naive_datetime_is_rejected():
    bad = dict(CHAT_RESPONSE_EXAMPLE)
    bad["pending_action"] = dict(bad["pending_action"])
    bad["pending_action"]["expires_at"] = "2026-12-03T10:15:00"  # no UTC offset
    with pytest.raises(ValidationError):
        ChatResponse.model_validate(bad)


def test_money_float_is_rejected():
    """api-contracts §2: integer rupees only, strict — a float must not
    be silently coerced into an int money field."""
    bad = dict(BOOKING_VIEW_EXAMPLE)
    bad["amount_paid"] = 2040.0
    with pytest.raises(ValidationError):
        BookingView.model_validate(bad)


def test_clarification_cap_constant_exists():
    assert MAX_CLARIFICATIONS == 2
