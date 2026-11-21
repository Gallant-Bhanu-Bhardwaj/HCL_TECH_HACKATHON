"""
tools.py - read-only facts for the agent.   STEP 1: STUB VERSION

Every function returns fixed data in its final shape, so agent.py works today.
In later steps, replace each body with real SQL. Keep the names, arguments
and return shapes exactly as they are.

Rules every function follows:
  - passenger_id and as_of are always passed in by agent.py, never by the LLM.
  - A booking that is missing OR belongs to someone else returns NOT_YOURS.
  - Money is a whole number of rupees (int).
"""
NOT_YOURS = {"error": "not_in_your_account"}   # agent.py checks this exact text


def search_trains(from_station, to_station, date, passenger_id=None, as_of=None):
    return [{"train_no": "12123", "name": "Deccan Express", "from": "PUNE", "to": "NGP",
             "date": date, "departs": "18:10", "arrives": "06:00", "arrives_day": "+1"}]


def check_seats(train_no, date, travel_class, passenger_id=None, as_of=None):
    return {"train_no": train_no, "date": date, "class": travel_class,
            "available": 12, "rac": 0, "waitlist": 0}


def get_fare(train_no, from_station, to_station, travel_class, passenger_id=None, as_of=None):
    return {"train_no": train_no, "from": "PUNE", "to": "NGP", "class": travel_class, "fare": 2040}


def my_bookings(passenger_id, as_of=None):
    if passenger_id != "P007":
        return []
    return [booking_status("UR-30418", passenger_id)]


def booking_status(booking_id, passenger_id, as_of=None):
    if booking_id != "UR-30418" or passenger_id != "P007":
        return NOT_YOURS
    return {"booking_id": "UR-30418", "train_no": "12123", "journey_date": "2026-12-05",
            "from": "PUNE", "to": "NGP", "class": "2AC", "status": "CNF", "amount_paid": 2040,
            "travellers": [{"name": "Asha", "status": "CNF", "coach": "A1", "berth": "12"}]}


def refund_quote(booking_id, passenger_id, as_of=None):
    if booking_id != "UR-30418" or passenger_id != "P007":
        return NOT_YOURS
    return {"booking_id": booking_id, "amount_paid": 2040, "charge": 200, "refund": 1840,
            "hours_before_departure": 51.0, "rule": "RUL-CAN-01"}
