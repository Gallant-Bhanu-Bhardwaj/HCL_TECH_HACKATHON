"""POST /actions/{id}/confirm and /cancel (api-contracts §4.2, §4.3).

No LLM involved on either path (D-principle 3). Typed errors from the
ActionService (app/actions/errors.py) are translated to the exact
contract status codes by the handlers in app/api/errors.py.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_action_service, get_passenger_context
from app.contracts.enums import AnswerType
from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import ActionMini, CancelResponse, ConfirmResponse

router = APIRouter()


@router.post("/actions/{action_id}/confirm", response_model=ConfirmResponse)
def confirm_action(
    action_id: str,
    ctx: PassengerContext = Depends(get_passenger_context),
    action_service=Depends(get_action_service),
) -> ConfirmResponse:
    result = action_service.confirm(ctx, action_id)

    if result.idempotent_replay:
        answer = f"That change was already made. Booking {result.action.booking_id} is {result.verification.booking_status}."
    else:
        answer = f"Booking {result.action.booking_id} is cancelled. Refund of Rs {result.verification.refund} is recorded."

    return ConfirmResponse(
        trace_id=uuid.uuid4().hex[:8],
        answer_type=AnswerType.ACTION_DONE,
        answer=answer,
        action=result.action,
        verification=result.verification,
        idempotent_replay=result.idempotent_replay,
    )


@router.post("/actions/{action_id}/cancel", response_model=CancelResponse)
def cancel_action(
    action_id: str,
    ctx: PassengerContext = Depends(get_passenger_context),
    action_service=Depends(get_action_service),
) -> CancelResponse:
    result = action_service.cancel(ctx, action_id)
    return CancelResponse(
        trace_id=uuid.uuid4().hex[:8],
        answer_type=AnswerType.ANSWER,
        answer="Okay, I have dropped that request. Nothing was changed.",
        action=ActionMini(action_id=result.action.action_id, status=result.action.status),
    )
