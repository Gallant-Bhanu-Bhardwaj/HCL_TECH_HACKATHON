"""get_fare ("calculate_fare") tests — only ever returns a stored fare."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.unit.tools.conftest import make_ctx

from app.tools.fares import FareNotFound, get_fare

CTX = make_ctx(as_of=datetime(2026, 12, 3, 8, 0, tzinfo=timezone.utc))


def test_pinned_pune_nagpur_2ac_fare_matches_published_examples(conn):
    quote = get_fare(conn, CTX, "12123", "2AC", "PUNE", "NGP", pax=1)
    assert quote.fare_per_pax == 2040  # matches docs/api-contracts.md's worked examples exactly
    assert quote.total == 2040
    assert quote.source == "fares table"


def test_multiple_passengers_multiplies_the_stored_fare(conn):
    quote = get_fare(conn, CTX, "12123", "2AC", "PUNE", "NGP", pax=3)
    assert quote.total == 2040 * 3


def test_unknown_class_for_this_train_raises_not_found(conn):
    # 12123 does not offer 1AC — must not invent a fare for it.
    with pytest.raises(FareNotFound):
        get_fare(conn, CTX, "12123", "1AC", "PUNE", "NGP")


def test_unknown_route_raises_not_found(conn):
    with pytest.raises(FareNotFound):
        get_fare(conn, CTX, "12123", "2AC", "PUNE", "MAS")  # 12123 never stops at MAS
