"""search_trains — deterministic, SQLite-backed train search
(api-contracts §6, R4: "let code do the exact work").

Reads `trains` + `train_stops` only. Never invents a train, a time, or
a running day — every TrainSearchItem returned corresponds to a real
train that genuinely runs on the requested boarding date. [Backend]
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta, timezone

from app.contracts.interfaces import PassengerContext
from app.contracts.schemas import TrainSearchItem, TrainSearchResult

TZ = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata (api-contracts §2)
_DAY_INDEX = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


def _hhmm_to_time(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def _combine(d: date, t: time) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=TZ)


def _runs_on_origin_date(runs_on: str, origin_date: date) -> bool:
    if runs_on == "DAILY":
        return True
    allowed = {_DAY_INDEX[token] for token in runs_on.split(",")}
    return origin_date.weekday() in allowed


def search_trains(
    conn: sqlite3.Connection,
    ctx: PassengerContext,
    from_code: str,
    to_code: str,
    boarding_date: date,
    after: time | None = None,
    before: time | None = None,
    cls: str | None = None,
) -> TrainSearchResult:
    """`boarding_date` is the calendar date the passenger boards at
    `from_code` (not necessarily the train's origin date — an
    after-midnight train boarded at a later stop has day_offset > 0 at
    that stop, so its ORIGIN departure date is `boarding_date` minus
    that stop's day_offset; the running-day check below uses that
    origin date, per `train_stops.day_offset`'s own definition).
    """
    rows = conn.execute(
        """
        SELECT
            t.train_no, t.name, t.runs_on, t.classes,
            s_from.stop_order AS from_order, s_from.departure AS from_departure,
            s_from.day_offset AS from_day_offset,
            s_to.stop_order AS to_order, s_to.arrival AS to_arrival,
            s_to.day_offset AS to_day_offset
        FROM trains t
        JOIN train_stops s_from ON s_from.train_no = t.train_no AND s_from.station_code = ?
        JOIN train_stops s_to ON s_to.train_no = t.train_no AND s_to.station_code = ?
        WHERE s_from.stop_order < s_to.stop_order
          AND s_from.departure IS NOT NULL
          AND s_to.arrival IS NOT NULL
        """,
        (from_code, to_code),
    ).fetchall()

    trains: list[TrainSearchItem] = []
    for row in rows:
        if cls is not None and cls not in row["classes"].split(","):
            continue

        origin_date = boarding_date - timedelta(days=row["from_day_offset"])
        if not _runs_on_origin_date(row["runs_on"], origin_date):
            continue

        depart_at = _combine(boarding_date, _hhmm_to_time(row["from_departure"]))
        if after is not None and depart_at.time() <= after:
            continue
        if before is not None and depart_at.time() >= before:
            continue

        arrive_date = boarding_date + timedelta(days=row["to_day_offset"] - row["from_day_offset"])
        arrive_at = _combine(arrive_date, _hhmm_to_time(row["to_arrival"]))

        trains.append(
            TrainSearchItem(
                train_no=row["train_no"],
                name=row["name"],
                from_code=from_code,
                to_code=to_code,
                depart_at=depart_at,
                arrive_at=arrive_at,
                duration_min=int((arrive_at - depart_at).total_seconds() // 60),
                classes=row["classes"].split(","),
                runs_on_date=True,  # only running trains are ever included above
            )
        )

    trains.sort(key=lambda t: t.depart_at)
    note = None if trains else f"No train found from {from_code} to {to_code} on {boarding_date.isoformat()}."
    return TrainSearchResult(trains=trains, note=note)
