"""Schema smoke test (phase0-tasks.md T8).

Applies db/schema.sql to a fresh in-memory SQLite database and checks
that the mandatory tables/columns from the guide's §4.2 are present,
plus the key constraints this project added on top.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "db" / "schema.sql"

# Guide §4.2 — table name -> its mandatory "key columns"
MANDATORY_TABLES = {
    "stations": {"station_code", "name", "other_names", "city"},
    "trains": {"train_no", "name", "runs_on", "classes"},
    "train_stops": {"train_no", "station_code", "stop_order", "arrival", "departure", "day_offset"},
    "fares": {"train_no", "class", "from_code", "to_code", "fare"},
    "seats": {"train_no", "journey_date", "class", "available", "rac", "waitlist"},
    "passengers": {"passenger_id", "name", "phone_last4", "preferred_language"},
    "bookings": {
        "booking_id", "passenger_id", "train_no", "journey_date", "from_code",
        "to_code", "class", "amount_paid", "status", "booked_at",
    },
    "booking_travellers": {"booking_id", "traveller_name", "age", "status", "coach", "berth"},
    "actions": {
        "action_id", "passenger_id", "booking_id", "action_type", "status",
        "created_at", "expires_at", "result",
    },
    "settings": {"name", "value", "source_doc"},
}

# This project's approved additions (architecture.md D2/D4/D6/O4)
ADDITIVE_TABLES = {"settings_history", "documents", "chunks", "traces", "sessions", "handoffs"}


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_PATH.read_text())
    yield connection
    connection.close()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_schema_applies_without_error(conn):
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for table in MANDATORY_TABLES:
        assert table in tables, f"mandatory table {table!r} is missing"
    for table in ADDITIVE_TABLES:
        assert table in tables, f"additive table {table!r} is missing"


@pytest.mark.parametrize("table,expected_columns", MANDATORY_TABLES.items())
def test_mandatory_columns_present(conn, table, expected_columns):
    actual = _columns(conn, table)
    missing = expected_columns - actual
    assert not missing, f"{table} is missing mandatory columns: {missing}"


def test_additive_action_columns_present(conn):
    # D6: as_of (business clock) is required alongside expires_at (operational clock)
    assert {"as_of", "params_json", "preview_json", "trace_id"} <= _columns(conn, "actions")


def test_additive_settings_columns_present(conn):
    assert {"effective_from", "effective_to", "unit"} <= _columns(conn, "settings")


def test_seats_has_capacity_columns(conn):
    # O4: no automatic waitlist promotion requires knowing capacity
    assert {"capacity", "rac_capacity"} <= _columns(conn, "seats")


def test_foreign_keys_enabled(conn):
    (enabled,) = conn.execute("PRAGMA foreign_keys").fetchone()
    assert enabled == 1


def test_booking_status_check_rejects_invalid_value(conn):
    conn.execute(
        "INSERT INTO stations (station_code, name, city) VALUES ('PUNE','Pune','Pune')"
    )
    conn.execute(
        "INSERT INTO trains (train_no, name, runs_on, classes) VALUES ('12123','Ujjwal Express','MON','2AC')"
    )
    conn.execute(
        "INSERT INTO passengers (passenger_id, name) VALUES ('P007','Test Passenger')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO bookings (
                booking_id, passenger_id, train_no, journey_date, from_code,
                to_code, class, amount_paid, status, booked_at
            ) VALUES ('UR-1','P007','12123','2026-12-05','PUNE','PUNE','2AC',2040,'not_a_real_status','2026-11-20T11:02:00+05:30')
            """
        )


def test_settings_history_is_append_only(conn):
    conn.execute(
        """
        INSERT INTO settings_history (name, old_value, new_value, effective_from, source_doc, changed_at)
        VALUES ('cancel_charge_2AC_over_48h', 200, 250, '2026-12-04', 'CIR-2026-09', '2026-12-03T09:00:00+05:30')
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE settings_history SET new_value = 999 WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM settings_history WHERE id = 1")


def test_fts5_available(conn):
    # architecture §5.2: FTS5 keyword search, no extra dependency
    (count,) = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()
    assert count == 0  # empty table, but the virtual table exists and is queryable
