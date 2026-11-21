"""
tools.py - read-only facts for the agent. Every answer comes from the database.

Rules every function follows:
  - passenger_id and as_of are always passed in by agent.py, never by the LLM.
  - A booking that is missing OR belongs to someone else returns NOT_YOURS.
  - Money is a whole number of rupees (int). Dates are 'YYYY-MM-DD'.
  - journey_date = the day the train leaves its FIRST station (as in the brief's tables).
"""
import difflib
from datetime import date, datetime, timedelta, timezone

from app.db import connect, get_setting

NOT_YOURS = {"error": "not_in_your_account"}   # agent.py checks this exact text
IST = timezone(timedelta(hours=5, minutes=30))


# ---------- helpers ----------

def now_from(as_of):
    """as_of is an ISO time string from the request, or None for 'now'."""
    return datetime.fromisoformat(as_of) if as_of else datetime.now(IST)


def find_stations(text):
    """List of station codes matching a name, code or alias: 0 = unknown, 2+ = ambiguous."""
    names = {}
    with connect() as con:
        for r in con.execute("SELECT station_code, name, other_names FROM stations"):
            for n in [r["station_code"], r["name"]] + (r["other_names"] or "").split(","):
                if n.strip():
                    names[n.strip().lower()] = r["station_code"]
    text = (text or "").strip().lower()
    if text in names:
        return [names[text]]
    close = difflib.get_close_matches(text, list(names), n=3, cutoff=0.75)
    return sorted({names[c] for c in close})


def one_station(text):
    """One station code, or an error dict the LLM can turn into a question."""
    codes = find_stations(text)
    if len(codes) == 1:
        return codes[0], None
    if not codes:
        return None, {"error": f"unknown station '{text}'"}
    return None, {"error": f"'{text}' could mean {', '.join(codes)}. Ask which one."}


def own_booking(booking_id, passenger_id):
    """The booking only if it belongs to this passenger, else None."""
    with connect() as con:
        return con.execute("SELECT * FROM bookings WHERE booking_id = ? AND passenger_id = ?",
                           ((booking_id or "").upper(), passenger_id)).fetchone()


def booking_details(b):
    with connect() as con:
        travellers = con.execute("SELECT traveller_name AS name, status, coach, berth "
                                 "FROM booking_travellers WHERE booking_id = ?", (b["booking_id"],))
        return {"booking_id": b["booking_id"], "train_no": b["train_no"],
                "journey_date": b["journey_date"], "from": b["from_code"], "to": b["to_code"],
                "class": b["class"], "status": b["status"], "amount_paid": b["amount_paid"],
                "departs_at": departure_at(b).isoformat(), "travellers": [dict(t) for t in travellers]}


def departure_at(b):
    """Exact date and time the train leaves the passenger's boarding station."""
    with connect() as con:
        stop = con.execute("SELECT departure, day_offset FROM train_stops "
                           "WHERE train_no = ? AND station_code = ?",
                           (b["train_no"], b["from_code"])).fetchone()
    day = date.fromisoformat(b["journey_date"]) + timedelta(days=stop["day_offset"])
    return datetime.fromisoformat(f"{day}T{stop['departure']}").replace(tzinfo=IST)


# ---------- tools the LLM can call ----------

SEARCH_SQL = """
SELECT t.train_no, t.name, t.runs_on, a.departure, a.day_offset AS dep_day,
       b.arrival, b.day_offset AS arr_day
FROM trains t
JOIN train_stops a ON a.train_no = t.train_no AND a.station_code = ?
JOIN train_stops b ON b.train_no = t.train_no AND b.station_code = ?
WHERE a.stop_order < b.stop_order"""


def search_trains(from_station, to_station, date, passenger_id=None, as_of=None):
    """Trains leaving from_station on this date (the passenger's travel date)."""
    frm, err = one_station(from_station)
    to, err2 = one_station(to_station)
    if err or err2:
        return err or err2
    travel_day = datetime.strptime(date, "%Y-%m-%d").date()
    trains = []
    with connect() as con:
        for r in con.execute(SEARCH_SQL, (frm, to)):
            origin_day = travel_day - timedelta(days=r["dep_day"])   # day it left its first station
            if r["runs_on"] == "Daily" or origin_day.strftime("%a") in r["runs_on"].split(","):
                trains.append({"train_no": r["train_no"], "name": r["name"], "from": frm, "to": to,
                               "departs": f"{travel_day} {r['departure']}",
                               "arrives": f"{origin_day + timedelta(days=r['arr_day'])} {r['arrival']}",
                               "journey_date": origin_day.isoformat()})
    return sorted(trains, key=lambda t: t["departs"])


def check_seats(train_no, date, travel_class, passenger_id=None, as_of=None):
    """date is the journey_date returned by search_trains."""
    with connect() as con:
        r = con.execute("SELECT available, rac, waitlist FROM seats "
                        "WHERE train_no = ? AND journey_date = ? AND class = ?",
                        (train_no, date, travel_class.upper())).fetchone()
    if r is None:
        return {}
    return {"train_no": train_no, "journey_date": date, "class": travel_class.upper(), **dict(r)}


def get_fare(train_no, from_station, to_station, travel_class, passenger_id=None, as_of=None):
    frm, err = one_station(from_station)
    to, err2 = one_station(to_station)
    if err or err2:
        return err or err2
    with connect() as con:
        r = con.execute("SELECT fare FROM fares WHERE train_no = ? AND class = ? "
                        "AND from_code = ? AND to_code = ?",
                        (train_no, travel_class.upper(), frm, to)).fetchone()
    if r is None:
        return {}
    return {"train_no": train_no, "from": frm, "to": to, "class": travel_class.upper(), "fare": r["fare"]}


def my_bookings(passenger_id, as_of=None):
    with connect() as con:
        rows = con.execute("SELECT * FROM bookings WHERE passenger_id = ? ORDER BY journey_date",
                           (passenger_id,)).fetchall()
    return [booking_details(b) for b in rows]


def booking_status(booking_id, passenger_id, as_of=None):
    b = own_booking(booking_id, passenger_id)
    return booking_details(b) if b else NOT_YOURS


def cancel_charge(travel_class, hours, paid, when):
    """(charge, source_doc) for cancelling this many hours before departure."""
    flat, src = get_setting(f"cancel_charge_{travel_class}_over_48h", when)
    if hours >= get_setting("cutoff_flat_hours", when)[0]:
        return round(flat), src
    if hours >= get_setting("cutoff_mid_hours", when)[0]:
        pct, src = get_setting("cancel_pct_12_to_48h", when)
    elif hours >= get_setting("cutoff_no_refund_hours", when)[0]:
        pct, src = get_setting("cancel_pct_4_to_12h", when)
    else:
        return paid, "RUL-CAN-01"                       # too late: no refund
    return max(round(flat), round(paid * pct / 100)), src


def refund_quote(booking_id, passenger_id, as_of=None):
    b = own_booking(booking_id, passenger_id)
    if b is None:
        return NOT_YOURS
    if b["status"] == "CANCELLED":
        return {"error": "this booking is already cancelled"}
    if b["status"] == "TRAIN_CANCELLED":
        return {"booking_id": b["booking_id"], "amount_paid": b["amount_paid"], "charge": 0,
                "refund": b["amount_paid"], "rule": "RUL-TCN-01"}
    now = now_from(as_of)
    hours = (departure_at(b) - now).total_seconds() / 3600
    if hours < 0:
        return {"error": "the train has already left, so it cannot be cancelled"}
    charge, src = cancel_charge(b["class"], hours, b["amount_paid"], now)
    return {"booking_id": b["booking_id"], "amount_paid": b["amount_paid"], "charge": charge,
            "refund": b["amount_paid"] - charge, "hours_before_departure": round(hours, 2),
            "rule": src}
