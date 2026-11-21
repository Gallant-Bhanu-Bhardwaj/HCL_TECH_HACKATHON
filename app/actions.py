"""
actions.py - the ONLY module that changes bookings.   STEP 1: STUB VERSION

propose_* only describe a change and return an action_id; nothing is written yet.
confirm() and cancel() are called by POST /actions/{id}/confirm and /cancel,
never by the LLM.
"""
from app import tools


def propose_cancel(booking_id, passenger_id, as_of=None):
    quote = tools.refund_quote(booking_id, passenger_id, as_of)
    if "error" in quote:
        return quote
    return {"action_id": "ACT-STUB01", "type": "cancel_booking", "booking_id": booking_id,
            "refund": quote["refund"], "expires_at": "2026-12-03T10:15:00+05:30"}


def propose_booking(train_no, date, from_station, to_station, travel_class, travellers,
                    passenger_id, as_of=None):
    return {"action_id": "ACT-STUB02", "type": "book", "train_no": train_no, "date": date,
            "class": travel_class, "travellers": travellers, "amount": 2040,
            "expires_at": "2026-12-03T10:15:00+05:30"}


def propose_change_boarding(booking_id, new_station, passenger_id, as_of=None):
    if "error" in tools.booking_status(booking_id, passenger_id, as_of):
        return tools.NOT_YOURS
    return {"action_id": "ACT-STUB03", "type": "change_boarding", "booking_id": booking_id,
            "new_station": new_station, "expires_at": "2026-12-03T10:15:00+05:30"}


def create_handover(desk, summary, booking_id, passenger_id, as_of=None):
    return {"ref": "HO-STUB1", "desk": desk, "summary": summary, "booking_id": booking_id or None}


def confirm(action_id, passenger_id, as_of=None):
    return {"answer_type": "action_done", "action_id": action_id, "checked": True,
            "answer": "Done (stub): nothing was really changed yet."}


def cancel(action_id, passenger_id, as_of=None):
    return {"answer_type": "answer", "action_id": action_id, "answer": "Okay, nothing was changed."}
