"""Step 2: the LLM picks a tool, Python runs it, the LLM explains the result.
This is the whole idea behind agent.py. Run: python step2_one_tool.py"""
import json

import requests

URL = "http://localhost:11434/v1/chat/completions"

TOOLS = [{"type": "function", "function": {
    "name": "search_trains",
    "description": "Find trains between two stations on a date (YYYY-MM-DD).",
    "parameters": {"type": "object",
                   "properties": {"from_station": {"type": "string"},
                                  "to_station": {"type": "string"},
                                  "date": {"type": "string"}},
                   "required": ["from_station", "to_station", "date"]}}}]


def search_trains(from_station, to_station, date):  # fake data for now
    return [{"train_no": "12123", "from": from_station, "to": to_station, "date": date,
             "departs": "18:40", "arrives": "06:10"}]


def ask(messages):
    body = {"model": "qwen2.5:7b", "messages": messages, "tools": TOOLS, "temperature": 0}
    return requests.post(URL, json=body, timeout=120).json()["choices"][0]["message"]


messages = [
    {"role": "system", "content": "You help Ujjwal Rail passengers. Today is 2026-12-03. Always use tools for train data."},
    {"role": "user", "content": "Trains from Pune to Nagpur on 5 Dec?"},
]

# 1. LLM decides which tool to call
reply = ask(messages)
if not reply.get("tool_calls"):
    print("No tool call. LLM said:", reply.get("content"))
    raise SystemExit

call = reply["tool_calls"][0]
args = json.loads(call["function"]["arguments"])
print("LLM wants:", call["function"]["name"], args)

# 2. Python runs the tool
result = search_trains(**args)

# 3. Send the result back; the LLM writes the final answer
messages.append({"role": "assistant", "content": "", "tool_calls": reply["tool_calls"]})
messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
print("Answer:", ask(messages)["content"])
