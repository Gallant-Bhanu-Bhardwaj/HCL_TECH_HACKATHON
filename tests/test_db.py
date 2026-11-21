"""Checks the database builds and settings follow their effective dates. Run: python -m pytest -q"""
import subprocess
import sys

from app.db import connect, get_setting

subprocess.run([sys.executable, "init_db.py"], check=True, capture_output=True)  # fresh database


def test_seed_loaded():
    with connect() as con:
        assert con.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == 3


def test_old_charge_before_circular():
    assert get_setting("cancel_charge_2AC_over_48h", "2026-12-09") == (200, "RUL-CAN-01")


def test_new_charge_from_circular_date():
    assert get_setting("cancel_charge_2AC_over_48h", "2026-12-10T08:00:00+05:30") == (240, "CIR-2026-03")


def test_unknown_setting():
    assert get_setting("no_such_setting", "2026-12-01") == (None, None)
