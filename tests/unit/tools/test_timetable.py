"""search_trains tests, against the real seeded train 12123."""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from tests.unit.tools.conftest import make_ctx

from app.tools.timetable import search_trains

CTX = make_ctx(as_of=datetime(2026, 12, 3, 8, 0, tzinfo=timezone.utc))


def test_finds_pinned_train_pune_to_nagpur(conn):
    result = search_trains(conn, CTX, "PUNE", "NGP", date(2026, 12, 5))
    train_nos = [t.train_no for t in result.trains]
    assert "12123" in train_nos

    item = next(t for t in result.trains if t.train_no == "12123")
    assert item.name == "Ujjwal Express"
    assert item.depart_at.isoformat() == "2026-12-05T18:40:00+05:30"
    assert item.arrive_at.isoformat() == "2026-12-06T06:10:00+05:30"
    assert item.duration_min == 690
    assert set(item.classes) >= {"SL", "3AC", "2AC"}
    assert item.runs_on_date is True


def test_after_filter_excludes_earlier_departures(conn):
    result = search_trains(conn, CTX, "PUNE", "NGP", date(2026, 12, 5), after=time(19, 0))
    assert "12123" not in [t.train_no for t in result.trains]  # departs 18:40, before 19:00


def test_before_filter_includes_it(conn):
    result = search_trains(conn, CTX, "PUNE", "NGP", date(2026, 12, 5), before=time(20, 0))
    assert "12123" in [t.train_no for t in result.trains]


def test_class_filter_excludes_trains_without_that_class(conn):
    result = search_trains(conn, CTX, "PUNE", "NGP", date(2026, 12, 5), cls="1AC")
    assert "12123" not in [t.train_no for t in result.trains]  # 12123 only offers SL/3AC/2AC


def test_no_route_returns_empty_with_a_note_not_an_invented_train(conn):
    result = search_trains(conn, CTX, "PUNE", "PUNE", date(2026, 12, 5))
    assert result.trains == []
    assert result.note is not None


def test_wrong_direction_is_not_returned(conn):
    # 12123 runs PUNE -> NGP; searching NGP -> PUNE must not return it
    # (stop_order direction is respected, not just "both stations on this train").
    result = search_trains(conn, CTX, "NGP", "PUNE", date(2026, 12, 5))
    assert "12123" not in [t.train_no for t in result.trains]
