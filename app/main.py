"""
main.py - the API (brief Section 6). Start it from the repo folder with:
    uvicorn app.main:app --reload --port 8000

Who is asking always comes from the X-Passenger-Id header, never from the message.
Every reply gets a trace_id, and the whole request + reply is saved in the traces table.
"""
import json
import uuid
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app import actions, agent, rag, tools
from app.db import connect

app = FastAPI(title="Ujjwal Rail Assistant")


class ChatIn(BaseModel):
    session_id: str
    message: str
    as_of: str | None = None      # e.g. "2026-12-03T10:00:00+05:30"; empty means now


class AsOf(BaseModel):
    as_of: str | None = None


def now_or(as_of):
    return as_of or datetime.now(tools.IST).isoformat(timespec="seconds")


def save_trace(endpoint, passenger_id, request, response):
    """Store the full record of one reply so judges can replay it (brief R10)."""
    trace_id = uuid.uuid4().hex[:8]
    response["trace_id"] = trace_id
    record = {"trace_id": trace_id, "endpoint": endpoint, "passenger_id": passenger_id,
              "saved_at": now_or(None), "request": request, "response": response}
    with connect() as con:
        con.execute("INSERT INTO traces (trace_id, data) VALUES (?, ?)",
                    (trace_id, json.dumps(record, default=str, ensure_ascii=False)))
    return response


@app.get("/health")
def health():
    with connect() as con:
        con.execute("SELECT 1")
    return {"status": "ok"}


@app.post("/chat")
def chat(body: ChatIn, x_passenger_id: str = Header(...)):
    as_of = now_or(body.as_of)
    try:
        result = agent.handle(x_passenger_id, body.session_id, body.message, as_of)
    except Exception as e:      # the API must always answer, and the failure is still traced
        result = {"answer_type": "not_found", "answer": "Sorry, something went wrong. Please try again.",
                  "sources": [], "tools": [], "pending_action": None, "handed_to_human": None,
                  "error": repr(e)}
    request = {"session_id": body.session_id, "message": body.message, "as_of": as_of}
    return save_trace("/chat", x_passenger_id, request, result)


@app.post("/actions/{action_id}/confirm")
def confirm(action_id: str, body: AsOf | None = None, x_passenger_id: str = Header(...)):
    as_of = now_or(body.as_of if body else None)
    result = actions.confirm(action_id, x_passenger_id, as_of)
    return save_trace("/confirm", x_passenger_id, {"action_id": action_id, "as_of": as_of}, result)


@app.post("/actions/{action_id}/cancel")
def cancel(action_id: str, body: AsOf | None = None, x_passenger_id: str = Header(...)):
    as_of = now_or(body.as_of if body else None)
    result = actions.cancel(action_id, x_passenger_id, as_of)
    return save_trace("/cancel", x_passenger_id, {"action_id": action_id, "as_of": as_of}, result)


@app.get("/bookings/{booking_id}")
def get_booking(booking_id: str, x_passenger_id: str = Header(...)):
    result = tools.booking_status(booking_id, x_passenger_id)
    if result == tools.NOT_YOURS:
        raise HTTPException(404, "Booking not found")   # same for missing and someone else's
    return result


@app.post("/ingest")
def ingest(doc: dict):
    """Add or update a rule, circular or FAQ. The RAG owner writes rag.ingest(doc)."""
    if not hasattr(rag, "ingest"):
        raise HTTPException(501, "rag.ingest is not written yet")
    return rag.ingest(doc)


@app.get("/trace/{trace_id}")
def get_trace(trace_id: str):
    with connect() as con:
        row = con.execute("SELECT data FROM traces WHERE trace_id = ?", (trace_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Trace not found")
    return json.loads(row["data"])
