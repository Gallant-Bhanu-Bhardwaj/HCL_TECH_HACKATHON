from typing import Dict, Any


def normalize_chat_response(response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return {"answer_type": "not_found", "answer": "The backend returned an unexpected response."}
    if response.get("success") is False:
        return {"answer_type": "refusal", "answer": response.get("error", "The request could not be completed."), "trace_id": response.get("trace_id")}
    return {
        "answer_type": response.get("answer_type", "answer"),
        "answer": response.get("answer", "No response received."),
        "action_id": response.get("action_id"),
        "trace_id": response.get("trace_id"),
        "preview": response.get("preview"),
        "raw": response,
    }
