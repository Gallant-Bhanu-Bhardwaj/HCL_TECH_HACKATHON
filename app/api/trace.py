"""GET /trace/{trace_id} (api-contracts §4.5, O8: owning passenger only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_passenger_context, get_trace_store
from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import TraceRecord
from app.privacy.errors import ResourceNotAccessible

router = APIRouter()


@router.get("/trace/{trace_id}", response_model=TraceRecord)
def get_trace(
    trace_id: str,
    ctx: PassengerContext = Depends(get_passenger_context),
    trace_store=Depends(get_trace_store),
) -> TraceRecord:
    record = trace_store.get_owned(trace_id, ctx.passenger_id)
    if record is None:
        raise ResourceNotAccessible(trace_id)
    return record
