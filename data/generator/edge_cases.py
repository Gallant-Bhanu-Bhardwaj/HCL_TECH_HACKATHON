"""Bookings, booking_travellers and actions — including every mandatory
awkward case from the master data-generation prompt, Phase 5, plus the
guide's own list (§4.2 "a few awkward cases on purpose").

Imported by generate_data.py; kept in its own module because this is
the part of the dataset that most needs to be read on its own, in one
place, when checking which record backs which edge case (see also
docs/edge-cases.md, written after generation with the real IDs).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

TZ_SUFFIX = "+05:30"
FIRST_NAMES_EXTRA = ["Ananya", "Vivaan", "Ishaan", "Riya", "Kabir"]
DAY_INDEX = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


def pick_running_date(rng, base_date: date, runs_on: str, horizon_days: int) -> date | None:
    """A journey_date within [base_date, base_date+horizon_days) that the
    train actually runs on (check #6: validator rejects any booking
    whose journey_date the train doesn't run)."""
    candidates = [base_date + timedelta(days=d) for d in range(horizon_days)]
    if runs_on != "DAILY":
        allowed = {DAY_INDEX[d] for d in runs_on.split(",")}
        candidates = [d for d in candidates if d.weekday() in allowed]
    return rng.choice(candidates) if candidates else None


def iso_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def iso_dt(d: date, t: time) -> str:
    return f"{d.strftime('%Y-%m-%d')}T{t.strftime('%H:%M:%S')}{TZ_SUFFIX}"


def origin_departure(train_meta_entry: dict, journey_date: date) -> datetime:
    """Naive datetime (local, +05:30 implied) of the ORIGIN stop's
    departure on `journey_date`. All pinned/edge-case bookings in this
    module board at the train's origin stop, so day_offset is always 0
    there by construction (see generate_data.build_stops)."""
    origin = train_meta_entry["stops"][0]
    hh, mm = (int(x) for x in origin["departure"].split(":"))
    return datetime.combine(journey_date, time(hh, mm))


def build_bookings_and_edge_cases(
    rng, base_date: date, passengers: list[dict], train_meta: dict[str, dict],
) -> tuple[list[tuple], list[tuple], list[tuple], dict[str, str]]:
    bookings: list[tuple] = []
    travellers: list[tuple] = []
    actions: list[tuple] = []
    edge_case_ids: dict[str, str] = {}

    booked_at_default = iso_dt(base_date - timedelta(days=5), time(10, 0))

    def add_booking(booking_id, passenger_id, train_no, journey_date, from_code, to_code,
                     cls, amount_paid, status, booked_at=None):
        bookings.append((
            booking_id, passenger_id, train_no, iso_date(journey_date), from_code, to_code,
            cls, amount_paid, status, booked_at or booked_at_default,
        ))

    def add_traveller(booking_id, name, age, status, coach=None, berth=None):
        travellers.append((booking_id, name, age, status, coach, berth))

    def add_action(action_id, passenger_id, booking_id, action_type, status,
                     created_at, expires_at, result, as_of, params_json, preview_json, trace_id):
        actions.append((
            action_id, passenger_id, booking_id, action_type, status,
            created_at, expires_at, result, as_of, params_json, preview_json, trace_id,
        ))

    def fare(train_no, cls, from_code, to_code, fares_lookup) -> int:
        return fares_lookup[(train_no, cls, from_code, to_code)]

    # ------------------------------------------------------------------
    # Build a fares lookup the same way generate_data.py built fares_rows,
    # by recomputing minutes-between from train_meta (keeps this module
    # self-contained; no import cycle with generate_data.py).
    # ------------------------------------------------------------------
    CLASS_FARE_PER_MIN = {"2S": 0.35, "SL": 0.55, "CC": 0.75, "3AC": 1.35, "EC": 1.55, "2AC": 1.95, "1AC": 3.10}

    def _minutes(hhmm_str: str) -> int:
        h, m = hhmm_str.split(":")
        return int(h) * 60 + int(m)

    fares_lookup: dict[tuple, int] = {}
    for train_no, meta in train_meta.items():
        stops = meta["stops"]
        cum = [0]
        for i in range(1, len(stops)):
            prev_dep = stops[i - 1]["departure"] or stops[i - 1]["arrival"]
            this_arr = stops[i]["arrival"] or stops[i]["departure"]
            prev_total = stops[i - 1]["day_offset"] * 1440 + _minutes(prev_dep)
            this_total = stops[i]["day_offset"] * 1440 + _minutes(this_arr)
            cum.append(cum[-1] + (this_total - prev_total))
        for i in range(len(stops)):
            for j in range(i + 1, len(stops)):
                minutes_between = cum[j] - cum[i]
                for cls in meta["classes"]:
                    raw = minutes_between * CLASS_FARE_PER_MIN[cls]
                    f = max(50, int(round(raw / 5.0)) * 5)
                    if train_no == "12123" and stops[i]["station_code"] == "PUNE" and stops[j]["station_code"] == "NGP" and cls == "2AC":
                        f = 2040
                    fares_lookup[(train_no, cls, stops[i]["station_code"], stops[j]["station_code"])] = f

    pax_cycle = [p["passenger_id"] for p in passengers]
    seq = {"n": 1}

    def next_booking_id() -> str:
        bid = f"UR-{30000 + seq['n']}"
        seq["n"] += 1
        return bid

    # ==================================================================
    # EDGE CASE: anchor booking — matches the Phase 0 stub fakes and the
    # worked examples already published in docs/api-contracts.md exactly.
    # ==================================================================
    anchor_journey_date = base_date + timedelta(days=2)  # 2026-12-05 when base_date=2026-12-03
    add_booking("UR-30418", "P007", "12123", anchor_journey_date, "PUNE", "NGP", "2AC",
                2040, "confirmed", booked_at=iso_dt(base_date - timedelta(days=13), time(11, 2)))
    add_traveller("UR-30418", "A. Sharma", 34, "CNF", coach="B2", berth="21")
    edge_case_ids["anchor_booking_matches_phase0_fakes"] = "UR-30418"

    # ==================================================================
    # Edge cases #1/#2 — cancellation exactly at the refund cutoff, and
    # one minute after it (RUL-CAN-01 §3/§6, D4 inclusive lower bound).
    # ==================================================================
    dep = origin_departure(train_meta["12123"], anchor_journey_date)  # PUNE 18:40 on anchor_journey_date
    sl_fare = fare("12123", "SL", "PUNE", "NGP", fares_lookup)

    exact_booking = next_booking_id()
    add_booking(exact_booking, "P010", "12123", anchor_journey_date, "PUNE", "NGP", "SL",
                sl_fare, "cancelled", booked_at=iso_dt(base_date - timedelta(days=10), time(9, 0)))
    add_traveller(exact_booking, "Riya Nair", 29, "CNF")
    as_of_exact = dep - timedelta(hours=48)  # exactly 48h0m before departure -> "over_48h" bracket (inclusive lower bound)
    charge_exact = 60  # SL, over_48h (policy_values.CANCEL_CHARGE_CNF_RUL_CAN_01["SL"]["over_48h"])
    add_action(
        "ACT-EDGE-0001", "P010", exact_booking, "cancel_booking", "done",
        iso_dt(as_of_exact.date(), as_of_exact.time()), iso_dt(as_of_exact.date(), (as_of_exact + timedelta(minutes=15)).time()),
        f'{{"booking_status":"cancelled","refund":{sl_fare - charge_exact},"matches_preview":true}}',
        iso_dt(as_of_exact.date(), as_of_exact.time()),
        f'{{"booking_id":"{exact_booking}"}}',
        f'{{"amount_paid":{sl_fare},"charge":{charge_exact},"refund":{sl_fare - charge_exact},"hours_before_departure":48.0}}',
        None,
    )
    edge_case_ids["cancel_exactly_at_48h_cutoff"] = {"booking_id": exact_booking, "action_id": "ACT-EDGE-0001"}

    after_booking = next_booking_id()
    add_booking(after_booking, "P011", "12123", anchor_journey_date, "PUNE", "NGP", "SL",
                sl_fare, "cancelled", booked_at=iso_dt(base_date - timedelta(days=10), time(9, 5)))
    add_traveller(after_booking, "Kabir Singh", 41, "CNF")
    as_of_after = dep - timedelta(hours=47, minutes=59)  # one minute later -> "12h_to_48h" bracket
    charge_after = 120  # SL, 12h_to_48h
    add_action(
        "ACT-EDGE-0002", "P011", after_booking, "cancel_booking", "done",
        iso_dt(as_of_after.date(), as_of_after.time()), iso_dt(as_of_after.date(), (as_of_after + timedelta(minutes=15)).time()),
        f'{{"booking_status":"cancelled","refund":{sl_fare - charge_after},"matches_preview":true}}',
        iso_dt(as_of_after.date(), as_of_after.time()),
        f'{{"booking_id":"{after_booking}"}}',
        f'{{"amount_paid":{sl_fare},"charge":{charge_after},"refund":{sl_fare - charge_after},"hours_before_departure":47.983333}}',
        None,
    )
    edge_case_ids["cancel_one_minute_after_48h_cutoff"] = {"booking_id": after_booking, "action_id": "ACT-EDGE-0002"}

    # ==================================================================
    # Edge case #3 — after-midnight train (train 22002, already built
    # with origin departure 00:40). One ordinary booking on it.
    # ==================================================================
    midnight_booking = next_booking_id()
    midnight_journey_date = base_date + timedelta(days=1)
    cc_fare = fare("22002", "CC", "CSMT", "PUNE", fares_lookup)
    add_booking(midnight_booking, "P012", "22002", midnight_journey_date, "CSMT", "PUNE", "CC", cc_fare, "confirmed")
    add_traveller(midnight_booking, "Ananya Rao", 27, "CNF", coach="C1", berth="12")
    edge_case_ids["after_midnight_train_booking"] = midnight_booking

    # ==================================================================
    # Edge case #4 — mixed confirmed/waitlisted travellers on one booking.
    # ==================================================================
    mixed_booking = next_booking_id()
    sl_fare_mixed = fare("12123", "SL", "PUNE", "NGP", fares_lookup)
    add_booking(mixed_booking, "P013", "12123", anchor_journey_date, "PUNE", "NGP", "SL", sl_fare_mixed * 2, "confirmed")
    add_traveller(mixed_booking, "Vivaan Mehta", 30, "CNF", coach="S4", berth="10")
    add_traveller(mixed_booking, "Ishaan Mehta", 8, "WL")
    edge_case_ids["mixed_cnf_and_wl_travellers_booking"] = mixed_booking

    # ==================================================================
    # Edge cases #7/#8/#9 — fully booked / RAC / waitlisted, all on one
    # deliberately small-capacity combo (12123, anchor_journey_date, 3AC).
    # Capacity for THIS combo is overridden to 3 in generate_data.py's
    # pinned seat overrides so these few bookings alone exhaust it.
    # ==================================================================
    fullybooked_ids = []
    for i in range(3):
        bid = next_booking_id()
        fare3ac = fare("12123", "3AC", "PUNE", "NGP", fares_lookup)
        add_booking(bid, pax_cycle[13 + i], "12123", anchor_journey_date, "PUNE", "NGP", "3AC", fare3ac, "confirmed")
        add_traveller(bid, f"Traveller {i+1} (fully-booked 3AC demo)", 35 + i, "CNF", coach="B1", berth=str(10 + i))
        fullybooked_ids.append(bid)
    edge_case_ids["fully_booked_3AC_combo_bookings"] = fullybooked_ids

    rac_booking = next_booking_id()
    fare3ac = fare("12123", "3AC", "PUNE", "NGP", fares_lookup)
    add_booking(rac_booking, "P016", "12123", anchor_journey_date, "PUNE", "NGP", "3AC", fare3ac, "rac")
    add_traveller(rac_booking, "Divya Kapoor", 26, "RAC")
    edge_case_ids["rac_traveller_booking"] = rac_booking

    wl_booking_ids = []
    for i in range(2):
        bid = next_booking_id()
        add_booking(bid, pax_cycle[17 + i], "12123", anchor_journey_date, "PUNE", "NGP", "3AC", fare3ac, "waitlisted")
        add_traveller(bid, f"Waitlisted Traveller {i+1}", 22 + i, "WL")
        wl_booking_ids.append(bid)
    edge_case_ids["waitlisted_traveller_bookings"] = wl_booking_ids

    # ==================================================================
    # Edge case #10 — operator-cancelled train.
    # ==================================================================
    opcancel_booking = next_booking_id()
    some_train_no = sorted(train_meta.keys())[3]
    opcancel_date = pick_running_date(rng, base_date, train_meta[some_train_no]["runs_on"], 14) or base_date
    cls0 = train_meta[some_train_no]["classes"][0]
    stops0 = train_meta[some_train_no]["stops"]
    from_code0, to_code0 = stops0[0]["station_code"], stops0[-1]["station_code"]
    fare_opc = fares_lookup.get((some_train_no, cls0, from_code0, to_code0), 500)
    add_booking(opcancel_booking, "P019", some_train_no, opcancel_date, from_code0, to_code0, cls0,
                fare_opc, "train_cancelled_by_operator")
    add_traveller(opcancel_booking, "Gautam Bose", 45, "CNF")
    edge_case_ids["operator_cancelled_train_booking"] = opcancel_booking

    # ==================================================================
    # Edge case #11 — expired pending action (never confirmed in time).
    # ==================================================================
    expired_booking = next_booking_id()
    exp_date = base_date + timedelta(days=3)
    sl_fare2 = fare("12123", "SL", "PUNE", "NGP", fares_lookup)
    add_booking(expired_booking, "P020", "12123", exp_date, "PUNE", "NGP", "SL", sl_fare2, "confirmed")
    add_traveller(expired_booking, "Tarun Iyer", 38, "CNF", coach="S2", berth="5")
    proposed_at = datetime.combine(base_date, time(9, 0))
    add_action(
        "ACT-EDGE-0003", "P020", expired_booking, "cancel_booking", "expired",
        iso_dt(proposed_at.date(), proposed_at.time()),
        iso_dt(proposed_at.date(), (proposed_at + timedelta(minutes=15)).time()),
        None,
        iso_dt(proposed_at.date(), proposed_at.time()),
        f'{{"booking_id":"{expired_booking}"}}',
        f'{{"amount_paid":{sl_fare2},"charge":60,"refund":{sl_fare2 - 60}}}',
        None,
    )
    edge_case_ids["expired_pending_action"] = {"booking_id": expired_booking, "action_id": "ACT-EDGE-0003"}

    # ==================================================================
    # Edge case #12 — duplicate confirmation attempt: a PROPOSED action
    # still open (fresh confirm) and a DONE action (confirming it again
    # against the running system must be idempotent, not a double-cancel).
    # ==================================================================
    duplicate_booking = next_booking_id()
    dup_date = base_date + timedelta(days=4)
    fare2ac = fare("12123", "2AC", "PUNE", "NGP", fares_lookup)
    add_booking(duplicate_booking, "P021", "12123", dup_date, "PUNE", "NGP", "2AC", fare2ac, "confirmed")
    add_traveller(duplicate_booking, "Radhika Desai", 31, "CNF", coach="B3", berth="15")
    done_at = datetime.combine(base_date - timedelta(days=1), time(10, 0))
    add_action(
        "ACT-EDGE-0004", "P021", duplicate_booking, "cancel_booking", "done",
        iso_dt(done_at.date(), done_at.time()), iso_dt(done_at.date(), (done_at + timedelta(minutes=15)).time()),
        f'{{"booking_status":"confirmed","note":"illustrative only — this action was proposed then confirmed once; a second confirm against the running API must return idempotent_replay=true, not cancel twice"}}',
        iso_dt(done_at.date(), done_at.time()),
        f'{{"booking_id":"{duplicate_booking}"}}',
        f'{{"amount_paid":{fare2ac},"charge":150,"refund":{fare2ac - 150}}}',
        None,
    )
    edge_case_ids["duplicate_confirmation_demo_action"] = {"booking_id": duplicate_booking, "action_id": "ACT-EDGE-0004"}

    fresh_booking = next_booking_id()
    fresh_date = base_date + timedelta(days=5)
    add_booking(fresh_booking, "P022", "12123", fresh_date, "PUNE", "NGP", "2AC", fare2ac, "confirmed")
    add_traveller(fresh_booking, "Fatima Khan", 29, "CNF", coach="B2", berth="30")
    proposed_fresh_at = datetime.combine(base_date, time(8, 0))
    add_action(
        "ACT-EDGE-0005", "P022", fresh_booking, "cancel_booking", "proposed",
        iso_dt(proposed_fresh_at.date(), proposed_fresh_at.time()),
        iso_dt(proposed_fresh_at.date(), (proposed_fresh_at + timedelta(minutes=15)).time()),
        None,
        iso_dt(proposed_fresh_at.date(), proposed_fresh_at.time()),
        f'{{"booking_id":"{fresh_booking}"}}',
        f'{{"amount_paid":{fare2ac},"charge":150,"refund":{fare2ac - 150}}}',
        None,
    )
    edge_case_ids["fresh_pending_action_awaiting_confirm"] = {"booking_id": fresh_booking, "action_id": "ACT-EDGE-0005"}

    # ==================================================================
    # Edge case #5 — a passenger with no bookings at all (reserved: never
    # given a booking anywhere in this module or the filler loop below).
    # ==================================================================
    no_booking_passenger = passengers[-1]["passenger_id"]  # the last generated passenger (P026)
    edge_case_ids["passenger_with_no_bookings"] = no_booking_passenger

    # ==================================================================
    # Edge case #6 — similar station names: no extra record needed, the
    # stations themselves (NDLS/"New Delhi" vs DLI/"Old Delhi", and
    # HYB/"Hyderabad Deccan" vs SC/"Secunderabad Junction") are enough.
    # Recorded here only so every edge case has one lookup entry.
    # ==================================================================
    edge_case_ids["similar_station_names"] = ["NDLS/DLI", "HYB/SC"]

    # ==================================================================
    # Filler bookings — ordinary confirmed/rac/waitlisted/cancelled
    # bookings across the remaining passengers and trains, to reach the
    # guide's minimum of 50 bookings in total across all five statuses.
    # ==================================================================
    reserved_passengers = {no_booking_passenger}
    train_list = sorted(train_meta.keys())
    status_cycle = ["confirmed", "confirmed", "rac", "waitlisted", "cancelled"]
    filler_count = 0
    target_total_bookings = 55  # comfortably above the guide's minimum of 50
    while len(bookings) < target_total_bookings:
        pax = pax_cycle[filler_count % len(pax_cycle)]
        if pax in reserved_passengers:
            filler_count += 1
            continue
        train_no = train_list[filler_count % len(train_list)]
        meta = train_meta[train_no]
        stops = meta["stops"]
        if len(stops) < 2:
            filler_count += 1
            continue
        i = 0
        j = rng.randint(1, len(stops) - 1)
        from_code, to_code = stops[i]["station_code"], stops[j]["station_code"]
        cls = meta["classes"][filler_count % len(meta["classes"])]
        f = fares_lookup.get((train_no, cls, from_code, to_code))
        if f is None:
            filler_count += 1
            continue
        journey_date = pick_running_date(rng, base_date, meta["runs_on"], 14)
        if journey_date is None:
            filler_count += 1
            continue
        status = status_cycle[filler_count % len(status_cycle)]
        traveller_status = {"confirmed": "CNF", "rac": "RAC", "waitlisted": "WL", "cancelled": "CNF"}[status]
        bid = next_booking_id()
        add_booking(bid, pax, train_no, journey_date, from_code, to_code, cls, f, status)
        name = f"{rng.choice(FIRST_NAMES_EXTRA)} Traveller"
        add_traveller(bid, name, rng.randint(5, 70), traveller_status,
                      coach=(f"{cls[0]}{rng.randint(1,9)}" if status != "waitlisted" else None),
                      berth=(str(rng.randint(1, 72)) if status in ("confirmed",) else None))
        filler_count += 1

    return bookings, travellers, actions, edge_case_ids
