"""GET /bookings/{id} (api-contracts §4.4).

Same privacy rule as /chat (R8): missing and foreign bookings return the
identical 404 body, via ResourceNotAccessible.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_passenger_context, get_tool_registry
from app.contracts.interfaces import NotAccessible, PassengerContext
from app.contracts.schemas import BookingView
from app.privacy.errors import ResourceNotAccessible

router = APIRouter()


@router.get("/bookings/{booking_id}", response_model=BookingView)
def get_booking(
    booking_id: str,
    ctx: PassengerContext = Depends(get_passenger_context),
    tool_registry=Depends(get_tool_registry),
) -> BookingView:
    result = tool_registry.get_booking_status(ctx, booking_id)
    if isinstance(result, NotAccessible):
        raise ResourceNotAccessible(booking_id)
    return result
