"""Checks the real tools against seed_small.sql. Run: python -m pytest -q"""
import subprocess
import sys

from app import tools

subprocess.run([sys.executable, "init_db.py"], check=True, capture_output=True)  # fresh database


def refund_at(time):
    return tools.refund_quote("UR-30418", "P007", f"2026-12-{time}+05:30")["refund"]


# --- stations ---
def test_aliases():
    assert tools.find_stations("Bombay") == ["CSMT"]
    assert tools.find_stations("poona") == ["PUNE"]

def test_similar_names():
    assert tools.find_stations("Kalyan") == ["KYN"]
    assert tools.find_stations("Kalyann") == ["KLYI", "KYN"]     # typo: ask which one
    assert "error" in tools.search_trains("Kalyann", "Nagpur", "2026-12-05")


# --- search, seats, fares ---
def test_search_includes_after_midnight_train():
    # 22111 leaves Mumbai Fri 4 Dec 22:00 and reaches Pune at 00:50 on Sat 5 Dec
    trains = tools.search_trains("Pune", "Nagpur", "2026-12-05")
    assert [t["train_no"] for t in trains] == ["22111", "12123"]
    assert trains[0]["journey_date"] == "2026-12-04"

def test_search_respects_running_days():
    trains = tools.search_trains("Pune", "Nagpur", "2026-12-04")   # 22111 did not leave on Thursday
    assert [t["train_no"] for t in trains] == ["12123"]

def test_seats_and_fare():
    assert tools.check_seats("12123", "2026-12-05", "3ac")["rac"] == 6
    assert tools.check_seats("12123", "2030-01-01", "2AC") == {}
    assert tools.get_fare("12123", "Pune", "Nagpur", "2AC")["fare"] == 2040


# --- bookings and privacy ---
def test_own_booking_only():
    assert tools.booking_status("UR-30418", "P007")["status"] == "CNF"
    assert tools.booking_status("UR-48213", "P007") == tools.NOT_YOURS   # someone else's
    assert tools.booking_status("UR-99999", "P007") == tools.NOT_YOURS   # does not exist
    assert tools.my_bookings("P020") == []

def test_mixed_travellers():
    statuses = [t["status"] for t in tools.booking_status("UR-30422", "P007")["travellers"]]
    assert statuses == ["CNF", "WL"]


# --- refunds at every cut-off (UR-30418: 2AC, Rs 2040, leaves Pune 5 Dec 18:10) ---
def test_refund_exactly_48_hours():
    assert refund_at("03T18:10:00") == 2040 - 200

def test_refund_one_minute_under_48_hours():
    assert refund_at("03T18:11:00") == 2040 - 510          # 25%

def test_refund_exactly_12_hours():
    assert refund_at("05T06:10:00") == 2040 - 510

def test_refund_one_minute_under_12_hours():
    assert refund_at("05T06:11:00") == 2040 - 1020         # 50%

def test_refund_exactly_4_hours():
    assert refund_at("05T14:10:00") == 2040 - 1020

def test_refund_one_minute_under_4_hours():
    assert refund_at("05T14:11:00") == 0

def test_refund_after_departure():
    assert "error" in tools.refund_quote("UR-30418", "P007", "2026-12-05T18:11:00+05:30")

def test_refund_not_yours():
    assert tools.refund_quote("UR-30418", "P012", "2026-12-03T10:00:00+05:30") == tools.NOT_YOURS

def test_departure_after_midnight():
    b = tools.own_booking("UR-30422", "P007")
    assert tools.departure_at(b).isoformat() == "2026-12-05T00:50:00+05:30"
