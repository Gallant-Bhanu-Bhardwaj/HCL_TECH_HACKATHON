"""Canned FakeActionService — implements the propose/confirm/cancel state
machine (api-contracts §4.2, §9) with in-memory state so Phase 0 stub
routes can demonstrate idempotency, expiry and ownership checks without
any real booking/refund logic (T3: no business logic — the refund/fare
numbers below are fixed, not computed).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.actions.errors import ActionConflict, ActionExpired, ActionNotAccessible
from app.contracts.enums import ActionStatus, ActionType
from app.contracts.interfaces import Clock, PassengerContext
from app.contracts.schemas import (
    ActionRef,
    BookingSpec,
    ConfirmResult,
    PendingAction,
    Refusal,
    Verification,
)

_ACTION_EXPIRY_MINUTES = 15  # placeholder; real value comes from settings in Phase 1


@dataclass
class _ActionRow:
    action_id: str
    passenger_id: str
    type: ActionType
    booking_id: str | None
    status: ActionStatus
    as_of: datetime  # business clock, saved at proposal (D6)
    expires_at: datetime  # operational clock, saved at proposal (D6)
    preview: dict
    result: ConfirmResult | None = None


class FakeActionService:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._actions: dict[str, _ActionRow] = {}
        self._seq = 0

    def _new_id(self) -> str:
        self._seq += 1
        return f"ACT-{self._seq:04d}"

    def propose_cancel(self, ctx: PassengerContext, booking_id: str) -> PendingAction | Refusal:
        action_id = self._new_id()
        expires_at = self._clock.now_utc() + timedelta(minutes=_ACTION_EXPIRY_MINUTES)
        preview = {"amount_paid": 2040, "charge": 200, "refund": 1840}
        self._actions[action_id] = _ActionRow(
            action_id=action_id, passenger_id=ctx.passenger_id, type=ActionType.CANCEL_BOOKING,
            booking_id=booking_id, status=ActionStatus.PROPOSED, as_of=ctx.as_of,
            expires_at=expires_at, preview=preview,
        )
        return PendingAction(
            action_id=action_id, type=ActionType.CANCEL_BOOKING, booking_id=booking_id,
            expires_at=expires_at, preview=preview, as_of=ctx.as_of,
        )

    def propose_booking(self, ctx: PassengerContext, spec: BookingSpec) -> PendingAction | Refusal:
        action_id = self._new_id()
        expires_at = self._clock.now_utc() + timedelta(minutes=_ACTION_EXPIRY_MINUTES)
        preview = {"fare_total": 1020 * len(spec.travellers)}
        self._actions[action_id] = _ActionRow(
            action_id=action_id, passenger_id=ctx.passenger_id, type=ActionType.BOOK_TICKET,
            booking_id=None, status=ActionStatus.PROPOSED, as_of=ctx.as_of,
            expires_at=expires_at, preview=preview,
        )
        return PendingAction(
            action_id=action_id, type=ActionType.BOOK_TICKET, booking_id=None,
            expires_at=expires_at, preview=preview, as_of=ctx.as_of,
        )

    def propose_boarding_change(
        self, ctx: PassengerContext, booking_id: str, new_boarding_code: str
    ) -> PendingAction | Refusal:
        action_id = self._new_id()
        expires_at = self._clock.now_utc() + timedelta(minutes=_ACTION_EXPIRY_MINUTES)
        preview = {"new_boarding_code": new_boarding_code}
        self._actions[action_id] = _ActionRow(
            action_id=action_id, passenger_id=ctx.passenger_id,
            type=ActionType.CHANGE_BOARDING_STATION, booking_id=booking_id,
            status=ActionStatus.PROPOSED, as_of=ctx.as_of, expires_at=expires_at, preview=preview,
        )
        return PendingAction(
            action_id=action_id, type=ActionType.CHANGE_BOARDING_STATION, booking_id=booking_id,
            expires_at=expires_at, preview=preview, as_of=ctx.as_of,
        )

    def _lookup_owned(self, ctx: PassengerContext, action_id: str) -> _ActionRow:
        row = self._actions.get(action_id)
        if row is None or row.passenger_id != ctx.passenger_id:
            raise ActionNotAccessible(action_id)  # R8: identical for missing/foreign
        return row

    def confirm(self, ctx: PassengerContext, action_id: str) -> ConfirmResult:
        row = self._lookup_owned(ctx, action_id)

        if row.status == ActionStatus.CANCELLED:
            raise ActionConflict(action_id)

        if row.status == ActionStatus.DONE:
            assert row.result is not None
            return ConfirmResult(
                action=row.result.action, verification=row.result.verification,
                idempotent_replay=True,
            )

        # D6: expiry uses ONLY the operational clock against the stored
        # expires_at timestamp — as_of is never consulted here.
        if self._clock.now_utc() >= row.expires_at:
            row.status = ActionStatus.EXPIRED
            raise ActionExpired(action_id)

        # Atomic (single-threaded fake) proposed -> executing -> done.
        row.status = ActionStatus.EXECUTING
        # Business-clock recompute would happen here in the real
        # implementation, evaluated against settings as of row.as_of.
        row.status = ActionStatus.DONE
        result = ConfirmResult(
            action=ActionRef(action_id=action_id, type=row.type, status=ActionStatus.DONE, booking_id=row.booking_id),
            verification=Verification(checked=True, booking_status="cancelled", refund=1840, matches_preview=True),
            idempotent_replay=False,
        )
        row.result = result
        return result

    def cancel(self, ctx: PassengerContext, action_id: str) -> ConfirmResult:
        row = self._lookup_owned(ctx, action_id)

        if row.status == ActionStatus.DONE:
            raise ActionConflict(action_id)

        if row.status == ActionStatus.CANCELLED:
            return ConfirmResult(
                action=ActionRef(action_id=action_id, type=row.type, status=ActionStatus.CANCELLED, booking_id=row.booking_id),
                verification=Verification(checked=False),
                idempotent_replay=True,
            )

        row.status = ActionStatus.CANCELLED
        return ConfirmResult(
            action=ActionRef(action_id=action_id, type=row.type, status=ActionStatus.CANCELLED, booking_id=row.booking_id),
            verification=Verification(checked=False),
            idempotent_replay=False,
        )
