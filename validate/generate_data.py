#!/usr/bin/env python3
"""Deterministic Ujjwal Rail synthetic data generator.

Master data-generation prompt, Phase 4/7. Produces one output file,
`db/seed_data.sql` — plain INSERT statements, loadable on top of
`db/schema.sql` into any fresh SQLite database (the real .db file
itself stays gitignored; this .sql text is what gets committed).

Reproducible: a fixed `--seed` and `--base-date` always produce
byte-identical output (hop durations use a seeded RNG; which trains,
stations, classes and edge cases exist is explicit, not randomised).

Run from the repo root:
    python3 data/generator/generate_data.py
    python3 data/validate/validate_data.py        # then validate

No external dependencies (stdlib only) — keeps this lightweight on a
MacBook Air M4 (architecture.md §10).
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import policy_values as pv  # noqa: E402

DOCS_ROOT = REPO_ROOT / "data" / "documents"
DEFAULT_OUT = REPO_ROOT / "db" / "seed_data.sql"

TZ_SUFFIX = "+05:30"  # Asia/Kolkata (api-contracts.md §2) — stored as plain ISO text, no sqlite datetime math


# ---------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------


def sql(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


class SqlWriter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def comment(self, text: str) -> None:
        self.lines.append(f"-- {text}")

    def insert(self, table: str, columns: list[str], rows: list[tuple]) -> None:
        if not rows:
            return
        col_list = ", ".join(columns)
        for row in rows:
            assert len(row) == len(columns), f"{table}: column/value count mismatch"
            values = ", ".join(sql(v) for v in row)
            self.lines.append(f"INSERT INTO {table} ({col_list}) VALUES ({values});")

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def iso_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def iso_dt(d: date, minutes_of_day: int) -> str:
    """ISO datetime for `d` at `minutes_of_day` minutes past that day's
    midnight (may exceed 1439 only if called with day already adjusted
    by the caller — callers always pass 0 <= minutes_of_day < 1440)."""
    hh, mm = divmod(minutes_of_day, 60)
    return f"{d.strftime('%Y-%m-%d')}T{hh:02d}:{mm:02d}:00{TZ_SUFFIX}"


def hhmm(minutes_of_day: int) -> str:
    hh, mm = divmod(minutes_of_day % 1440, 60)
    return f"{hh:02d}:{mm:02d}"


# ---------------------------------------------------------------------
# Phase 4 — Stations (>= 15; includes two similar-name pairs, edge case #6)
# ---------------------------------------------------------------------

# (station_code, name, other_names, city)
STATIONS: list[tuple[str, str, str, str]] = [
    ("PUNE", "Pune Junction", "Pune|Poona", "Pune"),
    ("CSMT", "Mumbai CSMT", "Bombay|CST|Mumbai Chhatrapati Shivaji", "Mumbai"),
    ("NDLS", "New Delhi", "Delhi|New Delhi Railway Station", "Delhi"),
    ("DLI", "Old Delhi", "Delhi Jn|Old Delhi Railway Station", "Delhi"),
    ("NGP", "Nagpur Junction", "Nagpur", "Nagpur"),
    ("BZA", "Vijayawada Junction", "Bezwada", "Vijayawada"),
    ("HYB", "Hyderabad Deccan", "Hyderabad", "Hyderabad"),
    ("SC", "Secunderabad Junction", "Secunderabad", "Hyderabad"),
    ("BLR", "Bengaluru City", "Bangalore|Bangalore City", "Bengaluru"),
    ("MAS", "Chennai Central", "Madras", "Chennai"),
    ("HWH", "Howrah Junction", "Calcutta|Kolkata Howrah", "Kolkata"),
    ("KOAA", "Kolkata", "Calcutta", "Kolkata"),
    ("ADI", "Ahmedabad Junction", "Amdavad", "Ahmedabad"),
    ("JP", "Jaipur Junction", "Jeypore|Jaipur", "Jaipur"),
    ("LKO", "Lucknow Charbagh", "Lucknow", "Lucknow"),
    ("PNBE", "Patna Junction", "Patna", "Patna"),
    ("BPL", "Bhopal Junction", "Bhopal", "Bhopal"),
]
STATION_CODES = [s[0] for s in STATIONS]

# ---------------------------------------------------------------------
# Phase 4 — Trains, stops (>= 25 trains; incl. an after-midnight departure,
# edge case #3)
# ---------------------------------------------------------------------


@dataclass
class TrainSpec:
    train_no: str
    name: str
    route: list[str]              # station codes, origin -> terminus
    classes: list[str]
    runs_on: str                  # "DAILY" or comma days, e.g. "MON,WED,FRI"
    origin_depart_minutes: int    # minutes past midnight of day_offset 0
    hop_minutes: list[int] | None = None  # explicit, else RNG-filled
    halt_minutes: int = 8


ALL_DAYS = "MON,TUE,WED,THU,FRI,SAT,SUN"

# Two trains are pinned with EXACT timings so they match the worked
# examples already published in docs/api-contracts.md and the Phase 0
# stub fakes (tests/fakes/tool_registry.py, orchestrator.py) byte for
# byte: train 12123, Pune -> Nagpur, depart 18:40, arrive 06:10 next
# day (690 minutes), fare paid 2040 for a single 2AC traveller.
PINNED_TRAINS: list[TrainSpec] = [
    TrainSpec(
        train_no="12123", name="Ujjwal Express", route=["PUNE", "BPL", "NGP"],
        classes=["SL", "3AC", "2AC"], runs_on="DAILY",
        origin_depart_minutes=18 * 60 + 40,
        hop_minutes=[300, 390],  # PUNE->BPL 300min, BPL->NGP 390min = 690min total, halt 0 at BPL for exact arithmetic
        halt_minutes=0,
    ),
    TrainSpec(
        # Guide's explicit awkward case: "a train that leaves after
        # midnight (so 'tomorrow's train' is ambiguous)".
        train_no="22002", name="Deccan Mail", route=["CSMT", "PUNE"],
        classes=["SL", "3AC", "CC"], runs_on="DAILY",
        origin_depart_minutes=0 * 60 + 40,  # 00:40 — just after midnight at the ORIGIN
        hop_minutes=[200],
        halt_minutes=0,
    ),
]

# Corridor templates reused (forwards/reversed, varied timing) to reach
# >= 25 trains in total without hand-writing every stop.
CORRIDORS: list[list[str]] = [
    ["CSMT", "PUNE", "SC", "BZA", "MAS"],
    ["NDLS", "JP", "ADI"],
    ["HWH", "KOAA", "PNBE", "LKO", "NDLS"],
    ["BLR", "HYB", "SC", "BPL", "ADI"],
    ["MAS", "BZA", "SC", "HYB", "BPL", "LKO", "PNBE"],
    ["NGP", "BPL", "JP", "NDLS"],
    ["DLI", "JP", "ADI", "CSMT"],
    ["PNBE", "LKO", "NDLS", "JP"],
]

TRAIN_NAME_WORDS = [
    "Express", "Mail", "Superfast", "Intercity", "Jan Shatabdi", "Garib Rath",
    "Duronto", "Sampark Kranti", "Sanchar Kranti", "Humsafar",
]


def _generate_more_trains(rng: random.Random, count: int) -> list[TrainSpec]:
    specs: list[TrainSpec] = []
    class_pools = [
        ["SL", "3AC", "2AC"],
        ["SL", "3AC", "2AC", "1AC"],
        ["CC", "EC"],
        ["SL", "3AC"],
        ["CC", "2S"],
    ]
    day_patterns = [
        "DAILY", "MON,WED,FRI", "TUE,THU,SAT,SUN", "MON,TUE,WED,THU,FRI",
        "SAT,SUN", "WED,SAT",
    ]
    n = 0
    corridor_i = 0
    while n < count:
        base_route = CORRIDORS[corridor_i % len(CORRIDORS)]
        route = base_route if n % 2 == 0 else list(reversed(base_route))
        train_no = str(20005 + n * 2)  # well clear of the 2 pinned numbers (12123, 22002)
        name = f"{route[-1]}-bound {rng.choice(TRAIN_NAME_WORDS)}"
        classes = class_pools[n % len(class_pools)]
        runs_on = day_patterns[n % len(day_patterns)]
        origin_depart = rng.choice([5 * 60 + 30, 7 * 60 + 15, 11 * 60, 14 * 60 + 20, 20 * 60 + 10, 22 * 60 + 45])
        specs.append(TrainSpec(
            train_no=train_no, name=name, route=route, classes=classes,
            runs_on=runs_on, origin_depart_minutes=origin_depart,
        ))
        n += 1
        corridor_i += 1
    return specs


def build_stops(spec: TrainSpec, rng: random.Random) -> list[dict]:
    """Returns stop dicts with arrival/departure HH:MM strings (or None
    at the origin/terminus) and day_offset, honouring explicit
    hop_minutes when the spec pins them (the two anchor trains)."""
    stops: list[dict] = []
    cur = spec.origin_depart_minutes
    for i, code in enumerate(spec.route):
        if i == 0:
            stops.append({
                "station_code": code, "stop_order": i + 1, "arrival": None,
                "departure": hhmm(cur), "day_offset": cur // 1440,
            })
            continue
        if spec.hop_minutes is not None:
            hop = spec.hop_minutes[i - 1]
        else:
            hop = rng.randint(70, 260)
        cur += hop
        is_last = i == len(spec.route) - 1
        if is_last:
            stops.append({
                "station_code": code, "stop_order": i + 1,
                "arrival": hhmm(cur), "departure": None, "day_offset": cur // 1440,
            })
        else:
            dep = cur + spec.halt_minutes
            stops.append({
                "station_code": code, "stop_order": i + 1,
                "arrival": hhmm(cur), "departure": hhmm(dep), "day_offset": cur // 1440,
            })
            cur = dep
    return stops


def total_duration_minutes(stops: list[dict]) -> int:
    first_departure_total = stops[0]["day_offset"] * 1440 + _minutes(stops[0]["departure"])
    last = stops[-1]
    last_arrival_total = last["day_offset"] * 1440 + _minutes(last["arrival"])
    return last_arrival_total - first_departure_total


def _minutes(hhmm_str: str) -> int:
    h, m = hhmm_str.split(":")
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------------
# Phase 4 — Fares (deterministic function of hop distance-proxy & class)
# ---------------------------------------------------------------------

CLASS_FARE_PER_MIN = {
    "2S": 0.35, "SL": 0.55, "CC": 0.75, "3AC": 1.35, "EC": 1.55, "2AC": 1.95, "1AC": 3.10,
}


def fare_for(minutes_between: int, cls: str) -> int:
    raw = minutes_between * CLASS_FARE_PER_MIN[cls]
    return max(50, int(round(raw / 5.0)) * 5)  # round to nearest Rs 5, floor Rs 50


# ---------------------------------------------------------------------
# Phase 4 — Passengers, bookings
# ---------------------------------------------------------------------

FIRST_NAMES = [
    "Aditi", "Rohan", "Priya", "Vikram", "Sneha", "Arjun", "Kavya", "Rahul",
    "Meera", "Karan", "Divya", "Siddharth", "Pooja", "Anil", "Nisha", "Varun",
    "Shreya", "Manish", "Lata", "Suresh", "Ayesha", "Tarun", "Radhika", "Gautam",
    "Fatima",
]
LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Khan", "Nair", "Gupta", "Reddy", "Patel",
    "Chatterjee", "Joshi", "Das", "Kapoor", "Menon", "Rao", "Singh", "Bose",
    "Pillai", "Agarwal", "Mukherjee", "Desai",
]
LANGS = ["en", "hi", "hinglish"]


def gen_passengers(rng: random.Random, n: int) -> list[dict]:
    passengers = []
    for i in range(1, n + 1):
        pid = f"P{i:03d}"
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        phone_last4 = f"{rng.randint(0, 9999):04d}"
        lang = LANGS[i % len(LANGS)]
        passengers.append({"passenger_id": pid, "name": name, "phone_last4": phone_last4, "preferred_language": lang})
    # Pinned: P007 is "A. Sharma", matching the Phase 0 stub fakes exactly.
    passengers[6] = {"passenger_id": "P007", "name": "A. Sharma", "phone_last4": "4821", "preferred_language": "en"}
    return passengers


# ---------------------------------------------------------------------
# Markdown document parsing (so documents/chunks get seeded too)
# ---------------------------------------------------------------------

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        raise ValueError("document missing --- front matter ---")
    raw, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in raw.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
        elif value == "":
            meta[key] = None
        else:
            meta[key] = value
    return meta, body


def split_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading, current_lines = None, []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return sections


def load_all_documents() -> list[dict]:
    docs = []
    for subdir in ("rules", "circulars", "faqs"):
        for path in sorted((DOCS_ROOT / subdir).glob("*.md")):
            meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
            sections = split_sections(body)
            docs.append({"meta": meta, "sections": sections, "path": path})
    return docs


# ---------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--base-date", type=str, default=iso_date(pv.BASE_DATE))
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--skip-docs", action="store_true", help="skip documents/chunks rows")
    args = parser.parse_args()

    base_date = datetime.strptime(args.base_date, "%Y-%m-%d").date()
    rng = random.Random(args.seed)
    w = SqlWriter()
    w.comment("Ujjwal Rail synthetic data — GENERATED FILE, do not hand-edit.")
    w.comment(f"Generated by data/generator/generate_data.py --seed {args.seed} --base-date {args.base_date}")
    w.comment("Load after db/schema.sql. See docs/data-generation-report.md for counts.")

    # --- stations ---
    w.comment("stations")
    w.insert("stations", ["station_code", "name", "other_names", "city"], STATIONS)

    # --- trains + train_stops ---
    more = _generate_more_trains(rng, 23)  # 2 pinned + 23 generated = 25
    all_specs = PINNED_TRAINS + more
    assert len(all_specs) >= 25, len(all_specs)

    trains_rows = []
    stops_rows = []
    fares_rows = []
    train_meta: dict[str, dict] = {}

    for spec in all_specs:
        stops = build_stops(spec, rng)
        duration = total_duration_minutes(stops)
        trains_rows.append((spec.train_no, spec.name, spec.runs_on, ",".join(spec.classes)))
        for s in stops:
            stops_rows.append((
                spec.train_no, s["station_code"], s["stop_order"],
                s["arrival"], s["departure"], s["day_offset"],
            ))
        # Fares for every (from, to) pair along the route, both directions of travel,
        # for every class the train offers (so any boarding-station change within
        # the route still resolves a real fare — RUL-BRD-01).
        cum_minutes = [0]
        total = 0
        for i in range(1, len(stops)):
            prev_dep = stops[i - 1]["departure"] if stops[i - 1]["departure"] else stops[i - 1]["arrival"]
            this_arr = stops[i]["arrival"] if stops[i]["arrival"] else stops[i]["departure"]
            prev_total = stops[i - 1]["day_offset"] * 1440 + _minutes(prev_dep)
            this_total = stops[i]["day_offset"] * 1440 + _minutes(this_arr)
            total = this_total - (stops[0]["day_offset"] * 1440 + _minutes(stops[0]["departure"]))
            cum_minutes.append(total)
        for i in range(len(stops)):
            for j in range(i + 1, len(stops)):
                minutes_between = cum_minutes[j] - cum_minutes[i]
                for cls in spec.classes:
                    fare = fare_for(minutes_between, cls)
                    # Pin the PUNE->NGP 2AC fare to match the already-published
                    # worked examples exactly (amount_paid 2040 for 1 traveller).
                    if spec.train_no == "12123" and stops[i]["station_code"] == "PUNE" and stops[j]["station_code"] == "NGP" and cls == "2AC":
                        fare = 2040
                    fares_rows.append((spec.train_no, cls, stops[i]["station_code"], stops[j]["station_code"], fare))
        train_meta[spec.train_no] = {"stops": stops, "classes": spec.classes, "name": spec.name, "runs_on": spec.runs_on}

    w.comment("trains")
    w.insert("trains", ["train_no", "name", "runs_on", "classes"], trains_rows)
    w.comment("train_stops")
    w.insert("train_stops", ["train_no", "station_code", "stop_order", "arrival", "departure", "day_offset"], stops_rows)
    w.comment("fares")
    w.insert("fares", ["train_no", "class", "from_code", "to_code", "fare"], fares_rows)

    # --- seats, for SEAT_HORIZON_DAYS from base_date, every train/class ---
    w.comment("seats")
    seats_rows = []
    seat_dates = [base_date + timedelta(days=d) for d in range(pv.SEAT_HORIZON_DAYS)]
    # Capacities are deliberately small (lightweight dataset, architecture
    # §10) — large enough that filler bookings essentially never collide
    # with each other across ~1000 (train, date, class) combinations, but
    # small enough that the hand-picked edge-case combos below only need
    # a handful of bookings each to demonstrate "fully booked"/RAC/WL.
    CAPACITY_BY_CLASS = {"1AC": 6, "2AC": 10, "3AC": 14, "SL": 18, "CC": 16, "EC": 10, "2S": 20}
    for train_no, meta in train_meta.items():
        for d in seat_dates:
            for cls in meta["classes"]:
                capacity = CAPACITY_BY_CLASS[cls]
                rac_capacity = max(2, capacity // 5)
                # Deterministic pseudo-random fill level per (train,date,class).
                fill_roll = rng.random()
                if fill_roll < 0.55:
                    available, rac, waitlist = rng.randint(1, capacity), 0, 0
                elif fill_roll < 0.75:
                    available, rac, waitlist = 0, rng.randint(1, rac_capacity), 0
                elif fill_roll < 0.92:
                    available, rac, waitlist = 0, rac_capacity, rng.randint(1, 15)
                else:
                    available, rac, waitlist = 0, rac_capacity, 0  # fully booked, no waitlist
                seats_rows.append((train_no, iso_date(d), cls, available, rac, waitlist, capacity, rac_capacity))
    # Pinned edge cases (override whatever the roll produced), so these are
    # ALWAYS present regardless of seed:
    def set_seat(rows, train_no, d, cls, available, rac, waitlist, capacity, rac_capacity):
        for idx, r in enumerate(rows):
            if r[0] == train_no and r[1] == iso_date(d) and r[2] == cls:
                rows[idx] = (train_no, iso_date(d), cls, available, rac, waitlist, capacity, rac_capacity)
                return
        rows.append((train_no, iso_date(d), cls, available, rac, waitlist, capacity, rac_capacity))

    # These numbers are reconciled BY HAND against the exact bookings
    # edge_cases.build_bookings_and_edge_cases() creates on the same
    # (train, date, class) combos — see that module for the booking IDs.
    edge_journey_date = base_date + timedelta(days=2)  # 2026-12-05 when base_date=2026-12-03
    set_seat(seats_rows, "12123", edge_journey_date, "2AC", 9, 0, 0, 10, 2)   # UR-30418 (anchor) takes 1 of 10
    set_seat(seats_rows, "12123", edge_journey_date, "SL", 17, 0, 1, 18, 3)   # mixed CNF+WL booking: 1 CNF, 1 WL
    set_seat(seats_rows, "12123", edge_journey_date, "3AC", 0, 1, 2, 3, 1)    # fully booked (3/3 CNF), RAC full, 2 on waitlist
    set_seat(seats_rows, "22002", base_date + timedelta(days=1), "CC", 15, 0, 0, 16, 3)  # after-midnight train, 1 of 16 taken
    w.insert("seats", ["train_no", "journey_date", "class", "available", "rac", "waitlist", "capacity", "rac_capacity"], seats_rows)

    # --- passengers (>= 25) ---
    passengers = gen_passengers(rng, 26)
    w.comment("passengers")
    w.insert("passengers", ["passenger_id", "name", "phone_last4", "preferred_language"],
             [(p["passenger_id"], p["name"], p["phone_last4"], p["preferred_language"]) for p in passengers])

    # --- bookings + booking_travellers (>= 50 bookings), see edge_cases.py for IDs ---
    from edge_cases import build_bookings_and_edge_cases  # local import after sys.path tweak above

    bookings_rows, travellers_rows, actions_rows, edge_case_ids = build_bookings_and_edge_cases(
        rng=rng, base_date=base_date, passengers=passengers, train_meta=train_meta,
    )
    w.comment("bookings")
    w.insert("bookings", [
        "booking_id", "passenger_id", "train_no", "journey_date", "from_code", "to_code",
        "class", "amount_paid", "status", "booked_at",
    ], bookings_rows)
    w.comment("booking_travellers")
    w.insert("booking_travellers", ["booking_id", "traveller_name", "age", "status", "coach", "berth"], travellers_rows)
    w.comment("actions")
    w.insert("actions", [
        "action_id", "passenger_id", "booking_id", "action_type", "status", "created_at",
        "expires_at", "result", "as_of", "params_json", "preview_json", "trace_id",
    ], actions_rows)

    # --- settings + settings_history ---
    w.comment("settings")
    settings_rows, history_rows = build_settings_rows()
    w.insert("settings", ["name", "value", "source_doc", "effective_from", "effective_to", "unit"], settings_rows)
    w.comment("settings_history")
    w.insert("settings_history", [
        "name", "old_value", "new_value", "effective_from", "source_doc", "changed_at", "trace_id", "changed_by",
    ], history_rows)

    # --- documents + chunks, parsed from data/documents/**/*.md ---
    if not args.skip_docs:
        w.comment("documents + chunks (parsed from data/documents/**/*.md)")
        doc_rows, chunk_rows = build_document_rows()
        w.insert("documents", ["doc_id", "doc_type", "title", "effective_from", "effective_to", "supersedes_json", "language", "status"], doc_rows)
        w.insert("chunks", ["chunk_id", "doc_id", "section", "text", "language"], chunk_rows)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(w.text(), encoding="utf-8")

    print(f"wrote {out_path} ({len(w.lines)} statements)")
    print(f"stations={len(STATIONS)} trains={len(trains_rows)} train_stops={len(stops_rows)} "
          f"fares={len(fares_rows)} seats={len(seats_rows)} passengers={len(passengers)} "
          f"bookings={len(bookings_rows)} booking_travellers={len(travellers_rows)} actions={len(actions_rows)} "
          f"settings={len(settings_rows)} settings_history={len(history_rows)}")
    print("edge_case_ids=" + repr(edge_case_ids))


def build_settings_rows() -> tuple[list[tuple], list[tuple]]:
    rows: list[tuple] = []
    history: list[tuple] = []

    def add(name, value, source_doc, effective_from, effective_to, unit, old_value=None, changed_at=None, trace_id=None):
        rows.append((name, value, source_doc, iso_date(effective_from), iso_date(effective_to) if effective_to else None, unit))
        history.append((
            name, old_value, value, iso_date(effective_from), source_doc,
            changed_at or iso_dt(effective_from, 9 * 60), trace_id, "seed_generator",
        ))

    rul_from = pv.BASE_DATE.replace(month=1, day=1)  # RUL-CAN-01 effective_from (2026-01-01), independent of --base-date
    for cls, brackets in pv.CANCEL_CHARGE_CNF_RUL_CAN_01.items():
        for bracket, value in brackets.items():
            add(f"cancel_charge_{cls}_{bracket}", value, "RUL-CAN-01", rul_from, None, "INR")
    for bracket, value in pv.CANCEL_CHARGE_RAC_RUL_CAN_01.items():
        add(f"cancel_charge_rac_{bracket}", value, "RUL-CAN-01", rul_from, None, "INR")
    for bracket, value in pv.CANCEL_CHARGE_WL_RUL_CAN_01.items():
        add(f"cancel_charge_wl_{bracket}", value, "RUL-CAN-01", rul_from, None, "INR")

    # Revisions (D2/D4): CIR-2026-07 then CIR-2026-11 both touch the SAME key,
    # each with its own effective_from row, so a lookup "as of" either date
    # resolves correctly, and settings_history records both changes.
    add("cancel_charge_2AC_over_48h", pv.CANCEL_CHARGE_2AC_OVER_48H_CIR_2026_07, "CIR-2026-07",
        pv.CIR_2026_07_EFFECTIVE_FROM, None, "INR", old_value=pv.CANCEL_CHARGE_CNF_RUL_CAN_01["2AC"]["over_48h"])
    add("cancel_charge_2AC_over_48h", pv.CANCEL_CHARGE_2AC_OVER_48H_CIR_2026_11, "CIR-2026-11",
        pv.CIR_2026_11_EFFECTIVE_FROM, None, "INR", old_value=pv.CANCEL_CHARGE_2AC_OVER_48H_CIR_2026_07)

    add("refund_pct_train_cancelled", pv.REFUND_PCT_TRAIN_CANCELLED, "RUL-OPC-01", rul_from, None, "%")
    add("refund_pct_late_over_3h", pv.REFUND_PCT_LATE_OVER_3H, "RUL-OPC-01", rul_from, None, "%")
    add("cancel_cutoff_hours_before_departure", pv.CANCEL_CUTOFF_HOURS_BEFORE_DEPARTURE, "RUL-CAN-01", rul_from, None, "hours")

    for cls, value in pv.TATKAL_CHARGE_RUL_TAT_01.items():
        add(f"tatkal_charge_{cls}", value, "RUL-TAT-01", rul_from, None, "INR")
    for cls, value in pv.TATKAL_CHARGE_CIR_2026_01.items():
        add(f"tatkal_charge_{cls}", value, "CIR-2026-01", pv.CIR_2026_01_EFFECTIVE_FROM, None, "INR",
            old_value=pv.TATKAL_CHARGE_RUL_TAT_01[cls])
    add("tatkal_open_hours_before", pv.TATKAL_OPEN_HOURS_BEFORE, "RUL-TAT-01", rul_from, None, "hours")

    add("boarding_change_cutoff_hours", pv.BOARDING_CHANGE_CUTOFF_HOURS, "RUL-BRD-01", rul_from, None, "hours")
    add("action_expiry_minutes", pv.ACTION_EXPIRY_MINUTES, "RUL-BOOK-01", rul_from, None, "minutes")
    add("max_pax_per_booking", pv.MAX_PAX_PER_BOOKING, "RUL-BOOK-01", rul_from, None, "passengers")
    add("chart_prepared_hours_before", pv.CHART_PREPARED_HOURS_BEFORE, "RUL-BOOK-01", rul_from, None, "hours")

    return rows, history


def build_document_rows() -> tuple[list[tuple], list[tuple]]:
    doc_rows: list[tuple] = []
    chunk_rows: list[tuple] = []
    for doc in load_all_documents():
        meta = doc["meta"]
        doc_id = meta["doc_id"]
        supersedes = meta.get("supersedes") or []
        doc_rows.append((
            doc_id, meta["doc_type"], meta["title"], meta["effective_from"],
            meta.get("effective_to"), "[" + ",".join(f'"{d}"' for d in supersedes) + "]",
            meta["language"], meta.get("status", "active"),
        ))
        for section, text in doc["sections"]:
            chunk_id = f"{doc_id}#{section}"
            chunk_rows.append((chunk_id, doc_id, section, text, meta["language"]))
    return doc_rows, chunk_rows


if __name__ == "__main__":
    main()
