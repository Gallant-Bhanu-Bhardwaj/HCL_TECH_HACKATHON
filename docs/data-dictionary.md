# Ujjwal Rail — Data Dictionary

Describes every table in `db/schema.sql`, populated by
`data/generator/generate_data.py` into `db/seed_data.sql`, and the
markdown documents in `data/documents/`. Mandatory table/column names
are exactly the official guide's §4.2 list; additive columns are
labelled as such and were approved in `docs/architecture.md` §3.1.

## Domain tables

### `stations`
| Column | Type | Notes |
|---|---|---|
| `station_code` | TEXT PK | e.g. `PUNE`, `NDLS` |
| `name` | TEXT | full station name |
| `other_names` | TEXT | `\|`-separated aliases (e.g. `Bombay\|CST`) |
| `city` | TEXT | |

17 rows. Includes two similar-name pairs on purpose: NDLS "New Delhi"
vs DLI "Old Delhi", and HYB "Hyderabad Deccan" vs SC "Secunderabad
Junction" (edge case #6).

### `trains`
| Column | Type | Notes |
|---|---|---|
| `train_no` | TEXT PK | |
| `name` | TEXT | |
| `runs_on` | TEXT | `DAILY` or a comma list of `MON..SUN` |
| `classes` | TEXT | comma list, e.g. `SL,3AC,2AC` |

25 rows. Two are pinned for determinism and cross-document consistency:
`12123` "Ujjwal Express" (Pune→Nagpur, matches the worked examples in
`docs/api-contracts.md`) and `22002` "Deccan Mail" (the after-midnight
edge case, origin departure 00:40).

### `train_stops`
| Column | Type | Notes |
|---|---|---|
| `train_no` | TEXT | FK → `trains` |
| `station_code` | TEXT | FK → `stations` |
| `stop_order` | INTEGER | 1-based, contiguous per train |
| `arrival` | TEXT | `HH:MM`, NULL at the origin |
| `departure` | TEXT | `HH:MM`, NULL at the terminus |
| `day_offset` | INTEGER | days after origin departure (handles after-midnight arrivals) |

PK `(train_no, stop_order)`.

### `fares`
| Column | Type | Notes |
|---|---|---|
| `train_no`, `class`, `from_code`, `to_code` | TEXT | PK together |
| `fare` | INTEGER | INR |

Generated for **every** ordered stop pair on every train/class, so any
boarding-station change within a route always resolves a real fare
(`RUL-BRD-01`). `fare = max(50, round(minutes_between * class_rate / 5) * 5)`
— a deterministic function of travel time and class, except the single
pinned value `12123/2AC/PUNE/NGP = 2040` (kept exact to match the
worked examples already published in `docs/api-contracts.md`).

### `seats`
| Column | Type | Notes |
|---|---|---|
| `train_no`, `journey_date`, `class` | — | PK together |
| `available`, `rac`, `waitlist` | INTEGER | current counts |
| `capacity` | INTEGER | *additive* (O4) |
| `rac_capacity` | INTEGER | *additive* (O4) |

14 days from `BASE_DATE` (2026-12-03) for every train/class — 938 rows.
Capacities are deliberately small (6–20 seats) to keep the dataset
lightweight; see `docs/data-sources-and-limitations.md` for exactly
which combos are hand-reconciled against real bookings and which are
ambient/illustrative.

### `passengers`
| Column | Type | Notes |
|---|---|---|
| `passenger_id` | TEXT PK | `P001`..`P026` |
| `name` | TEXT | synthetic |
| `phone_last4` | TEXT | always exactly 4 digits; no full number is ever stored |
| `preferred_language` | TEXT | `en` \| `hi` \| `hinglish` |

26 rows. `P007` = "A. Sharma", pinned to match the Phase 0 stub fakes.
`P026` deliberately has **no bookings** (edge case #5).

### `bookings`
| Column | Type | Notes |
|---|---|---|
| `booking_id` | TEXT PK | `UR-<n>` |
| `passenger_id` | TEXT | FK |
| `train_no` | TEXT | FK |
| `journey_date` | TEXT | `YYYY-MM-DD`; always a day the train actually runs |
| `from_code`, `to_code` | TEXT | FK; always a valid, correctly-ordered stop pair |
| `class` | TEXT | |
| `amount_paid` | INTEGER | INR |
| `status` | TEXT | `confirmed` \| `rac` \| `waitlisted` \| `cancelled` \| `train_cancelled_by_operator` |
| `booked_at` | TEXT | ISO datetime |

55 rows, all five statuses present. One booking (a mixed-status case,
see `booking_travellers` below) has `status='confirmed'` at the booking
level even though one traveller on it is waitlisted — the convention
this data kit uses is: **booking-level `status` reflects the
"best"/primary traveller's state; per-traveller truth is always in
`booking_travellers`.**

### `booking_travellers`
| Column | Type | Notes |
|---|---|---|
| `booking_id` | TEXT | FK; PK with `traveller_name` |
| `traveller_name` | TEXT | synthetic |
| `age` | INTEGER | |
| `status` | TEXT | `CNF` \| `RAC` \| `WL` |
| `coach`, `berth` | TEXT | NULL until confirmed/allotted |

56 rows (one booking has 2 travellers: one CNF, one WL — edge case #4).

### `actions`
| Column | Type | Notes |
|---|---|---|
| `action_id` | TEXT PK | `ACT-EDGE-000n` for the 5 seeded ones |
| `passenger_id`, `booking_id` | TEXT | FK |
| `action_type` | TEXT | `book_ticket` \| `cancel_booking` \| `change_boarding_station` |
| `status` | TEXT | `proposed` \| `executing` \| `done` \| `failed` \| `cancelled` \| `expired` |
| `created_at`, `expires_at` | TEXT | `expires_at` always later than `created_at` |
| `result` | TEXT | JSON, NULL until done/failed |
| `as_of` | TEXT | *additive, required (D6)* — business clock, separate from `expires_at`'s operational clock |
| `params_json`, `preview_json`, `trace_id` | TEXT | *additive* |

5 seeded rows, one per action-lifecycle edge case (exact-cutoff done,
after-cutoff done, expired, done-for-duplicate-confirm-demo, proposed-
and-still-open).

### `settings` / `settings_history`
`settings(name, value, source_doc, effective_from, effective_to, unit)`
— 54 rows, one per `(key, effective_from)` pair; a key with more than
one circular revision has more than one row (D2/D4). `settings_history`
is append-only (enforced by triggers) — 54 rows, one per settings row
ever written, each recording `old_value -> new_value`.

### `documents` / `chunks` / `chunk_vectors`
Parsed directly from `data/documents/**/*.md` at generation time —
38 documents (12 rules, 6 circulars, 20 FAQs), 105 chunks (one per `##`
section). `chunk_vectors` is left empty by the generator (no RAG
implementation in this phase — architecture.md explicitly excludes it
from this data-generation step).

## Document front matter (`data/documents/**/*.md`)

| Field | Required | Notes |
|---|---|---|
| `doc_id` | yes | `RUL-*` \| `CIR-*` \| `FAQ-*` |
| `doc_type` | yes | `rule` \| `circular` \| `faq` |
| `title` | yes | |
| `version` | *additive* | informational only |
| `effective_from` | yes | ISO date |
| `effective_to` | optional | ISO date; empty = open-ended |
| `supersedes` | yes (may be `[]`) | list of doc_ids this one overrides |
| `language` | yes | `en` \| `hi` \| `hinglish` |
| `status` | yes | `active` \| `withdrawn` |
| `related_docs` | *additive* | cross-reference hints, not used by validation |
| `outdated`, `superseded_by` | *additive*, FAQs only | marks the 2 intentionally outdated FAQs (FAQ-07, FAQ-13) |

Each `##` heading inside the body is one **section**; its exact text is
the `section` value used everywhere (citations, `chunks.section`).

## Enumerated values (cross-reference)

Mirrors `app/contracts/enums.py` exactly — see that file for the
authoritative list (`AnswerType`, `ActionType`, `ActionStatus`,
`TravellerStatus`, `BookingStatus`, `Intent`, `Desk`, `Language`,
`DocType`, `BookingOutcome`). This data kit uses no value outside
those enums.
