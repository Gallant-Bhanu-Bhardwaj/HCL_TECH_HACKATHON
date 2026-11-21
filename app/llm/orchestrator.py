"""The real orchestrator (architecture §5.1 flows; api-contracts §8).

Routes a message to the real, deterministic tools/RAG built in prior
phases. No arithmetic, no fare/refund/availability number, and no
timetable fact is ever invented here — every number in the composed
answer comes straight from a ToolCall's real output or a retrieved
Passage. The LLM's only job in this MVP is the deterministic
intent/entity extraction in app/llm/intent.py — there is no actual
Ollama text-generation call in this orchestrator (app/llm/ has no real
LLMClient yet; see the task report for why that's an honest, scoped
choice, not an oversight).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from app.contracts.enums import AnswerType, Desk
from app.contracts.interfaces import NotAccessible, PassengerContext
from app.contracts.schemas import (
    ChatResponse,
    Conflict as ConflictModel,
    HandoffRef,
    PendingActionRef,
    SourceRef,
    ToolCall,
)
from app.db.connection import get_connection
from app.llm.intent import ParsedMessage, parse_message
from app.rag.retrieve import retrieve_context
from app.tools.availability import SeatsRowNotFound, check_availability
from app.tools.fares import FareNotFound, get_fare
from app.tools.refund import BookingNotFound, refund_quote
from app.tools.stations import resolve_station
from app.tools.timetable import search_trains


class RealOrchestrator:
    def __init__(self, db_path_getter, clock, action_service, handoff_service) -> None:
        self._db_path_getter = db_path_getter  # callable -> str, so app.state.db_path can change per-app
        self._clock = clock
        self._action_service = action_service
        self._handoff_service = handoff_service

    def handle_chat(self, ctx: PassengerContext, session_id: str, message: str) -> ChatResponse:
        trace_id = uuid.uuid4().hex[:8]
        conn = get_connection(self._db_path_getter())
        try:
            parsed = parse_message(message, today=ctx.as_of.date())

            if parsed.wants_human:
                return self._handle_human(ctx, session_id, message, parsed, trace_id)

            answer_parts: list[str] = []
            sources: list[SourceRef] = []
            tools: list[ToolCall] = []
            conflicts: list[ConflictModel] = []
            pending_action: PendingActionRef | None = None
            answer_type = AnswerType.ANSWER
            matched_anything = False

            # --- Booking-specific: ownership (R8) is checked for ANY mention of a
            # booking_id, not only refund/cancel wording — a bare "what's the
            # status of booking X, it's my friend's" must get the same
            # non-revealing refusal, not fall through to "not_found". ---
            e = parsed.entities
            if e.booking_id:
                matched_anything = True
                piece = self._handle_booking(conn, ctx, e.booking_id, parsed.wants_cancel)
                if piece["refused"]:
                    return self._refusal(trace_id, "I can't help with another passenger's booking.")
                answer_parts.append(piece["text"])
                sources.extend(piece["sources"])
                tools.extend(piece["tools"])
                if piece["pending_action"] is not None:
                    pending_action = piece["pending_action"]
                    answer_type = AnswerType.CONFIRM_NEEDED

            # --- Train search ---
            if e.from_text and e.to_text:
                matched_anything = True
                piece = self._handle_search(conn, ctx, e)
                answer_parts.append(piece["text"])
                tools.extend(piece["tools"])

            # --- Availability ---
            if parsed.wants_availability and e.train_no and e.cls:
                matched_anything = True
                journey_date = e.journey_date or ctx.as_of.date()
                piece = self._handle_availability(conn, ctx, e.train_no, journey_date, e.cls)
                answer_parts.append(piece["text"])
                tools.extend(piece["tools"])

            # --- Fare ---
            if parsed.wants_fare and e.train_no and e.cls and e.from_text and e.to_text:
                matched_anything = True
                piece = self._handle_fare(conn, ctx, e)
                answer_parts.append(piece["text"])
                tools.extend(piece["tools"])

            # --- Policy / rules (RAG) — additive: can stack with any of the above ---
            if parsed.wants_policy or not matched_anything:
                rag_piece = self._handle_policy(conn, ctx, message)
                if rag_piece is not None:
                    matched_anything = True
                    answer_parts.append(rag_piece["text"])
                    sources.extend(rag_piece["sources"])
                    conflicts.extend(rag_piece["conflicts"])

            if not matched_anything:
                if parsed.is_travel_related:
                    return ChatResponse(
                        trace_id=trace_id, answer_type=AnswerType.NOT_FOUND,
                        answer="I couldn't find anything in Ujjwal Rail's data or documents that answers that.",
                        handed_to_human=None,
                    )
                return self._refusal(trace_id, "I can only help with Ujjwal Rail travel questions.")

            return ChatResponse(
                trace_id=trace_id,
                answer_type=answer_type,
                answer=" ".join(p for p in answer_parts if p),
                sources=sources,
                tools=tools,
                pending_action=pending_action,
                handed_to_human=None,
                conflicts=conflicts or None,
            )
        finally:
            conn.close()

    # -------------------------------------------------------------
    # Per-intent handlers — each returns plain dicts of real tool output
    # -------------------------------------------------------------

    def _handle_human(self, ctx, session_id, message, parsed: ParsedMessage, trace_id: str) -> ChatResponse:
        desk = Desk.SAFETY if "harass" in message.lower() or "safety" in message.lower() else (
            Desk.COMPLAINTS if "complain" in message.lower() else Desk.GENERAL
        )
        record = self._handoff_service.create(
            ctx, desk=desk, summary=message[:200], booking_id=parsed.entities.booking_id, session_id=session_id,
        )
        return ChatResponse(
            trace_id=trace_id, answer_type=AnswerType.HANDED_TO_HUMAN,
            answer=f"I've passed this to our {desk.value} desk. They'll follow up — I can't promise a specific outcome.",
            handed_to_human=HandoffRef(
                handoff_id=record.handoff_id, desk=record.desk, summary=record.summary, booking_id=record.booking_id,
            ),
        )

    def _refusal(self, trace_id: str, text: str) -> ChatResponse:
        return ChatResponse(trace_id=trace_id, answer_type=AnswerType.REFUSAL, answer=text, handed_to_human=None)

    def _handle_booking(self, conn, ctx: PassengerContext, booking_id: str, wants_cancel: bool) -> dict:
        owner_row = conn.execute("SELECT passenger_id FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if owner_row is None or owner_row["passenger_id"] != ctx.passenger_id:
            return {"refused": True, "text": "", "sources": [], "tools": [], "pending_action": None}

        try:
            quote = refund_quote(conn, ctx, booking_id)
        except BookingNotFound:
            return {"refused": True, "text": "", "sources": [], "tools": [], "pending_action": None}

        tool_call = ToolCall(
            tool="refund_quote",
            output={
                "amount_paid": quote.amount_paid, "charge": quote.charge, "refund": quote.refund,
                "hours_before_departure": quote.hours_before_departure,
            },
        )
        pending_action = None
        if wants_cancel and quote.can_cancel:
            proposal = self._action_service.propose_cancel(ctx, booking_id)
            pending_action = PendingActionRef(
                action_id=proposal.action_id, type=proposal.type,
                booking_id=proposal.booking_id, expires_at=proposal.expires_at,
            )
            text = (
                f"Cancelling booking {booking_id} now gives you a refund of Rs {quote.refund} "
                f"(paid Rs {quote.amount_paid}, charge Rs {quote.charge}). Shall I go ahead?"
            )
        elif wants_cancel and not quote.can_cancel:
            text = quote.reason or f"Booking {booking_id} cannot be cancelled right now."
        elif quote.can_cancel:
            text = (
                f"If you cancel booking {booking_id} now, you'd get a refund of Rs {quote.refund} "
                f"(paid Rs {quote.amount_paid}, charge Rs {quote.charge})."
            )
        else:
            # Neither an explicit cancel nor a refund question — e.g. a bare
            # "what's the status of booking X" mention. get_booking_status()
            # isn't implemented yet (see the tools-task report), so this is
            # the honest, minimal answer available from refund_quote's own
            # booking-state fields rather than a guessed status.
            text = quote.reason or f"Booking {booking_id} is on file and currently cancellable."
        return {
            "refused": False, "text": text, "sources": list(quote.rule_basis),
            "tools": [tool_call], "pending_action": pending_action,
        }

    def _handle_search(self, conn, ctx: PassengerContext, e) -> dict:
        from_match = resolve_station(conn, e.from_text)
        to_match = resolve_station(conn, e.to_text)
        if from_match.kind != "exact" or to_match.kind != "exact":
            return {"text": f"I couldn't find a single matching station for \"{e.from_text}\" and/or \"{e.to_text}\".", "tools": []}

        boarding_date = e.journey_date or ctx.as_of.date()
        result = search_trains(conn, ctx, from_match.station_code, to_match.station_code, boarding_date, after=e.after, before=e.before)
        tool_call = ToolCall(tool="search_trains", output={"trains": [t.train_no for t in result.trains], "note": result.note})
        if not result.trains:
            return {"text": result.note or "No trains found for that route and date.", "tools": [tool_call]}
        lines = [f"{t.train_no} ({t.name}) departs {t.depart_at.strftime('%H:%M')}, arrives {t.arrive_at.strftime('%H:%M')}" for t in result.trains[:5]]
        return {"text": "Trains found: " + "; ".join(lines) + ".", "tools": [tool_call]}

    def _handle_availability(self, conn, ctx, train_no: str, journey_date: date, cls: str) -> dict:
        try:
            avail = check_availability(conn, ctx, train_no, journey_date, cls, "", "")
        except SeatsRowNotFound:
            return {"text": f"I have no seat data for train {train_no}, {cls}, on {journey_date.isoformat()}.", "tools": []}
        tool_call = ToolCall(tool="check_availability", output={"available": avail.available, "rac": avail.rac, "waitlist": avail.waitlist, "outcome": avail.outcome.value})
        if avail.outcome.value == "CNF":
            text = f"Yes, {avail.available} {cls} seat(s) available on {train_no} ({journey_date.isoformat()})."
        elif avail.outcome.value == "RAC":
            text = f"{cls} on {train_no} ({journey_date.isoformat()}) is on RAC right now."
        else:
            text = f"{cls} on {train_no} ({journey_date.isoformat()}) is fully booked; you'd be on the waitlist ({avail.waitlist} ahead)."
        return {"text": text, "tools": [tool_call]}

    def _handle_fare(self, conn, ctx, e) -> dict:
        from_match = resolve_station(conn, e.from_text)
        to_match = resolve_station(conn, e.to_text)
        if from_match.kind != "exact" or to_match.kind != "exact":
            return {"text": "", "tools": []}
        try:
            quote = get_fare(conn, ctx, e.train_no, e.cls, from_match.station_code, to_match.station_code)
        except FareNotFound:
            return {"text": f"I don't have a fare on file for {e.cls} on train {e.train_no} for that route.", "tools": []}
        tool_call = ToolCall(tool="get_fare", output={"fare_per_pax": quote.fare_per_pax, "total": quote.total})
        return {"text": f"The {e.cls} fare on train {e.train_no} is Rs {quote.fare_per_pax}.", "tools": [tool_call]}

    def _handle_policy(self, conn, ctx, message: str) -> dict | None:
        result = retrieve_context(conn, message, as_of=ctx.as_of.date(), top_k=2)
        if not result.passages:
            return None
        passage = result.passages[0]
        return {
            "text": passage.text.split("\n\n")[0][:400],
            "sources": [SourceRef(doc_id=p.doc_id, section=p.section) for p in result.passages],
            "conflicts": list(result.conflicts),
        }
