"""Canned, contract-valid FakeToolRegistry — no business logic (T3).

Returns fixed example data shaped exactly like docs/api-contracts.md §6
so Phase 0 stub routes, and other modules' early tests, have something
real to call before the Backend's actual tools land.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.contracts.enums import BookingOutcome, BookingStatus, TravellerStatus
from app.contracts.interfaces import NotAccessible, PassengerContext, SettingValue
from app.contracts.schemas import (
    Availability,
    BoardingInfo,
    BookingSummary,
    BookingView,
    CancelEligibility,
    FareQuote,
    PerTravellerRefund,
    RefundQuote,
    SourceRef,
    StationMatch,
    TrainSearchItem,
    TrainSearchResult,
    TravellerView,
)

_SAMPLE_BOOKING_ID = "UR-30418"
_FOREIGN_BOOKING_ID = "UR-99999"  # belongs to someone else in this fake


class FakeToolRegistry:
    def resolve_station(self, text: str) -> StationMatch:
        if text.strip().upper() in {"PUNE", "PUNE JN"}:
            return StationMatch(kind="exact", station_code="PUNE")
        return StationMatch(kind="none")

    def search_trains(
        self, ctx: PassengerContext, from_code, to_code, date, after=None,
        before=None, cls=None,
    ) -> TrainSearchResult:
        item = TrainSearchItem(
            train_no="12123",
            name="Ujjwal Express",
            from_code=from_code,
            to_code=to_code,
            depart_at=datetime(2026, 12, 5, 18, 40, tzinfo=timezone.utc),
            arrive_at=datetime(2026, 12, 6, 6, 10, tzinfo=timezone.utc),
            duration_min=690,
            classes=["2AC", "3AC", "SL"],
            runs_on_date=True,
        )
        return TrainSearchResult(trains=[item], note=None)

    def check_availability(self, ctx, train_no, journey_date, cls, from_code, to_code) -> Availability:
        return Availability(
            train_no=train_no, journey_date=journey_date, cls=cls,
            available=4, rac=0, waitlist=0, outcome=BookingOutcome.CNF,
        )

    def get_fare(self, ctx, train_no, cls, from_code, to_code, pax=1) -> FareQuote:
        per_pax = 1020
        return FareQuote(
            train_no=train_no, cls=cls, from_code=from_code, to_code=to_code,
            fare_per_pax=per_pax, pax=pax, total=per_pax * pax,
        )

    def list_my_bookings(self, ctx, upcoming_only=True) -> list[BookingSummary]:
        return [
            BookingSummary(
                booking_id=_SAMPLE_BOOKING_ID, train_no="12123",
                journey_date=date(2026, 12, 5), from_code="PUNE", to_code="NGP",
                status=BookingStatus.CONFIRMED,
            )
        ]

    def get_booking_status(self, ctx: PassengerContext, booking_id: str):
        if booking_id != _SAMPLE_BOOKING_ID or ctx.passenger_id != "P007":
            return NotAccessible()  # R8: missing and foreign look identical
        return BookingView(
            booking_id=_SAMPLE_BOOKING_ID,
            passenger_id="P007",
            train_no="12123",
            train_name="Ujjwal Express",
            journey_date=date(2026, 12, 5),
            from_code="PUNE",
            to_code="NGP",
            class_="2AC",
            boarding=BoardingInfo(
                station_code="PUNE", departure=datetime(2026, 12, 5, 18, 40, tzinfo=timezone.utc)
            ),
            amount_paid=2040,
            status=BookingStatus.CONFIRMED,
            booked_at=datetime(2026, 11, 20, 11, 2, tzinfo=timezone.utc),
            travellers=[
                TravellerView(traveller_name="A. Sharma", age=34, status=TravellerStatus.CNF, coach="B2", berth="21")
            ],
        )

    def refund_quote(self, ctx, booking_id: str) -> RefundQuote:
        return RefundQuote(
            booking_id=booking_id,
            amount_paid=2040,
            charge=200,
            refund=1840,
            hours_before_departure=51.0,
            departure_at=datetime(2026, 12, 5, 18, 40, tzinfo=timezone.utc),
            rule_basis=[SourceRef(doc_id="RUL-CAN-01", section="3. Refund table")],
            per_traveller=[
                PerTravellerRefund(traveller_name="A. Sharma", status=TravellerStatus.CNF, refund=1840, charge=200)
            ],
            booking_status_effect="normal",
            can_cancel=True,
        )

    def can_cancel(self, ctx, booking_id: str) -> CancelEligibility:
        return CancelEligibility(can_cancel=True, hours_before_departure=51.0)

    def get_setting(self, name: str, as_of: datetime) -> SettingValue:
        return SettingValue(name=name, value=200, effective_from=as_of, source_doc="RUL-CAN-01")
