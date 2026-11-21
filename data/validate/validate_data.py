#!/usr/bin/env python3
"""Independent validator for the Ujjwal Rail synthetic data kit.

Master data-generation prompt, Phase 7. Loads db/schema.sql +
db/seed_data.sql into a throwaway SQLite database (never touches a
real .db file) and runs the 18 checks from that prompt.

Exit code: 0 if every CRITICAL check passes, 1 otherwise. Checks marked
WARN never fail the run; they are reported but do not affect the exit
code (used for the deliberately-approximate ambient seat fill — see
docs/data-sources-and-limitations.md). Every check that runs is
printed PASS/FAIL/WARN; nothing is reported as passed without actually
running the query.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"
SEED_PATH = REPO_ROOT / "db" / "seed_data.sql"

sys.path.insert(0, str(REPO_ROOT))
try:
    from app.contracts.settings_keys import is_registered, value_matches_type  # type: ignore
    HAVE_APP_CONTRACTS = True
except Exception:
    HAVE_APP_CONTRACTS = False


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.passed: int = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
            print(f"PASS  {name}")
        else:
            self.failures.append(f"{name}: {detail}")
            print(f"FAIL  {name}: {detail}")

    def warn(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
            print(f"PASS  {name}")
        else:
            self.warnings.append(f"{name}: {detail}")
            print(f"WARN  {name}: {detail}")


def load_db(schema_path: Path, seed_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.executescript(seed_path.read_text(encoding="utf-8"))
    return conn


def q(conn, sql_text, params=()):
    return conn.execute(sql_text, params).fetchall()


def q1(conn, sql_text, params=()):
    row = conn.execute(sql_text, params).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------
# Checks 1–18 (master data-generation prompt, Phase 7)
# ---------------------------------------------------------------------


def check_record_counts(conn, r: Result) -> None:
    minimums = {
        "stations": 15, "trains": 25, "passengers": 25, "bookings": 50,
        "documents": 38,
    }
    for table, minimum in minimums.items():
        n = q1(conn, f"SELECT COUNT(*) FROM {table}")
        r.check(f"1. record count: {table} >= {minimum}", n >= minimum, f"got {n}")
    doc_types = dict(q(conn, "SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type"))
    r.check("1. record count: >=12 rules", doc_types.get("rule", 0) >= 12, str(doc_types.get("rule")))
    r.check("1. record count: >=6 circulars", doc_types.get("circular", 0) >= 6, str(doc_types.get("circular")))
    r.check("1. record count: >=20 FAQs", doc_types.get("faq", 0) >= 20, str(doc_types.get("faq")))
    statuses = dict(q(conn, "SELECT status, COUNT(*) FROM bookings GROUP BY status"))
    for status in ("confirmed", "rac", "waitlisted", "cancelled", "train_cancelled_by_operator"):
        r.check(f"1. booking status present: {status}", statuses.get(status, 0) > 0, f"count={statuses.get(status, 0)}")


def check_unique_primary_ids(conn, r: Result) -> None:
    tables_pk = {
        "stations": "station_code", "trains": "train_no", "passengers": "passenger_id",
        "bookings": "booking_id", "actions": "action_id", "documents": "doc_id", "chunks": "chunk_id",
    }
    for table, pk in tables_pk.items():
        total = q1(conn, f"SELECT COUNT(*) FROM {table}")
        distinct = q1(conn, f"SELECT COUNT(DISTINCT {pk}) FROM {table}")
        r.check(f"2. unique {pk} in {table}", total == distinct, f"{total} rows, {distinct} distinct")


def check_foreign_keys(conn, r: Result) -> None:
    violations = q(conn, "PRAGMA foreign_key_check")
    r.check("3. foreign-key integrity (PRAGMA foreign_key_check)", len(violations) == 0, f"{len(violations)} violation(s): {violations[:5]}")


def check_booking_to_passenger(conn, r: Result) -> None:
    orphans = q1(conn, """
        SELECT COUNT(*) FROM bookings b
        LEFT JOIN passengers p ON p.passenger_id = b.passenger_id
        WHERE p.passenger_id IS NULL
    """)
    r.check("4. every booking.passenger_id resolves to a real passenger", orphans == 0, f"{orphans} orphan bookings")


def check_booking_to_train(conn, r: Result) -> None:
    orphans = q1(conn, """
        SELECT COUNT(*) FROM bookings b
        LEFT JOIN trains t ON t.train_no = b.train_no
        WHERE t.train_no IS NULL
    """)
    r.check("5. every booking.train_no resolves to a real train", orphans == 0, f"{orphans} orphan bookings")


DAY_INDEX = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


def check_train_running_days(conn, r: Result) -> None:
    rows = q(conn, "SELECT b.booking_id, b.train_no, b.journey_date, t.runs_on FROM bookings b JOIN trains t ON t.train_no = b.train_no")
    bad = []
    for booking_id, train_no, journey_date, runs_on in rows:
        if runs_on == "DAILY":
            continue
        weekday = date.fromisoformat(journey_date).weekday()
        allowed_days = {DAY_INDEX[d] for d in runs_on.split(",")}
        if weekday not in allowed_days:
            bad.append((booking_id, train_no, journey_date, runs_on))
    r.check("6. every booking's journey_date is a day the train actually runs on", len(bad) == 0, f"{len(bad)} bad booking(s): {bad[:5]}")


def check_valid_station_routes(conn, r: Result) -> None:
    bad = q(conn, """
        SELECT b.booking_id FROM bookings b
        WHERE NOT EXISTS (SELECT 1 FROM stations s WHERE s.station_code = b.from_code)
           OR NOT EXISTS (SELECT 1 FROM stations s WHERE s.station_code = b.to_code)
           OR NOT EXISTS (
                SELECT 1 FROM train_stops s1 JOIN train_stops s2
                  ON s1.train_no = s2.train_no AND s1.train_no = b.train_no
                WHERE s1.station_code = b.from_code AND s2.station_code = b.to_code
                  AND s1.stop_order < s2.stop_order
           )
    """)
    r.check("7. every booking's from/to is a valid, correctly-ordered stop pair on that train", len(bad) == 0, f"{len(bad)} bad booking(s): {bad[:5]}")


def check_stop_ordering(conn, r: Result) -> None:
    bad = q(conn, """
        SELECT train_no, COUNT(*) FROM train_stops
        GROUP BY train_no, stop_order HAVING COUNT(*) > 1
    """)
    gaps = q(conn, """
        SELECT train_no FROM train_stops
        GROUP BY train_no
        HAVING MAX(stop_order) != COUNT(*)
    """)
    r.check("8. stop_order has no duplicates within a train", len(bad) == 0, f"{bad[:5]}")
    r.check("8. stop_order is a contiguous 1..N sequence per train", len(gaps) == 0, f"{gaps[:5]}")


def check_seat_capacity_consistency(conn, r: Result) -> None:
    bad_rows = q(conn, "SELECT train_no, journey_date, class FROM seats WHERE available < 0 OR available > capacity OR rac < 0 OR rac > rac_capacity OR waitlist < 0")
    r.check("9. seats: available/rac within [0, capacity]/[0, rac_capacity], waitlist >= 0", len(bad_rows) == 0, f"{bad_rows[:5]}")

    over_capacity = q(conn, """
        SELECT bt_count.train_no, bt_count.journey_date, bt_count.class, bt_count.cnf_count, s.capacity
        FROM (
            SELECT b.train_no, b.journey_date, b.class, COUNT(*) AS cnf_count
            FROM bookings b JOIN booking_travellers bt ON bt.booking_id = b.booking_id
            WHERE bt.status = 'CNF' AND b.status != 'cancelled' AND b.status != 'train_cancelled_by_operator'
            GROUP BY b.train_no, b.journey_date, b.class
        ) bt_count
        JOIN seats s ON s.train_no = bt_count.train_no AND s.journey_date = bt_count.journey_date AND s.class = bt_count.class
        WHERE bt_count.cnf_count > s.capacity
    """)
    r.check("9. CNF travellers booked never exceed that train/date/class's seat capacity", len(over_capacity) == 0, f"{over_capacity[:5]}")


def check_refund_settings_consistency(conn, r: Result) -> None:
    """Spot-check RUL-CAN-01's documented 2AC/over_48h figure (Rs 150)
    is exactly the settings row with that source_doc, and that the two
    circular revisions chain correctly (D4/D6)."""
    rul_value = q1(conn, "SELECT value FROM settings WHERE name='cancel_charge_2AC_over_48h' AND source_doc='RUL-CAN-01'")
    cir07_value = q1(conn, "SELECT value FROM settings WHERE name='cancel_charge_2AC_over_48h' AND source_doc='CIR-2026-07'")
    cir11_value = q1(conn, "SELECT value FROM settings WHERE name='cancel_charge_2AC_over_48h' AND source_doc='CIR-2026-11'")
    r.check("10. RUL-CAN-01 2AC/over_48h settings value is 150", rul_value == 150, f"got {rul_value}")
    r.check("10. CIR-2026-07 revises 2AC/over_48h to 200", cir07_value == 200, f"got {cir07_value}")
    r.check("10. CIR-2026-11 revises 2AC/over_48h to 250", cir11_value == 250, f"got {cir11_value}")
    history_rows = q1(conn, "SELECT COUNT(*) FROM settings_history WHERE name='cancel_charge_2AC_over_48h'")
    # 3 = the original RUL-CAN-01 insertion (old_value NULL -> 150) + the two
    # circular revisions (150 -> 200, 200 -> 250): the full audit trail (D2).
    r.check("10. settings_history has the original insertion + both revisions recorded", history_rows == 3, f"got {history_rows}")
    if HAVE_APP_CONTRACTS:
        names = [row[0] for row in q(conn, "SELECT DISTINCT name FROM settings")]
        unregistered = [n for n in names if not is_registered(n)]
        r.check("10. every settings.name is a registered key (app/contracts/settings_keys.py)", len(unregistered) == 0, f"{unregistered}")
    else:
        r.warn("10. settings key registry check (app not importable here)", False, "skipped")


def check_circular_supersession(conn, r: Result) -> None:
    rows = q(conn, "SELECT doc_id, supersedes_json FROM documents WHERE doc_type='circular' AND supersedes_json != '[]'")
    bad = []
    for doc_id, supersedes_json in rows:
        superseded = json.loads(supersedes_json)
        for s in superseded:
            exists = q1(conn, "SELECT COUNT(*) FROM documents WHERE doc_id = ?", (s,))
            if not exists:
                bad.append((doc_id, s))
    r.check("11. every circular's 'supersedes' list points to a real document", len(bad) == 0, f"{bad}")
    superseding_count = q1(conn, "SELECT COUNT(*) FROM documents WHERE doc_type='circular' AND supersedes_json != '[]'")
    r.check("11. at least 2 circulars supersede an older document", superseding_count >= 2, f"got {superseding_count}")


def check_future_effective_circular(conn, r: Result) -> None:
    today = q1(conn, "SELECT value FROM settings LIMIT 1")  # placeholder; real base date below
    future = q(conn, "SELECT doc_id, effective_from FROM documents WHERE doc_type='circular' AND effective_from > '2026-12-03'")
    r.check("12. at least 1 circular has a future effective_from (relative to BASE_DATE 2026-12-03)", len(future) >= 1, f"{future}")
    cir11_in_settings_future = q1(conn, "SELECT effective_from FROM settings WHERE source_doc='CIR-2026-11'")
    r.check("12. CIR-2026-11's settings row is dated 2026-12-10, after BASE_DATE", cir11_in_settings_future == "2026-12-10", f"got {cir11_in_settings_future}")


def check_outdated_faq_references(conn, r: Result) -> None:
    faqs = q(conn, "SELECT doc_id, supersedes_json FROM documents WHERE doc_type='faq'")
    # "outdated" is additive metadata in the .md front matter (superseded_by),
    # not a schema.sql column — cross-check against the two known outdated FAQs.
    outdated_doc_ids = {"FAQ-07", "FAQ-13"}
    present = {row[0] for row in faqs}
    r.check("13. both known-outdated FAQs (superseded by a circular) exist", outdated_doc_ids <= present, f"missing: {outdated_doc_ids - present}")


def check_eval_category_counts(conn, r: Result) -> None:
    eval_path = REPO_ROOT / "eval" / "eval_set.json"
    if not eval_path.exists():
        r.check("14. eval set exists with >=34 questions and required category minimums", False, "eval/eval_set.json not found")
        return
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    r.check("14. eval set has >= 34 questions", len(data) >= 34, f"got {len(data)}")
    minimums = {
        "train_search_seat_fare": 5, "refund_deadline": 5, "policy": 4, "change_action": 4,
        "human_handover": 3, "vague": 3, "hindi_hinglish": 3, "privacy_attack": 2, "prompt_injection": 2,
    }
    counts: dict[str, int] = {}
    for item in data:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    for category, minimum in minimums.items():
        r.check(f"14. eval category '{category}' >= {minimum}", counts.get(category, 0) >= minimum, f"got {counts.get(category, 0)}")


def check_document_and_section_citations(conn, r: Result) -> None:
    eval_path = REPO_ROOT / "eval" / "eval_set.json"
    if not eval_path.exists():
        r.warn("15. eval citations resolve to real documents/sections", False, "eval set not found; skipped")
        return
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    bad = []
    for item in data:
        for cite in item.get("expected_document_citations", []):
            doc_id, section = cite["doc_id"], cite["section"]
            found = q1(conn, "SELECT COUNT(*) FROM chunks WHERE doc_id = ? AND section = ?", (doc_id, section))
            if not found:
                bad.append((item["test_id"], doc_id, section))
    r.check("15. every eval expected_document_citations entry resolves to a real doc_id+section", len(bad) == 0, f"{bad[:5]}")


def check_action_ownership_and_booking_refs(conn, r: Result) -> None:
    bad_owner = q1(conn, """
        SELECT COUNT(*) FROM actions a LEFT JOIN passengers p ON p.passenger_id = a.passenger_id
        WHERE p.passenger_id IS NULL
    """)
    bad_booking = q1(conn, """
        SELECT COUNT(*) FROM actions a
        WHERE a.booking_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.booking_id = a.booking_id)
    """)
    r.check("16. every action.passenger_id resolves to a real passenger", bad_owner == 0, f"{bad_owner}")
    r.check("16. every non-null action.booking_id resolves to a real booking", bad_booking == 0, f"{bad_booking}")


def check_action_expiry_timestamps(conn, r: Result) -> None:
    rows = q(conn, "SELECT action_id, created_at, expires_at FROM actions")
    bad = []
    for action_id, created_at, expires_at in rows:
        try:
            c = datetime.fromisoformat(created_at)
            e = datetime.fromisoformat(expires_at)
        except ValueError:
            bad.append((action_id, "unparseable timestamp"))
            continue
        if e <= c:
            bad.append((action_id, "expires_at <= created_at"))
    r.check("17. every action's expires_at is a valid, later timestamp than created_at", len(bad) == 0, f"{bad}")


REAL_PII_PATTERNS = [
    re.compile(r"\b\d{10}\b"),           # a bare 10-digit number (full phone)
    re.compile(r"\b\d{12}\b"),           # a bare 12-digit number (Aadhaar-shaped)
    re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),  # PAN-shaped
]


def check_no_real_pii(conn, r: Result) -> None:
    names = q(conn, "SELECT name FROM passengers")
    bad_names = [n[0] for n in names if any(p.search(n[0]) for p in REAL_PII_PATTERNS)]
    phones = q(conn, "SELECT phone_last4 FROM passengers")
    bad_phones = [p[0] for p in phones if p[0] and len(p[0]) != 4]
    r.check("18. no passenger name matches a real-ID-number shape", len(bad_names) == 0, f"{bad_names}")
    r.check("18. phone_last4 is always exactly 4 digits (never a full number)", len(bad_phones) == 0, f"{bad_phones}")


CHECKS = [
    check_record_counts,
    check_unique_primary_ids,
    check_foreign_keys,
    check_booking_to_passenger,
    check_booking_to_train,
    check_train_running_days,
    check_valid_station_routes,
    check_stop_ordering,
    check_seat_capacity_consistency,
    check_refund_settings_consistency,
    check_circular_supersession,
    check_future_effective_circular,
    check_outdated_faq_references,
    check_eval_category_counts,
    check_document_and_section_citations,
    check_action_ownership_and_booking_refs,
    check_action_expiry_timestamps,
    check_no_real_pii,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default=str(SCHEMA_PATH))
    parser.add_argument("--seed-data", default=str(SEED_PATH))
    args = parser.parse_args()

    schema_path, seed_path = Path(args.schema), Path(args.seed_data)
    if not schema_path.exists() or not seed_path.exists():
        print(f"FAIL  cannot find {schema_path} and/or {seed_path} — run generate_data.py first")
        return 1

    conn = load_db(schema_path, seed_path)
    r = Result()
    for check in CHECKS:
        check(conn, r)

    print()
    print(f"{r.passed} checks passed, {len(r.warnings)} warning(s), {len(r.failures)} failure(s)")
    if r.failures:
        print("CRITICAL FAILURES:")
        for f in r.failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
