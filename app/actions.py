"""
actions.py - the ONLY module that changes bookings.

How a change works (brief R5):
  1. propose_* checks everything, saves an 'actions' row (status 'proposed') and returns a preview.
     Nothing in bookings or seats changes yet.
  2. The passenger presses Confirm -> POST /actions/{id}/confirm -> confirm() below.
     The LLM can never call confirm().
  3. confirm() claims the action ONCE, re-checks it, makes the change in one transaction,
     then reads the booking back to check it worked.
"""
import json
import random
import uuid
from datetime import timedelta

from app import tools
from app.db import connect, get_setting

DESKS = ["complaints", "refunds", "safety"]


class PreviewChanged(Exception):
    """The refund or seats changed between the preview and the confirm."""


def now_ist(as_of):
    return tools.now_from(as_of).astimezone(tools.IST)   # one time zone, so time strings compare


def new_action(passenger_id, booking_id, action_type, params, now):
    """Save a proposed action and return the preview the passenger sees."""
    ttl, _ = get_setting("action_ttl_minutes", now)
    action_id = "ACT-" + uuid.uuid4().hex[:6].upper()
    expires = (now + timedelta(minutes=ttl)).isoformat()
    with connect() as con:
        con.execute("INSERT INTO actions (action_id, passenger_id, booking_id, action_type, status, "
                    "created_at, expires_at, params) VALUES (?, ?, ?, ?, 'proposed', ?, ?, ?)",
                    (action_id, passenger_id, booking_id, action_type, now.isoformat(), expires,
                     json.dumps(params)))
    return {"action_id": action_id, "type": action_type, "booking_id": booking_id,
            **params, "expires_at": expires}


# ---------- 1. proposals (called by agent.py through the LLM) ----------

def propose_cancel(booking_id, passenger_id, as_of=None):
    quote = tools.refund_quote(booking_id, passenger_id, as_of)
    if "error" in quote:
        return quote
    params = {"refund": quote["refund"], "charge": quote["charge"], "rule": quote["rule"]}
    return new_action(passenger_id, quote["booking_id"], "cancel_booking", params, now_ist(as_of))


def propose_booking(train_no, date, from_station, to_station, travel_class, travellers,
                    passenger_id, as_of=None):
    """travellers looks like 'Ravi:34, Sita:30'. date is the passenger's travel date."""
    trains = tools.search_trains(from_station, to_station, date)
    if isinstance(trains, dict):
        return trains                                    # station error
    train = next((t for t in trains if t["train_no"] == train_no), None)
    if train is None:
        return {"error": f"train {train_no} does not run between these stations on {date}"}
    fare = tools.get_fare(train_no, train["from"], train["to"], travel_class)
    if not fare:
        return {"error": f"no {travel_class} fare for this train"}
    people = []
    for part in travellers.split(","):
        name, _, age = part.partition(":")
        people.append({"name": name.strip(), "age": int(age) if age.strip().isdigit() else None})
    params = {"train_no": train_no, "journey_date": train["journey_date"], "from": train["from"],
              "to": train["to"], "class": fare["class"], "travellers": people,
              "amount": fare["fare"] * len(people)}
    return new_action(passenger_id, None, "book", params, now_ist(as_of))


def propose_change_boarding(booking_id, new_station, passenger_id, as_of=None):
    b = tools.own_booking(booking_id, passenger_id)
    if b is None:
        return tools.NOT_YOURS
    if b["status"] in ("CANCELLED", "TRAIN_CANCELLED"):
        return {"error": "this booking is cancelled"}
    code, err = tools.one_station(new_station)
    if err:
        return err
    error = boarding_change_error(b, code, now_ist(as_of))
    if error:
        return {"error": error}
    params = {"old_station": b["from_code"], "new_station": code}
    return new_action(passenger_id, b["booking_id"], "change_boarding", params, now_ist(as_of))


def boarding_change_error(b, new_code, now):
    """None if allowed. The new station must be on the route before the destination."""
    with connect() as con:
        order = {r["station_code"]: r["stop_order"] for r in
                 con.execute("SELECT station_code, stop_order FROM train_stops WHERE train_no = ?",
                             (b["train_no"],))}
    if new_code == b["from_code"]:
        return "that is already the boarding station"
    if new_code not in order or order[new_code] >= order[b["to_code"]]:
        return f"{new_code} is not a stop before {b['to_code']} on train {b['train_no']}"
    cutoff, _ = get_setting("boarding_change_cutoff_hours", now)
    if (tools.departure_at(b) - now).total_seconds() / 3600 < cutoff:
        return f"boarding station can only be changed up to {int(cutoff)} hours before departure"
    return None


def create_handover(desk, summary, booking_id, passenger_id, as_of=None):
    desk = desk if desk in DESKS else "complaints"
    b = tools.own_booking(booking_id, passenger_id) if booking_id else None
    ref = "HO-" + uuid.uuid4().hex[:5].upper()
    with connect() as con:
        con.execute("INSERT INTO handovers (ref, passenger_id, desk, summary, booking_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (ref, passenger_id, desk, summary[:500], b["booking_id"] if b else None,
                     now_ist(as_of).isoformat()))
    return {"ref": ref, "desk": desk, "summary": summary[:500], "booking_id": b["booking_id"] if b else None}


# ---------- 2. confirm and cancel (called by the API, never by the LLM) ----------

def confirm(action_id, passenger_id, as_of=None):
    now = now_ist(as_of)
    con = connect()
    try:
        with con:   # one transaction: everything below is saved together, or nothing is
            claimed = con.execute(
                "UPDATE actions SET status = 'done' WHERE action_id = ? AND passenger_id = ? "
                "AND status = 'proposed' AND expires_at > ?",
                (action_id, passenger_id, now.isoformat())).rowcount
            if claimed == 0:
                return previous_result(con, action_id, passenger_id)
            a = con.execute("SELECT * FROM actions WHERE action_id = ?", (action_id,)).fetchone()
            result = APPLY[a["action_type"]](con, a, json.loads(a["params"]), now)
            con.execute("UPDATE actions SET result = ? WHERE action_id = ?", (json.dumps(result), action_id))
    except PreviewChanged as e:
        with con:
            con.execute("UPDATE actions SET status = 'expired' WHERE action_id = ?", (action_id,))
        return {"answer_type": "refusal", "action_id": action_id,
                "answer": f"Nothing was changed: {e}. Please ask again for a new preview."}
    finally:
        con.close()
    return verify(action_id, result)


def cancel(action_id, passenger_id, as_of=None):
    with connect() as con:
        dropped = con.execute("UPDATE actions SET status = 'cancelled' WHERE action_id = ? "
                              "AND passenger_id = ? AND status = 'proposed'",
                              (action_id, passenger_id)).rowcount
    if dropped:
        return {"answer_type": "answer", "action_id": action_id, "answer": "Okay, nothing was changed."}
    return {"answer_type": "refusal", "action_id": action_id,
            "answer": "This request has expired or cannot be changed."}


def previous_result(con, action_id, passenger_id):
    """Confirm called again, too late, or by someone else: change nothing."""
    a = con.execute("SELECT status, result FROM actions WHERE action_id = ? AND passenger_id = ?",
                    (action_id, passenger_id)).fetchone()
    if a and a["status"] == "done":
        return {"answer_type": "action_done", "action_id": action_id,
                "answer": "This was already done.", "result": json.loads(a["result"])}
    return {"answer_type": "refusal", "action_id": action_id,
            "answer": "This request has expired or cannot be confirmed."}


# ---------- 3. the changes themselves (run inside confirm's transaction) ----------

def apply_cancel(con, a, p, now):
    quote = tools.refund_quote(a["booking_id"], a["passenger_id"], now.isoformat())
    if quote.get("refund") != p["refund"]:
        raise PreviewChanged(f"the refund is now {quote.get('refund')}, not {p['refund']}")
    b = con.execute("SELECT * FROM bookings WHERE booking_id = ?", (a["booking_id"],)).fetchone()
    freed = con.execute("SELECT COUNT(*) FROM booking_travellers WHERE booking_id = ? AND status = 'CNF'",
                        (b["booking_id"],)).fetchone()[0]
    con.execute("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = ?", (b["booking_id"],))
    con.execute("UPDATE seats SET available = available + ? "
                "WHERE train_no = ? AND journey_date = ? AND class = ?",
                (freed, b["train_no"], b["journey_date"], b["class"]))
    return {"booking_id": b["booking_id"], "status": "CANCELLED", "refund": p["refund"]}


def apply_book(con, a, p, now):
    """Confirmed while seats last, then waitlisted (RAC is left out to keep this simple)."""
    seat = con.execute("SELECT available FROM seats WHERE train_no = ? AND journey_date = ? AND class = ?",
                       (p["train_no"], p["journey_date"], p["class"])).fetchone()
    if seat is None:
        raise PreviewChanged("there is no seat data for this train and date")
    free = seat["available"]
    booking_id = "UR-" + str(random.randint(10000, 99999))
    while con.execute("SELECT 1 FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone():
        booking_id = "UR-" + str(random.randint(10000, 99999))
    statuses = []
    for person in p["travellers"]:
        status = "CNF" if free > 0 else "WL"
        free -= status == "CNF"
        statuses.append(status)
        con.execute("INSERT INTO booking_travellers (booking_id, traveller_name, age, status) "
                    "VALUES (?, ?, ?, ?)", (booking_id, person["name"], person["age"], status))
    booking_status = "CNF" if all(s == "CNF" for s in statuses) else "WL"
    con.execute("INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (booking_id, a["passenger_id"], p["train_no"], p["journey_date"], p["from"], p["to"],
                 p["class"], p["amount"], booking_status, now.isoformat()))
    con.execute("UPDATE seats SET available = ?, waitlist = waitlist + ? "
                "WHERE train_no = ? AND journey_date = ? AND class = ?",
                (free, statuses.count("WL"), p["train_no"], p["journey_date"], p["class"]))
    return {"booking_id": booking_id, "status": booking_status, "amount": p["amount"],
            "travellers": statuses}


def apply_change_boarding(con, a, p, now):
    b = con.execute("SELECT * FROM bookings WHERE booking_id = ?", (a["booking_id"],)).fetchone()
    error = boarding_change_error(b, p["new_station"], now)
    if error:
        raise PreviewChanged(error)
    con.execute("UPDATE bookings SET from_code = ? WHERE booking_id = ?", (p["new_station"], b["booking_id"]))
    return {"booking_id": b["booking_id"], "status": b["status"], "from": p["new_station"]}


APPLY = {"cancel_booking": apply_cancel, "book": apply_book, "change_boarding": apply_change_boarding}


def verify(action_id, result):
    """Read the booking back and check the change really happened (brief R5, step 4)."""
    with connect() as con:
        b = con.execute("SELECT status, from_code FROM bookings WHERE booking_id = ?",
                        (result["booking_id"],)).fetchone()
    checked = (b is not None and b["status"] == result["status"]
               and b["from_code"] == result.get("from", b["from_code"]))
    answer = f"Done. Booking {result['booking_id']} is now {b['status']}." if checked else \
        "The change was saved but could not be checked. Please contact support."
    return {"answer_type": "action_done" if checked else "not_found", "action_id": action_id,
            "answer": answer, "result": result, "checked": checked}
