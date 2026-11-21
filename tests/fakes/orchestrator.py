"""Canned FakeOrchestrator — always resolves to the guide's §6.1 example
scenario, but PROPOSES THE ACTION FOR REAL through the wired
ActionService so the returned action_id is actually confirmable. No
intent parsing, no tools, no RAG, no LLM (T3) — just enough wiring for
the propose -> confirm -> verify path to be exercised end to end.
"""
from __future__ import annotations

from app.contracts.enums import AnswerType
from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import ChatResponse, PendingActionRef, Refusal, SourceRef, ToolCall

_SAMPLE_BOOKING_ID = "UR-30418"


class FakeOrchestrator:
    def __init__(self, clock, action_service) -> None:
        self._clock = clock
        self._action_service = action_service

    def handle_chat(self, ctx: PassengerContext, session_id: str, message: str) -> ChatResponse:
        import uuid

        proposal = self._action_service.propose_cancel(ctx, _SAMPLE_BOOKING_ID)
        trace_id = uuid.uuid4().hex[:8]

        if isinstance(proposal, Refusal):
            return ChatResponse(
                trace_id=trace_id,
                answer_type=AnswerType.REFUSAL,
                answer=proposal.reason,
                handed_to_human=None,
            )

        return ChatResponse(
            trace_id=trace_id,
            answer_type=AnswerType.CONFIRM_NEEDED,
            answer=(
                f"Cancelling booking {_SAMPLE_BOOKING_ID} (12123, Pune to Nagpur, 5 Dec, 2AC, "
                f"1 seat) now gives you a refund of Rs {proposal.preview.get('refund', 0)}. Shall I go ahead?"
            ),
            sources=[
                SourceRef(doc_id="RUL-CAN-01", section="3. Refund table"),
                SourceRef(doc_id="CIR-2026-07", section="Revised charges"),
            ],
            tools=[ToolCall(tool="refund_quote", output=dict(proposal.preview))],
            pending_action=PendingActionRef(
                action_id=proposal.action_id,
                type=proposal.type,
                booking_id=proposal.booking_id,
                expires_at=proposal.expires_at,
            ),
            handed_to_human=None,
        )
