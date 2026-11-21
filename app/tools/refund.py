"""refund_quote — deterministic, SQLite-backed (api-contracts §6;
architecture D4/D6/D7: pure function of booking + settings-as-of-as_of
+ as_of; never the LLM; never executes a cancellation itself).

Boundary convention (D4): every bracket's lower bound is inclusive —
exactly 48.0 hours before departure falls in "48h or more", not
"12h to 48h". `classify_bracket` below is the one place this is
decided; RUL-CAN-01 §3/§6 and the settings table agree with it.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, time, timedelta, timezone

from app.contracts.enums import TravellerStatus
from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import PerTravellerRefund, RefundQuote, SourceRef

TZ = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata (api-contracts §2)
BRACKETS = ("over_48h", "12h_to_48h", "4h_to_12h", "under_4h")
_BRACKET_FLOOR_HOURS = {"over_48h": 48, "12h_to_48h": 12, "4h_to_12h": 4, "under_4h": 0}

# Which section of a settings row's source_doc actually defines that
# value. Hand-maintained because the real RAG/retrieval module isn't
# built yet (architecture.md: "Do not implement RAG" was out of scope
# for the data-generation phase, and still is here) — this is a small,
# explicit, documented stand-in, not a general citation-resolution
# mechanism. Every (doc_id, section) pair here is a real chunk —
# verified against data/documents/ at the time this was written.
_RAC_WL_SECTION = "4. Refund table (RAC and waitlisted travellers)"
_CNF_SECTION = "3. Refund table (confirmed travellers)"
_CIRCULAR_SECTION = "1. Revised charges"
_OPERATOR_CANCELLED_SECTION = "2. Train cancelled by the operator"


def _section_for(setting_name: str, source_doc: str) -> str:
    if source_doc.startswith("CIR-"):
        return _CIRCULAR_SECTION
    if setting_name.startswith("cancel_charge_rac_") or setting_name.startswith("cancel_charge_wl_"):
        return _RAC_WL_SECTION
    return _CNF_SECTION


class BookingNotFound(Exception):
    """No such booking (or a NotAccessible case the caller already
    filtered by ownership before calling this — this function itself
    does not check passenger_id, see note in refund_quote())."""


def classify_bracket(hours_before_departure: float) -> str:
    if hours_before_departure >= 48:
        return "over_48h"
    if hours_before_departure >= 12:
        return "12h_to_48h"
    if hours_before_departure >= 4:
        return "4h_to_12h"
    return "under_4h"


def _next_bracket_cutoff(departure_at: datetime, hours_before_departure: float) -> datetime | None:
    """The next instant (closer to departure) at which the charge gets
    worse — i.e. departure_at minus the current bracket's own floor.
    None once already in the last bracket (under_4h: no further step)."""
    bracket = classify_bracket(hours_before_departure)
    idx = BRACKETS.index(bracket)
    if idx == len(BRACKETS) - 1:
        return None
    floor_hours = _BRACKET_FLOOR_HOURS[bracket]
    return departure_at - timedelta(hours=floor_hours)


def _lookup_setting(conn: sqlite3.Connection, name: str, as_of_date: str) -> tuple[int | float, str]:
    """Latest row for `name` whose effective_from <= as_of_date (D6:
    business clock only). Raises KeyError if nothing is effective yet
    — the caller must treat that as not_found, never a guessed 0."""
    row = conn.execute(
        "SELECT value, source_doc FROM settings "
        "WHERE name = ? AND effective_from <= ? "
        "ORDER BY effective_from DESC LIMIT 1",
        (name, as_of_date),
    ).fetchone()
    if row is None:
        raise KeyError(f"no effective settings row for {name!r} as of {as_of_date}")
    return row["value"], row["source_doc"]


def _charge_setting_name(cls: str, status: str, bracket: str) -> str:
    if status == TravellerStatus.RAC.value:
        return f"cancel_charge_rac_{bracket}"
    if status == TravellerStatus.WL.value:
        return f"cancel_charge_wl_{bracket}"
    return f"cancel_charge_{cls}_{bracket}"


def refund_quote(conn: sqlite3.Connection, ctx: PassengerContext, booking_id: str) -> RefundQuote:
    """Pure function of (this booking's rows, settings as of
    ctx.as_of.date(), ctx.as_of) — D6: business clock only, never the
    operational Clock. Ownership (is this ctx.passenger_id's booking?)
    is the caller's job (api-contracts §6: NotAccessible, R8) — this
    function only raises BookingNotFound for a genuinely missing row,
    so it never becomes the thing that leaks "exists vs not mine".
    """
    booking = conn.execute(
        "SELECT booking_id, train_no, journey_date, from_code, to_code, class, "
        "amount_paid, status FROM bookings WHERE booking_id = ?",
        (booking_id,),
    ).fetchone()
    if booking is None:
        raise BookingNotFound(booking_id)

    stop = conn.execute(
        "SELECT departure, day_offset FROM train_stops WHERE train_no = ? AND station_code = ?",
        (booking["train_no"], booking["from_code"]),
    ).fetchone()
    if stop is None or stop["departure"] is None:
        # Data integrity problem, not a user error — never invent a time.
        raise BookingNotFound(f"{booking_id}: no boarding-stop departure time on file")

    journey_date = datetime.strptime(booking["journey_date"], "%Y-%m-%d").date()
    hh, mm = (int(x) for x in stop["departure"].split(":"))
    departure_at = datetime(
        journey_date.year, journey_date.month, journey_date.day, hh, mm, tzinfo=TZ
    ) + timedelta(days=stop["day_offset"])

    hours_before_departure = (departure_at - ctx.as_of).total_seconds() / 3600.0

    # --- Already-settled bookings: nothing further to propose (D5/R8-adjacent). ---
    if booking["status"] == "train_cancelled_by_operator":
        try:
            pct, source_doc = _lookup_setting(conn, "refund_pct_train_cancelled", ctx.as_of.date().isoformat())
        except KeyError:
            pct, source_doc = 100, "RUL-OPC-01"
        return RefundQuote(
            booking_id=booking_id,
            amount_paid=booking["amount_paid"],
            charge=0,
            refund=booking["amount_paid"] if pct >= 100 else int(booking["amount_paid"] * pct / 100),
            hours_before_departure=hours_before_departure,
            departure_at=departure_at,
            rule_basis=[SourceRef(doc_id=source_doc, section=_OPERATOR_CANCELLED_SECTION)],
            per_traveller=[],
            booking_status_effect="train_cancelled_full_refund",
            can_cancel=False,
            reason="Ujjwal Rail already cancelled this train; the full refund was processed automatically.",
        )

    if booking["status"] == "cancelled":
        return RefundQuote(
            booking_id=booking_id,
            amount_paid=booking["amount_paid"],
            charge=0,
            refund=0,
            hours_before_departure=hours_before_departure,
            departure_at=departure_at,
            rule_basis=[],
            per_traveller=[],
            booking_status_effect="not_cancellable",
            can_cancel=False,
            reason="This booking is already cancelled.",
        )

    # --- Already departed: not a self-service cancellation (RUL-CAN-01 §2). ---
    if hours_before_departure < 0:
        return RefundQuote(
            booking_id=booking_id,
            amount_paid=booking["amount_paid"],
            charge=booking["amount_paid"],
            refund=0,
            hours_before_departure=hours_before_departure,
            departure_at=departure_at,
            rule_basis=[SourceRef(doc_id="RUL-CAN-01", section="2. Who may cancel, and when")],
            per_traveller=[],
            booking_status_effect="not_cancellable",
            can_cancel=False,
            reason="This train has already departed; a missed/no-show claim is handled by a person, not self-service.",
        )

    # --- Ordinary self-cancellation: per-traveller charge/refund (RUL-CAN-01 §3/§4). ---
    travellers = conn.execute(
        "SELECT traveller_name, status FROM booking_travellers WHERE booking_id = ?",
        (booking_id,),
    ).fetchall()
    if not travellers:
        raise BookingNotFound(f"{booking_id}: no booking_travellers on file")

    bracket = classify_bracket(hours_before_departure)
    as_of_date = ctx.as_of.date().isoformat()
    per_traveller_amount = booking["amount_paid"] // len(travellers)  # equal-split (no per-traveller fare column)

    per_traveller: list[PerTravellerRefund] = []
    citations: dict[tuple[str, str], SourceRef] = {}
    total_charge = 0
    total_refund = 0

    for t in travellers:
        setting_name = _charge_setting_name(booking["class"], t["status"], bracket)
        try:
            charge_value, source_doc = _lookup_setting(conn, setting_name, as_of_date)
        except KeyError as exc:
            raise BookingNotFound(f"{booking_id}: {exc}") from exc
        charge = int(charge_value)
        refund = max(0, per_traveller_amount - charge)  # never a negative refund (RUL-REF-01 §3)

        per_traveller.append(
            PerTravellerRefund(traveller_name=t["traveller_name"], status=t["status"], refund=refund, charge=charge)
        )
        total_charge += charge
        total_refund += refund
        key = (source_doc, setting_name)
        if key not in citations:
            citations[key] = SourceRef(doc_id=source_doc, section=_section_for(setting_name, source_doc))

    return RefundQuote(
        booking_id=booking_id,
        amount_paid=booking["amount_paid"],
        charge=total_charge,
        refund=total_refund,
        hours_before_departure=hours_before_departure,
        departure_at=departure_at,
        rule_basis=list(citations.values()),
        per_traveller=per_traveller,
        booking_status_effect="normal",
        can_cancel=True,
        next_cutoff_at=_next_bracket_cutoff(departure_at, hours_before_departure),
    )
