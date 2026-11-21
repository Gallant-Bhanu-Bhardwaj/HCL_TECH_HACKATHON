"""main.py - minimal /chat endpoint to test the agent locally."""
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header
from pydantic import BaseModel

from app.agent import handle

app = FastAPI()


class ChatIn(BaseModel):
    session_id: str
    message: str
    as_of: str | None = None


@app.post("/chat")
def chat(body: ChatIn, x_passenger_id: str = Header()):
    as_of = body.as_of or datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds")
    return handle(x_passenger_id, body.session_id, body.message, as_of)


@app.get("/health")
def health():
    return {"status": "ok"}
