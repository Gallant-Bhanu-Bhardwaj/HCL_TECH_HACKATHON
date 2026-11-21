"""Station resolution — deterministic, SQLite-backed (api-contracts §6).

No LLM, no fuzzy guessing beyond a conservative substring fallback: a
station is only ever returned if it is a real row in `stations`.
[Backend]
"""
from __future__ import annotations

import sqlite3

from app.contracts.schemas import StationMatch


def resolve_station(conn: sqlite3.Connection, text: str) -> StationMatch:
    """Resolve free text (a station code, name, or alias) to a real
    `stations.station_code`.

    Two tiers, both exact-match before ever falling back to substring:
      1. Exact match (case-insensitive) on station_code, name, or one of
         the `|`-separated `other_names` aliases.
      2. Only if tier 1 finds nothing: a case-insensitive substring
         match against name/alias/city, so "Hyderabad" can still find
         "Hyderabad Deccan" without ever inventing a station that
         isn't a real row.

    Ambiguous (>1 distinct station_code matches) -> kind="ambiguous"
    with every candidate listed; no match at all -> kind="none".
    """
    needle = text.strip()
    if not needle:
        return StationMatch(kind="none")
    needle_upper = needle.upper()

    rows = conn.execute("SELECT station_code, name, other_names, city FROM stations").fetchall()

    exact: set[str] = set()
    for row in rows:
        aliases = [a.strip().upper() for a in (row["other_names"] or "").split("|") if a.strip()]
        if (
            row["station_code"].upper() == needle_upper
            or row["name"].upper() == needle_upper
            or needle_upper in aliases
        ):
            exact.add(row["station_code"])

    if len(exact) == 1:
        return StationMatch(kind="exact", station_code=next(iter(exact)))
    if len(exact) > 1:
        return StationMatch(kind="ambiguous", candidates=sorted(exact))

    substring: set[str] = set()
    for row in rows:
        haystacks = [row["name"], row["city"]] + (row["other_names"] or "").split("|")
        if any(needle_upper in h.upper() for h in haystacks if h and h.strip()):
            substring.add(row["station_code"])

    if len(substring) == 1:
        return StationMatch(kind="exact", station_code=next(iter(substring)))
    if len(substring) > 1:
        return StationMatch(kind="ambiguous", candidates=sorted(substring))
    return StationMatch(kind="none")
