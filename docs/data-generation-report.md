# Data generation report

Run in this session: `python3 data/generator/generate_data.py` then
`python3 data/validate/validate_data.py` (via `.venv`, Python 3.12.14).
`--seed 42 --base-date 2026-12-03` (both defaults). The validator ran
against `db/schema.sql` + `db/seed_data.sql` loaded into a throwaway
in-memory SQLite database — no real `.db` file is touched or committed.

## Actual record counts (from the real generator run, not estimated)

```
stations=17 trains=25 train_stops=112 fares=555 seats=938
passengers=26 bookings=55 booking_travellers=56 actions=5
settings=54 settings_history=54
documents=38 chunks=105
```

Document breakdown: 12 rules, 6 circulars, 20 FAQs (38 total) — matches
the guide's §4.1 minimums exactly on rules/circulars and exceeds the
FAQ minimum requirement of 20.

Booking status coverage (all five present, guide §4.2):
`confirmed`, `rac`, `waitlisted`, `cancelled`, `train_cancelled_by_operator`.

Reproducibility check performed this session: two consecutive runs
with identical arguments produced a byte-identical `db/seed_data.sql`
(`md5 = d86193fe4ba7df2f50d7d16de4769dcc` both times).

## Files generated

**Documents** (38 files, hand-authored, see `docs/ai-prompts.md`):
`data/documents/INDEX.md`, 12 files in `data/documents/rules/`, 6 in
`data/documents/circulars/`, 20 in `data/documents/faqs/`.

**Generator** (script, deterministic):
`data/generator/policy_values.py` (canonical settings values),
`data/generator/generate_data.py` (main script), `data/generator/
edge_cases.py` (bookings/travellers/actions incl. every mandatory
edge case).

**Validator** (script):
`data/validate/validate_data.py` (18 checks).

**Generated data output** (committable text, not a binary `.db`):
`db/seed_data.sql` (2,055 `INSERT` statements).

**Evaluation set**:
`eval/eval_set.json` (34 questions).

**This documentation** (Phase 8):
`docs/data-dictionary.md`, `docs/data-sources-and-limitations.md`,
`docs/data-generation-report.md` (this file), `docs/ai-prompts.md`.

## Validation results (actual output, this run)

```
55 checks passed, 0 warning(s), 0 failure(s)
```

Every one of the 18 check categories in the master data-generation
prompt's Phase 7 ran and passed; nothing here is reported as passed
without actually executing (several genuine failures were caught and
fixed during this session before reaching this result — see below).

Full check list (abbreviated; see `data/validate/validate_data.py` for
the exact SQL/Python behind each):

| # | Check | Result |
|---|---|---|
| 1 | Required record counts (all tables + 5 booking statuses + doc-type minimums) | PASS (13 sub-checks) |
| 2 | Unique primary identifiers (7 tables) | PASS (7 sub-checks) |
| 3 | Foreign-key integrity (`PRAGMA foreign_key_check`) | PASS |
| 4 | Booking → passenger references | PASS |
| 5 | Booking → train references | PASS |
| 6 | Train running-day validity (journey_date vs `runs_on`) | PASS |
| 7 | Valid, correctly-ordered station routes per booking | PASS |
| 8 | Stop ordering (no duplicate/no gaps in `stop_order`) | PASS (2 sub-checks) |
| 9 | Seat capacity consistency (range + CNF-vs-capacity) | PASS (2 sub-checks) |
| 10 | Refund settings/policy consistency incl. settings_history and key registry | PASS (5 sub-checks) |
| 11 | Circular supersession validity | PASS (2 sub-checks) |
| 12 | Future-effective circular handling | PASS (2 sub-checks) |
| 13 | Outdated FAQ references exist | PASS |
| 14 | Evaluation category counts (≥34 total, all 9 category minimums) | PASS (10 sub-checks) |
| 15 | Document/section citations resolve | PASS |
| 16 | Action ownership and booking references | PASS (2 sub-checks) |
| 17 | Action expiry timestamp validity | PASS |
| 18 | No real passenger PII (name/phone shape scan) | PASS (2 sub-checks) |

### Failures found and fixed during this session (full honesty, per the
master prompt: "never report tests as passed unless they actually ran")

1. **First generator run** crashed outright: a procedurally-generated
   train's number (`12123`) collided with the hand-pinned "Ujjwal
   Express" train number, silently overwriting its schedule. Fixed by
   moving the generated-train numbering range away from the pinned
   numbers (`generate_data.py`).
2. **First full validation run** (after fixing #1) found 2 real
   failures:
   - Check #6 failed: 11 filler bookings had a `journey_date` the
     train doesn't actually run on (the filler-booking loop picked a
     random date without checking `runs_on`). Fixed by adding
     `edge_cases.pick_running_date()` and using it everywhere a
     booking date is chosen, including the operator-cancelled-train
     edge case.
   - Check #10's own expectation was wrong, not the data: it asserted
     exactly 2 `settings_history` rows for `cancel_charge_2AC_over_48h`,
     but there are correctly 3 (the original RUL-CAN-01 insertion plus
     the two circular revisions) — a full audit trail is the intended
     behaviour (D2). Fixed by correcting the check's expected count,
     not the generated data.
3. Re-ran both scripts after each fix; the run reported above (55
   passed / 0 failed) is the one after all three fixes, not the first
   attempt.

## Edge-case record IDs (master data-generation prompt, Phase 5)

| # | Edge case | Record ID(s) |
|---|---|---|
| — | Anchor booking (matches Phase 0 stub fakes / api-contracts.md examples) | `UR-30418` (passenger `P007`, train `12123`, 2AC) |
| 1 | Cancellation exactly at the 48h refund cutoff | booking `UR-30001`, action `ACT-EDGE-0001` |
| 2 | Cancellation one minute after the 48h cutoff | booking `UR-30002`, action `ACT-EDGE-0002` |
| 3 | After-midnight train | train `22002` ("Deccan Mail", departs 00:40), booking `UR-30003` |
| 4 | Mixed confirmed + waitlisted travellers on one booking | booking `UR-30004` |
| 5 | Passenger with no bookings | passenger `P026` |
| 6 | Similar station names | `NDLS`/`DLI` ("New Delhi"/"Old Delhi"), `HYB`/`SC` ("Hyderabad Deccan"/"Secunderabad Junction") |
| 7 | Fully booked train | `12123`, 2026-12-05, class `3AC` (capacity 3, bookings `UR-30005`..`UR-30007`) |
| 8 | RAC passenger | booking `UR-30008` |
| 9 | Waitlisted passenger | bookings `UR-30009`, `UR-30010` |
| 10 | Operator-cancelled train | booking `UR-30011` |
| 11 | Expired pending action | booking `UR-30012`, action `ACT-EDGE-0003` |
| 12 | Duplicate confirmation attempt (tested live against the running API) | booking `UR-30013`, action `ACT-EDGE-0004` (already `done`) |
| — | Fresh pending action, for the ordinary single-confirm path | booking `UR-30014`, action `ACT-EDGE-0005` (`proposed`) |
| 13 | Future-effective circular | `CIR-2026-11` (effective 2026-12-10, after `BASE_DATE`) |
| 14 | Outdated FAQ superseded by a circular | `FAQ-07` (superseded by `CIR-2026-07`/`CIR-2026-11`), `FAQ-13` (superseded by `CIR-2026-01`) |

(Printed verbatim by `generate_data.py` as `edge_case_ids=...` on every
run, so this table can be regenerated/re-verified at any time.)

## Known limitations

See `docs/data-sources-and-limitations.md` for the full list. In
summary: `seats` is a point-in-time snapshot, hand-reconciled only for
the combinations the edge-case/anchor bookings actually touch; there is
no live train-delay data; fares follow a formula rather than a
hand-tuned table (except one pinned value); `chunk_vectors` is empty
(no RAG in this phase); and the Markdown front-matter's additive
fields (`version`, `related_docs`, `outdated`, `superseded_by`) are not
yet consumed by any parser.

## What has NOT been done (explicitly out of scope here)

Per the master data-generation prompt, Phase 9: no RAG implementation,
no backend business logic, no frontend, no LLM orchestration, and no
change to the approved architecture/API contracts. Nothing in `data/`,
`db/seed_data.sql`, or `eval/` has been committed or pushed.
