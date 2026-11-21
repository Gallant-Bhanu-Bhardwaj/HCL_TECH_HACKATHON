"""Checks preview -> confirm -> change -> check, and that nothing happens twice. Run: python -m pytest -q"""
import subprocess
import sys

import pytest

from app import actions, tools
from app.db import connect

EARLY = "2026-12-03T10:00:00+05:30"     # 56 hours before UR-30418 leaves Pune


@pytest.fixture(autouse=True)
def fresh_db():
    subprocess.run([sys.executable, "init_db.py"], check=True, capture_output=True)


def seats(train_no, day, cls):
    with connect() as con:
        return con.execute("SELECT available, waitlist FROM seats WHERE train_no = ? AND journey_date = ? "
                           "AND class = ?", (train_no, day, cls)).fetchone()


# --- cancel ---
def test_cancel_preview_changes_nothing():
    preview = actions.propose_cancel("UR-30418", "P007", EARLY)
    assert preview["refund"] == 1840 and "action_id" in preview
    assert tools.booking_status("UR-30418", "P007")["status"] == "CNF"

def test_cancel_confirm_once_only():
    action_id = actions.propose_cancel("UR-30418", "P007", EARLY)["action_id"]
    first = actions.confirm(action_id, "P007", EARLY)
    second = actions.confirm(action_id, "P007", EARLY)
    assert first["answer_type"] == "action_done" and first["checked"]
    assert second["answer"] == "This was already done."
    assert tools.booking_status("UR-30418", "P007")["status"] == "CANCELLED"
    assert seats("12123", "2026-12-05", "2AC")["available"] == 6      # one seat freed, only once

def test_confirm_by_someone_else_is_refused():
    action_id = actions.propose_cancel("UR-30418", "P007", EARLY)["action_id"]
    assert actions.confirm(action_id, "P012", EARLY)["answer_type"] == "refusal"
    assert tools.booking_status("UR-30418", "P007")["status"] == "CNF"

def test_confirm_after_expiry_is_refused():
    action_id = actions.propose_cancel("UR-30418", "P007", EARLY)["action_id"]
    assert actions.confirm(action_id, "P007", "2026-12-03T10:11:00+05:30")["answer_type"] == "refusal"

def test_refund_changed_since_preview():
    # preview at 48h05m (flat charge), confirm at 47h58m (25% charge): must not cancel
    action_id = actions.propose_cancel("UR-30418", "P007", "2026-12-03T18:05:00+05:30")["action_id"]
    result = actions.confirm(action_id, "P007", "2026-12-03T18:12:00+05:30")
    assert result["answer_type"] == "refusal"
    assert tools.booking_status("UR-30418", "P007")["status"] == "CNF"

def test_drop_a_proposal():
    action_id = actions.propose_cancel("UR-30418", "P007", EARLY)["action_id"]
    assert actions.cancel(action_id, "P007")["answer_type"] == "answer"
    assert actions.confirm(action_id, "P007", EARLY)["answer_type"] == "refusal"

def test_cannot_cancel_someone_elses_booking():
    assert actions.propose_cancel("UR-48213", "P007", EARLY) == tools.NOT_YOURS


# --- book ---
def test_book_two_seats():
    preview = actions.propose_booking("12123", "2026-12-05", "Pune", "Nagpur", "2AC",
                                      "Ravi:34, Sita:30", "P020", EARLY)
    assert preview["amount"] == 4080
    done = actions.confirm(preview["action_id"], "P020", EARLY)
    assert done["checked"] and done["result"]["status"] == "CNF"
    assert seats("12123", "2026-12-05", "2AC")["available"] == 3

def test_book_full_class_goes_to_waitlist():
    preview = actions.propose_booking("12123", "2026-12-05", "Pune", "Nagpur", "3AC", "Ravi:34", "P020", EARLY)
    done = actions.confirm(preview["action_id"], "P020", EARLY)
    assert done["result"]["status"] == "WL"

def test_book_train_not_running():
    assert "error" in actions.propose_booking("22111", "2026-12-04", "Pune", "Nagpur", "SL", "Ravi:34",
                                              "P020", EARLY)


# --- change boarding station ---
def test_change_boarding_to_kalyan():
    preview = actions.propose_change_boarding("UR-30418", "Kalyan", "P007", EARLY)
    done = actions.confirm(preview["action_id"], "P007", EARLY)
    assert done["checked"] and tools.booking_status("UR-30418", "P007")["from"] == "KYN"

def test_change_boarding_rules():
    assert "error" in actions.propose_change_boarding("UR-30418", "Kalyani", "P007", EARLY)   # not on route
    assert "error" in actions.propose_change_boarding("UR-30418", "Kalyan", "P007",
                                                      "2026-12-05T10:00:00+05:30")             # past cut-off
    assert actions.propose_change_boarding("UR-48213", "Kalyan", "P007", EARLY) == tools.NOT_YOURS


# --- hand-over ---
def test_handover_is_saved():
    ho = actions.create_handover("refunds", "Train cancelled, refund not received", "UR-30418", "P007", EARLY)
    with connect() as con:
        row = con.execute("SELECT desk, booking_id FROM handovers WHERE ref = ?", (ho["ref"],)).fetchone()
    assert (row["desk"], row["booking_id"]) == ("refunds", "UR-30418")

def test_handover_hides_someone_elses_booking():
    ho = actions.create_handover("complaints", "about my friend's ticket", "UR-48213", "P007", EARLY)
    assert ho["booking_id"] is None
