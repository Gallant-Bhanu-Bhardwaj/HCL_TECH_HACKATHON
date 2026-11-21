from typing import Any, Dict, Optional

import requests


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 12, mock_mode: bool = False):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.mock_mode = mock_mode

    def _headers(self, passenger_id: str) -> Dict[str, str]:
        return {"X-Passenger-Id": passenger_id, "Content-Type": "application/json"}

    def _request(self, method: str, path: str, passenger_id: str, **kwargs) -> Dict[str, Any]:
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(passenger_id),
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            if not response.content:
                return {"success": True}
            return response.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out. Please try again."}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to the FastAPI backend."}
        except requests.exceptions.HTTPError as exc:
            try:
                detail = exc.response.json().get("detail")
            except Exception:
                detail = None
            return {"success": False, "error": detail or f"Backend returned HTTP {exc.response.status_code}."}
        except requests.exceptions.RequestException as exc:
            return {"success": False, "error": f"API request failed: {exc}"}
        except ValueError:
            return {"success": False, "error": "Backend returned invalid JSON."}

    def health_check(self) -> Dict[str, Any]:
        if self.mock_mode:
            return {"status": "healthy", "mode": "mock"}
        try:
            response = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"status": "offline", "error": "Request timed out"}
        except requests.exceptions.RequestException:
            return {"status": "offline", "error": "Cannot connect"}

    def send_chat_message(self, passenger_id: str, session_id: str, message: str) -> Dict[str, Any]:
        if self.mock_mode:
            return mock_chat_message(message)
        return self._request("POST", "/chat", passenger_id, json={"session_id": session_id, "message": message})

    def get_booking(self, passenger_id: str, booking_id: str) -> Dict[str, Any]:
        if self.mock_mode:
            booking = next((item for item in mock_bookings() if item["booking_id"] == booking_id), None)
            return booking or {"success": False, "answer_type": "not_found", "answer": "Booking not found."}
        return self._request("GET", f"/bookings/{booking_id}", passenger_id)

    def get_bookings(self, passenger_id: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {"success": True, "bookings": mock_bookings()}
        return {
            "success": False,
            "answer_type": "not_found",
            "answer": "A booking-list endpoint is not included in the provided backend contract.",
        }

    def confirm_action(self, passenger_id: str, action_id: str) -> Dict[str, Any]:
        if self.mock_mode:
            return mock_confirm(action_id)
        return self._request("POST", f"/actions/{action_id}/confirm", passenger_id)

    def cancel_action(self, passenger_id: str, action_id: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "success": True,
                "answer_type": "action_done",
                "answer": "Pending action cancelled. No ticket was cancelled.",
                "action_id": action_id,
                "trace_id": "TR-MOCK-ACTION-CANCEL",
            }
        return self._request("POST", f"/actions/{action_id}/cancel", passenger_id)

    def get_trace(self, passenger_id: str, trace_id: str) -> Dict[str, Any]:
        if self.mock_mode:
            return {"trace_id": trace_id, "status": "completed", "steps": ["Request received", "Intent identified", "Safe response returned"]}
        return self._request("GET", f"/trace/{trace_id}", passenger_id)


def mock_bookings():
    return [
        {"booking_id":"URAI-240501","train_number":"12304","train_name":"Prayagraj Express","from_station":"PRYJ - Prayagraj Junction","to_station":"NDLS - New Delhi","journey_date":"2026-12-08","travel_class":"Sleeper (SL)","status":"CNF","amount_paid":685,"pnr":"42******18","passengers":[{"name":"A. Sharma","age":32,"gender":"M","berth":"S4 / 31"}],"refundable":True,"refund_preview":{"estimated_refund":512,"cancellation_charges":173,"rules":"IRCTC confirmed-ticket cancellation rules may apply. Final refund is calculated by the backend.","processing":"Refund to original payment method within 3-7 working days.","policy_reference":"Railway cancellation policy - current schedule"}},
        {"booking_id":"URAI-240826","train_number":"22435","train_name":"Vande Bharat Express","from_station":"PRYJ - Prayagraj Junction","to_station":"ANVT - Anand Vihar Terminal","journey_date":"2026-12-12","travel_class":"Chair Car (CC)","status":"RAC","amount_paid":920,"pnr":"61******44","passengers":[{"name":"A. Sharma","age":32,"gender":"M","berth":"RAC 14"}],"refundable":True,"refund_preview":{"estimated_refund":735,"cancellation_charges":185,"rules":"RAC cancellation charges are calculated by the applicable railway rules.","processing":"Refund to original payment method within 3-7 working days.","policy_reference":"RAC cancellation policy"}},
    ]


def mock_chat_message(message: str) -> Dict[str, Any]:
    text = message.lower()
    if any(word in text for word in ("cancel", "radd", "cancel karo")):
        return {"answer_type":"confirm_needed","answer":"I found an eligible booking. Please review the cancellation preview before confirming.","action_id":"ACT-CANCEL-240501","trace_id":"TR-MOCK-001","preview":{"booking_id":"URAI-240501","train_number":"12304","train_name":"Prayagraj Express","journey_date":"2026-12-08","status":"CNF","amount_paid":685,"estimated_refund":512,"cancellation_charges":173,"rules":"Confirmed-ticket cancellation charges are returned by the backend. No official calculation is made by this frontend."}}
    if any(word in text for word in ("refund", "paisa", "wapsi")):
        return {"answer_type":"answer","answer":"The estimated refund for booking URAI-240501 is ₹512, with ₹173 cancellation charges. This is mock preview data and final refund will be calculated by the backend.","action_id":None,"trace_id":"TR-MOCK-002"}
    if any(word in text for word in ("book", "booking", "meri ticket")):
        return {"answer_type":"answer","answer":"You have 2 bookings. URAI-240501 is confirmed and URAI-240826 is RAC. Open My Bookings for complete details.","action_id":None,"trace_id":"TR-MOCK-003"}
    if any(word in text for word in ("human", "agent", "complaint", "shikayat", "helpdesk")):
        return {"answer_type":"handed_to_human","answer":"A support request can be escalated to a human agent. Please share the issue; support staff is expected to contact you through the registered channel.","action_id":None,"trace_id":"TR-MOCK-HUMAN"}
    if any(word in text for word in ("seat", "availability")):
        return {"answer_type":"clarification","answer":"For seat availability, please share the from station, to station and journey date. I can guide you to the Search Trains page.","action_id":None,"trace_id":"TR-MOCK-004"}
    return {"answer_type":"answer","answer":"Namaste! Welcome to Ujjwal Rail AI. I can help with train search, bookings, cancellations and refund information.","action_id":None,"trace_id":"TR-MOCK-005"}


def mock_confirm(action_id: str) -> Dict[str, Any]:
    if "CANCEL" in action_id.upper():
        return {"success":True,"answer_type":"action_done","answer":"Cancellation completed in mock mode. Booking status is now Cancelled.","action_id":action_id,"trace_id":"TR-MOCK-CANCEL","updated_status":"CANCELLED","refund":{"estimated_refund":512,"cancellation_charges":173,"processing":"Refund to original payment method within 3-7 working days."}}
    return {"success":True,"answer_type":"action_done","answer":"The action has been confirmed in mock mode.","action_id":action_id,"trace_id":"TR-MOCK-CONFIRM","updated_status":"CNF"}


def mock_cancel(action_id: str) -> Dict[str, Any]:
    return {"success":True,"answer_type":"action_done","answer":"Cancellation confirmed in mock mode. Booking status is now Cancelled.","action_id":action_id,"trace_id":"TR-MOCK-CANCEL","updated_status":"CANCELLED","refund":{"estimated_refund":512,"cancellation_charges":173,"processing":"Refund to original payment method within 3-7 working days."}}
