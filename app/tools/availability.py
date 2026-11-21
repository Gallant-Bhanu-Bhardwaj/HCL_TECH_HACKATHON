"""check_availability — deterministic, SQLite-backed (api-contracts §6).

`TrainSearchItem` (returned by search_trains) carries no seat-count
field — it is a SHARED-FROZEN shape (architecture §8) and that's not
part of it. Seat/availability info is this separate, per-(train,date,
class) lookup against the `seats` table, exactly as the guide's own
example splits "which trains run" from "is there a seat" into two
questions. [Backend]
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.contracts.enums import BookingOutcome
from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import Availability


class SeatsRowNotFound(Exception):
    """No seats row exists for this (train_no, journey_date, class) —
    i.e. the train doesn't run that date/class combo at all. Never
    guessed; the caller must treat this as not_found, not FULL."""


def check_availability(
    conn: sqlite3.Connection,
    ctx: PassengerContext,
    train_no: str,
    journey_date: date,
    cls: str,
    from_code: str,
    to_code: str,
) -> Availability:
    row = conn.execute(
        "SELECT available, rac, waitlist, rac_capacity FROM seats "
        "WHERE train_no = ? AND journey_date = ? AND class = ?",
        (train_no, journey_date.isoformat(), cls),
    ).fetchone()
    if row is None:
        raise SeatsRowNotFound(f"no seats row for {train_no}/{journey_date}/{cls}")

    # architecture.md O4: a new booking is CNF if a seat is free, else
    # RAC if RAC capacity remains, else WL — waitlist has no capacity
    # ceiling, so this never resolves to FULL (BookingOutcome's own
    # docstring: "No other outcome").
    if row["available"] > 0:
        outcome = BookingOutcome.CNF
    elif row["rac"] < row["rac_capacity"]:
        outcome = BookingOutcome.RAC
    else:
        outcome = BookingOutcome.WL

    return Availability(
        train_no=train_no,
        journey_date=journey_date,
        cls=cls,
        available=row["available"],
        rac=row["rac"],
        waitlist=row["waitlist"],
        outcome=outcome,
    )
