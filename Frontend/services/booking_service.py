from typing import Dict, Any, List


def normalize_booking_list(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    if isinstance(response.get("bookings"), list):
        return response["bookings"]
    if isinstance(response.get("data"), list):
        return response["data"]
    if isinstance(response.get("booking"), dict):
        return [response["booking"]]
    return []
