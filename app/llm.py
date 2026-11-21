"""
llm.py - talks to the LLM.

Works with any OpenAI-compatible chat API:
  - Ollama (default): LLM_URL=http://localhost:11434/v1/chat/completions
  - Hosted model:     set LLM_URL, LLM_MODEL and LLM_API_KEY
Set MOCK_LLM=true to test without any model.
"""
import json
import os
import re

import requests

MOCK = os.getenv("MOCK_LLM", "false").lower() == "true"
URL = os.getenv("LLM_URL", "http://localhost:11434/v1/chat/completions")
MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")
API_KEY = os.getenv("LLM_API_KEY", "ollama")


def chat(messages, tools):
    """Send the conversation to the LLM. Returns one assistant message (text or tool calls)."""
    if MOCK:
        return mock_chat(messages)
    body = {"model": MODEL, "messages": messages, "tools": tools, "temperature": 0}
    headers = {"Authorization": f"Bearer {API_KEY}"}
    resp = requests.post(URL, json=body, headers=headers, timeout=120)
    resp.raise_for_status()
    return fix_text_tool_call(resp.json()["choices"][0]["message"])


def fix_text_tool_call(msg):
    """qwen2.5 sometimes writes a tool call as JSON text instead of tool_calls. Convert it."""
    text = msg.get("content") or ""
    if msg.get("tool_calls") or '"arguments"' not in text:
        return msg
    try:
        data = json.loads(re.search(r"\{.*\}", text, re.S)[0])
        return tool_call(data["name"], **data["arguments"])
    except (TypeError, ValueError, KeyError):
        return msg


# ---------- Mock mode: fixed replies so the team can test without a model ----------

def mock_chat(messages):
    last = messages[-1]
    if last["role"] == "tool":  # a tool already ran, so just show its output
        return {"role": "assistant", "content": "(mock) Tool result: " + last["content"]}

    text = last["content"].lower()
    booking = re.search(r"ur-\d+", text)
    route = re.search(r"from (\w+) to (\w+)", text)

    if route:
        return tool_call("search_trains", from_station=route[1], to_station=route[2], date="2026-12-05")
    if booking and "refund" in text:
        return tool_call("refund_quote", booking_id=booking[0].upper())
    if booking and "cancel" in text:
        return tool_call("propose_cancel", booking_id=booking[0].upper())
    if booking:
        return tool_call("booking_status", booking_id=booking[0].upper())
    if "my booking" in text or "status" in text:
        return tool_call("my_bookings")
    if any(w in text for w in ["rule", "pet", "id proof", "tatkal", "luggage"]):
        return tool_call("search_rules", query=text)
    return {"role": "assistant", "content": "(mock) From which station, and on which date?"}


def tool_call(name, **args):
    """Build a tool-call message in the same format a real LLM returns."""
    call = {"id": f"call_{name}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}
    return {"role": "assistant", "content": None, "tool_calls": [call]}
