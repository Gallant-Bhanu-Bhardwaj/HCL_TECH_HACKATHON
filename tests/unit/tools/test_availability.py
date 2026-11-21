"""check_availability tests, against the real pinned seat rows."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from tests.unit.tools.conftest import make_ctx

from app.contracts.enums import BookingOutcome
from app.tools.availability import SeatsRowNotFound, check_availability

CTX = make_ctx(as_of=datetime(2026, 12, 3, 8, 0, tzinfo=timezone.utc))
JOURNEY_DATE = date(2026, 12, 5)


def test_2ac_has_seats_available(conn):
    result = check_availability(conn, CTX, "12123", JOURNEY_DATE, "2AC", "PUNE", "NGP")
    assert result.available == 9
    assert result.outcome == BookingOutcome.CNF


def test_3ac_is_fully_booked_and_rac_full_so_outcome_is_waitlist(conn):
    # Pinned edge case: capacity=3 (all CNF), rac=1 (== rac_capacity=1, full), waitlist=2.
    result = check_availability(conn, CTX, "12123", JOURNEY_DATE, "3AC", "PUNE", "NGP")
    assert result.available == 0
    assert result.rac == 1
    assert result.waitlist == 2
    assert result.outcome == BookingOutcome.WL  # no RAC room left either


def test_sl_has_one_waitlisted_traveller_but_seats_still_open(conn):
    result = check_availability(conn, CTX, "12123", JOURNEY_DATE, "SL", "PUNE", "NGP")
    assert result.available == 17
    assert result.waitlist == 1
    assert result.outcome == BookingOutcome.CNF  # seats still open despite the WL traveller


def test_unknown_train_date_class_combo_raises_not_found(conn):
    with pytest.raises(SeatsRowNotFound):
        check_availability(conn, CTX, "12123", date(2099, 1, 1), "2AC", "PUNE", "NGP")
