"""refund_quote tests — the D4 inclusive-boundary cases, per-traveller
splitting, and the already-settled-booking short-circuits, all against
real seeded bookings.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.unit.tools.conftest import make_ctx

from app.tools.refund import BookingNotFound, classify_bracket, refund_quote

TZ = timezone(timedelta(hours=5, minutes=30))


@pytest.mark.parametrize(
    "hours,expected",
    [
        (48.0, "over_48h"),
        (47.999, "12h_to_48h"),
        (100.0, "over_48h"),
        (12.0, "12h_to_48h"),
        (11.999, "4h_to_12h"),
        (4.0, "4h_to_12h"),
        (3.999, "under_4h"),
        (0.0, "under_4h"),
    ],
)
def test_classify_bracket_inclusive_lower_bound(hours, expected):
    assert classify_bracket(hours) == expected


def test_exactly_48h_before_departure_uses_the_cheaper_bracket(conn):
    """Booking UR-30418 (2AC, 2040 paid) departs 2026-12-05 18:40.
    Exactly 48h before is 2026-12-03 18:40 -- D4: inclusive lower
    bound, so this is "48h or more", not "12h to 48h"."""
    ctx = make_ctx(as_of=datetime(2026, 12, 3, 18, 40, 0, tzinfo=TZ))
    quote = refund_quote(conn, ctx, "UR-30418")

    assert quote.hours_before_departure == pytest.approx(48.0, abs=1e-6)
    assert quote.charge == 200  # CIR-2026-07's revised 2AC/over_48h rate, in effect by 2026-12-03
    assert quote.refund == 1840
    assert quote.can_cancel is True
    assert any(r.doc_id == "CIR-2026-07" for r in quote.rule_basis)


def test_one_minute_after_48h_cutoff_uses_the_next_bracket(conn):
    """One minute later than the previous test -> crosses into
    "12h to 48h", a materially higher charge (D4)."""
    ctx = make_ctx(as_of=datetime(2026, 12, 3, 18, 41, 0, tzinfo=TZ))
    quote = refund_quote(conn, ctx, "UR-30418")

    assert quote.hours_before_departure < 48.0
    assert quote.charge == 240  # RUL-CAN-01's un-revised 2AC/12h_to_48h rate
    assert quote.refund == 1800
    assert quote.refund < 1840  # strictly less than the exact-cutoff case


def test_mixed_cnf_and_wl_booking_splits_refund_per_traveller(conn):
    """UR-30004: SL, 760 paid, 2 travellers (Vivaan CNF, Ishaan WL).
    Equal split -> 380 each. At exactly 48h: CNF charge 60 (SL/over_48h),
    WL charge always 0 (RUL-CAN-01 §4: waitlisted tickets are never
    charged to cancel)."""
    ctx = make_ctx(as_of=datetime(2026, 12, 3, 18, 40, 0, tzinfo=TZ))
    quote = refund_quote(conn, ctx, "UR-30004")

    by_name = {p.traveller_name: p for p in quote.per_traveller}
    assert by_name["Vivaan Mehta"].status == "CNF"
    assert by_name["Vivaan Mehta"].charge == 60
    assert by_name["Vivaan Mehta"].refund == 320

    assert by_name["Ishaan Mehta"].status == "WL"
    assert by_name["Ishaan Mehta"].charge == 0
    assert by_name["Ishaan Mehta"].refund == 380

    assert quote.charge == 60
    assert quote.refund == 700


def test_operator_cancelled_booking_is_full_refund_no_charge(conn):
    """UR-30011: status=train_cancelled_by_operator, 575 paid."""
    ctx = make_ctx(as_of=datetime(2026, 12, 3, 8, 0, tzinfo=timezone.utc))
    quote = refund_quote(conn, ctx, "UR-30011")

    assert quote.charge == 0
    assert quote.refund == 575
    assert quote.booking_status_effect == "train_cancelled_full_refund"
    assert quote.can_cancel is False  # already settled automatically; nothing to propose


def test_already_cancelled_booking_proposes_nothing_further(conn):
    """UR-30001 is already status='cancelled' in the seed data."""
    ctx = make_ctx(as_of=datetime(2026, 12, 3, 8, 0, tzinfo=timezone.utc))
    quote = refund_quote(conn, ctx, "UR-30001")

    assert quote.can_cancel is False
    assert quote.refund == 0
    assert quote.charge == 0
    assert quote.booking_status_effect == "not_cancellable"


def test_booking_already_departed_is_not_a_self_service_cancellation(conn):
    """UR-30418 departs 2026-12-05 18:40; asking "now" (long after) must
    not quote an ordinary cancellation — RUL-CAN-01 §2."""
    ctx = make_ctx(as_of=datetime(2026, 12, 10, 0, 0, 0, tzinfo=TZ))
    quote = refund_quote(conn, ctx, "UR-30418")

    assert quote.hours_before_departure < 0
    assert quote.can_cancel is False
    assert quote.reason is not None and "departed" in quote.reason


def test_unknown_booking_id_raises_not_found(conn):
    ctx = make_ctx(as_of=datetime(2026, 12, 3, 8, 0, tzinfo=timezone.utc))
    with pytest.raises(BookingNotFound):
        refund_quote(conn, ctx, "UR-00000-DOES-NOT-EXIST")


def test_next_cutoff_at_points_to_the_next_bracket_boundary(conn):
    ctx = make_ctx(as_of=datetime(2026, 12, 4, 18, 0, 0, tzinfo=TZ))  # ~24h40m before departure
    quote = refund_quote(conn, ctx, "UR-30418")

    assert classify_bracket(quote.hours_before_departure) == "12h_to_48h"
    # next_cutoff_at = departure_at - 12h (the floor of the current bracket)
    assert quote.next_cutoff_at == quote.departure_at - timedelta(hours=12)
