"""Tests for app/db/connection.py: initialization, idempotent seed
loading, and foreign-key enforcement.
"""
from __future__ import annotations

import sqlite3

import pytest

from app.db.connection import check_connectivity, get_connection, init_db


def test_init_db_creates_schema_and_loads_seed(tmp_path):
    db_path = str(tmp_path / "ujjwal.db")
    conn = init_db(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"stations", "trains", "bookings", "settings_history"} <= tables

        station_count = conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
        booking_count = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        assert station_count > 0
        assert booking_count > 0
    finally:
        conn.close()


def test_init_db_is_idempotent(tmp_path):
    """Calling init_db() twice against the same file must not duplicate
    rows or raise — it should detect the data is already there and skip
    re-applying db/seed_data.sql."""
    db_path = str(tmp_path / "ujjwal.db")

    conn1 = init_db(db_path)
    first_count = conn1.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    conn1.close()

    conn2 = init_db(db_path)  # second call, same file
    second_count = conn2.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    conn2.close()

    assert first_count == second_count
    assert first_count > 0


def test_init_db_called_three_times_still_stable(tmp_path):
    db_path = str(tmp_path / "ujjwal.db")
    counts = []
    for _ in range(3):
        conn = init_db(db_path)
        counts.append(conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0])
        conn.close()
    assert counts[0] == counts[1] == counts[2]
    assert counts[0] > 0


def test_get_connection_has_foreign_keys_enabled(tmp_path):
    db_path = str(tmp_path / "ujjwal.db")
    init_db(db_path).close()

    conn = get_connection(db_path)
    try:
        (enabled,) = conn.execute("PRAGMA foreign_keys").fetchone()
        assert enabled == 1
    finally:
        conn.close()


def test_foreign_key_violation_is_rejected(tmp_path):
    """A booking referencing a train_no that doesn't exist must be
    rejected, proving PRAGMA foreign_keys=ON is actually enforced (not
    just set and ignored)."""
    db_path = str(tmp_path / "ujjwal.db")
    init_db(db_path).close()

    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO passengers (passenger_id, name, preferred_language) "
            "VALUES ('P-TEST', 'Test Passenger', 'en')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO bookings (
                    booking_id, passenger_id, train_no, journey_date, from_code,
                    to_code, class, amount_paid, status, booked_at
                ) VALUES (
                    'UR-TEST-1', 'P-TEST', 'NO-SUCH-TRAIN', '2026-12-05', 'PUNE',
                    'NGP', '2AC', 100, 'confirmed', '2026-11-20T11:00:00+05:30'
                )
                """
            )
    finally:
        conn.close()


def test_check_connectivity_true_after_init(tmp_path):
    db_path = str(tmp_path / "ujjwal.db")
    init_db(db_path).close()
    assert check_connectivity(db_path) is True


def test_check_connectivity_false_for_unreachable_path():
    # A directory that cannot exist as a file path component.
    assert check_connectivity("/this/path/does/not/exist/ujjwal.db") is False


def test_seed_data_file_itself_is_untouched(tmp_path):
    """Sanity check that init_db() never writes back into db/seed_data.sql
    (it only reads it)."""
    from pathlib import Path

    seed_path = Path(__file__).resolve().parents[3] / "db" / "seed_data.sql"
    before = seed_path.read_text(encoding="utf-8")
    init_db(str(tmp_path / "ujjwal.db")).close()
    after = seed_path.read_text(encoding="utf-8")
    assert before == after
