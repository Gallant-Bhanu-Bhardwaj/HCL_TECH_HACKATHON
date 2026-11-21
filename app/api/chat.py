"""POST /chat (api-contracts §4.1).

Phase 0: delegates straight to the wired Orchestrator (a fake in this
branch) and persists a trace. No intent parsing, no tools, no RAG yet —
those land with the real AI/LLM, Backend and RAG implementations.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_clock,
    get_orchestrator,
    get_passenger_context,
    get_trace_store,
)
from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import ChatRequest, ChatResponse, TraceRecord

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    ctx: PassengerContext = Depends(get_passenger_context),
    orchestrator=Depends(get_orchestrator),
    trace_store=Depends(get_trace_store),
    clock=Depends(get_clock),
) -> ChatResponse:
    if body.as_of is not None:
        ctx.as_of = body.as_of  # business clock override (api-contracts §2)

    response = orchestrator.handle_chat(ctx, body.session_id, body.message)

    trace_store.save(
        TraceRecord(
            trace_id=response.trace_id,
            created_at=clock.now_utc(),  # operational clock, distinct from business as_of (D6)
            as_of=ctx.as_of,
            endpoint="/chat",
            session_id=body.session_id,
            passenger_id=ctx.passenger_id,
            request={"message": body.message},
            response=response.model_dump(mode="json"),
        )
    )
    return response
