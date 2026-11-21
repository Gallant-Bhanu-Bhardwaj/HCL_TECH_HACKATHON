"""FastAPI dependencies: pull wired implementations off app.state, and
build the per-request PassengerContext (identity is injected from the
header ONLY — never from the body or message text).
"""
from __future__ import annotations

from fastapi import Depends, Header, Request

from app.audit.recorder import InMemoryTraceRecorder
from app.contracts.interfaces import PassengerContext
from app.privacy.errors import Unauthenticated


def get_clock(request: Request):
    return request.app.state.clock


def get_tool_registry(request: Request):
    return request.app.state.tool_registry


def get_retriever(request: Request):
    return request.app.state.retriever


def get_action_service(request: Request):
    return request.app.state.action_service


def get_handoff_service(request: Request):
    return request.app.state.handoff_service


def get_session_store(request: Request):
    return request.app.state.session_store


def get_orchestrator(request: Request):
    return request.app.state.orchestrator


def get_trace_store(request: Request):
    return request.app.state.trace_store


def get_passenger_context(
    x_passenger_id: str | None = Header(default=None, alias="X-Passenger-Id"),
    clock=Depends(get_clock),
) -> PassengerContext:
    if not x_passenger_id:
        raise Unauthenticated()
    return PassengerContext(
        passenger_id=x_passenger_id,
        preferred_language="en",
        as_of=clock.now_utc(),
        trace=InMemoryTraceRecorder(),
    )
