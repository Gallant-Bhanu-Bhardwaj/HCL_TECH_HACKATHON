import re


def mask_passenger_id(passenger_id: str) -> str:
    if not passenger_id:
        return "Not set"
    if len(passenger_id) <= 4:
        return "****"
    return f"{passenger_id[:3]}***{passenger_id[-2:]}"


def mask_phone(phone: str) -> str:
    if not phone:
        return "-"
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return "****"
    return f"***-***-{digits[-4:]}"


def rupee(value) -> str:
    if value is None:
        return "Not available"
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def status_label(status: str) -> str:
    labels = {
        "CNF": "Confirmed",
        "RAC": "RAC",
        "WL": "Waitlist",
        "CANCELLED": "Cancelled",
    }
    return labels.get(str(status).upper(), status or "Unknown")
