"""get_fare ("calculate_fare") — deterministic, SQLite-backed
(api-contracts §6; RUL-CLS-01 §3: "Ujjwal Rail does not use dynamic
pricing... the assistant never computes a fare itself; it always
reads it from this table").

This tool never computes a fare from distance, class or any formula —
it only ever returns a value that is actually stored in `fares`.
[Backend]
"""
from __future__ import annotations

import sqlite3

from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import FareQuote


class FareNotFound(Exception):
    """No row in `fares` for this exact (train_no, class, from_code,
    to_code). The caller must surface this as not_found — never fall
    back to a guessed or derived number (RUL-CLS-01 §3)."""


def get_fare(
    conn: sqlite3.Connection,
    ctx: PassengerContext,
    train_no: str,
    cls: str,
    from_code: str,
    to_code: str,
    pax: int = 1,
) -> FareQuote:
    row = conn.execute(
        "SELECT fare FROM fares WHERE train_no = ? AND class = ? AND from_code = ? AND to_code = ?",
        (train_no, cls, from_code, to_code),
    ).fetchone()
    if row is None:
        raise FareNotFound(
            f"no fare on file for train {train_no}, class {cls}, {from_code}->{to_code}"
        )

    fare_per_pax = row["fare"]
    return FareQuote(
        train_no=train_no,
        cls=cls,
        from_code=from_code,
        to_code=to_code,
        fare_per_pax=fare_per_pax,
        pax=pax,
        total=fare_per_pax * pax,
    )
