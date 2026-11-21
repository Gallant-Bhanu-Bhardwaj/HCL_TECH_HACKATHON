"""resolve_station tests — exact, alias, substring, ambiguous, none."""
from __future__ import annotations

import sqlite3

from app.tools.stations import resolve_station


def test_exact_station_code(conn):
    assert resolve_station(conn, "PUNE").kind == "exact"
    assert resolve_station(conn, "PUNE").station_code == "PUNE"


def test_lowercase_and_whitespace_are_normalised(conn):
    result = resolve_station(conn, "  pune  ")
    assert result.kind == "exact"
    assert result.station_code == "PUNE"


def test_exact_alias_match(conn):
    # Bombay / CST are real aliases of CSMT in the seed data
    assert resolve_station(conn, "Bombay").station_code == "CSMT"
    assert resolve_station(conn, "CST").station_code == "CSMT"


def test_unknown_text_is_none(conn):
    result = resolve_station(conn, "Nonexistent Place")
    assert result.kind == "none"
    assert result.station_code is None


def test_empty_text_is_none(conn):
    assert resolve_station(conn, "   ").kind == "none"


def test_ambiguous_substring_match_is_reported_with_all_candidates(tmp_path):
    """Isolated mini-db (not the full seed) so this test exercises the
    ambiguity logic itself, independent of which real stations happen
    to collide today."""
    db_path = str(tmp_path / "ambiguous.db")
    test_conn = sqlite3.connect(db_path)
    test_conn.row_factory = sqlite3.Row
    test_conn.execute(
        "CREATE TABLE stations (station_code TEXT PRIMARY KEY, name TEXT, other_names TEXT, city TEXT)"
    )
    test_conn.executemany(
        "INSERT INTO stations VALUES (?, ?, ?, ?)",
        [
            ("AAA", "North Springfield", "", "Springfield"),
            ("BBB", "South Springfield", "", "Springfield"),
        ],
    )
    test_conn.commit()

    result = resolve_station(test_conn, "Springfield")
    assert result.kind == "ambiguous"
    assert set(result.candidates) == {"AAA", "BBB"}
    test_conn.close()
