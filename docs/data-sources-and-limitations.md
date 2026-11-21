# Data sources, disclaimers, assumptions and limitations

## Disclaimers

**This is entirely synthetic data for a fictional operator.** "Ujjwal
Rail", every train number, station, fare, policy figure, passenger
name, phone digit, and booking in this repository is invented for the
HCLTech AI Engineer Hackathon. None of it describes any real train
operator, and no real passenger data, real booking reference, or real
payment is involved anywhere (guide §4.1 data rules).

**Policies are fictional.** Cancellation charges, refund brackets,
Tatkal surcharges, concession rates and every other number in
`data/documents/rules/` and `data/documents/circulars/` are Ujjwal
Rail's own invented rules. They may resemble public railway rule
structures (the guide explicitly allows borrowing structure), but the
actual numbers are not real-world figures and must never be presented
as such.

## How the data was produced

* **Rules, circulars, FAQs** (`data/documents/`): drafted directly as
  Markdown files in this session (see `docs/ai-prompts.md` for the
  exact prompt and model). Not script-generated — these are prose
  policy documents, written once and meant to be read/edited by a
  person, matching the guide's "write them with an LLM, then check and
  edit" instruction (§4.1).
* **Structured data** (stations, trains, fares, seats, passengers,
  bookings, travellers, actions, settings): produced by
  `data/generator/generate_data.py`, a deterministic script (fixed
  `--seed`, fixed `--base-date`) with no external dependencies.
  Two trains and a handful of bookings/actions are explicitly pinned
  (not randomised) so they exactly match the worked examples already
  published in `docs/api-contracts.md` and the Phase 0 stub fakes in
  `tests/fakes/`. Everything else (the other 23 trains' schedules,
  ordinary filler bookings, ambient seat fill levels) is built with a
  seeded `random.Random`, so two runs with the same arguments produce
  byte-identical output (verified: `md5(db/seed_data.sql)` matched
  across two consecutive runs during this session).
* **Canonical values**: every policy number appearing in more than one
  place (a rule, a circular, a setting) is defined exactly once in
  `data/generator/policy_values.py` and copied by hand into the
  matching Markdown document, so there is one source of truth, not
  three independently-typed copies that could drift.

## Assumptions

* `BASE_DATE = 2026-12-03` is this data kit's reference "today". It is
  configurable (`--base-date`) but every effective-dated circular in
  this kit was chosen relative to a *real* calendar date, not relative
  to `BASE_DATE`, except CIR-2026-11 (deliberately future, 2026-12-10)
  and CIR-2026-02's window (deliberately expired, ends 2026-09-30) —
  both exist specifically to exercise effective-date filtering in
  either direction. Moving `--base-date` far from 2026-12-03 would
  change which circulars are "in effect" at generation time; the
  worked examples in `docs/api-contracts.md` assume the default.
* A booking's top-level `status` reflects its primary/"best" traveller;
  per-traveller truth is always in `booking_travellers` (see the data
  dictionary's note on the mixed CNF/WL booking).
* Boarding is always assumed to be at a train's origin stop for the
  pinned/edge-case bookings' "hours before departure" calculations
  (`data/generator/edge_cases.py:origin_departure`). A real system
  would use the passenger's actual `from_code` stop.
* Travel classes are fixed to seven codes (`SL, 3AC, 2AC, 1AC, CC, EC,
  2S`); which classes a given train offers is assigned per train, not
  universally.

## Known limitations

* **`seats` is not a live ledger.** For the handful of (train, date,
  class) combinations that the edge-case/anchor bookings actually
  touch, `seats.available/rac/waitlist` are hand-reconciled to exactly
  match those bookings (see the comment above the pinned overrides in
  `generate_data.py`). For the other ~930 (train, date, class)
  combinations — which have at most a couple of ordinary filler
  bookings scattered thinly across them, by construction — the seat
  counts are an **independent, illustrative ambient fill level**, not
  derived from the filler bookings that happen to land on them. The
  validator's seat check (#9) is therefore capacity-based ("CNF
  travellers on a combo never exceed that combo's capacity"), not an
  exact-reconciliation check against every combo's `available` value.
  A real backend computing `available` live from actual bookings would
  not have this limitation.
* **No live train-delay data.** `RUL-OPC-01` §3 (more-than-3-hours-late
  refunds) is a policy statement only; there is no `delays` table or
  per-train live running status in this kit. A "my train is late"
  claim is, by design, meant to be handed to a human desk, not
  computed from data that does not exist here.
* **Fares are a formula, not hand-tuned per route.** Every fare except
  the one pinned `12123/2AC/PUNE/NGP = 2040` value comes from
  `minutes_between_stops × a per-class rate`, rounded to the nearest
  Rs 5. They are internally consistent (same train/class/route always
  gives the same fare) but are not meant to resemble any real fare
  table precisely.
* **`chunk_vectors` is empty.** No embeddings are generated in this
  phase — RAG implementation is explicitly out of scope here
  (architecture.md, master data-generation prompt Phase 9).
* **Front-matter extras are additive, not yet consumed by code.**
  `version`, `related_docs`, `outdated`, `superseded_by` in the
  Markdown front matter are documentation aids for this phase; no
  parser in `app/` reads them yet (the real RAG parser, when built,
  reads `doc_id/doc_type/title/effective_from/effective_to/supersedes/
  language/status` per `docs/api-contracts.md` §5.1, and may ignore or
  formalise the extra fields).
* **Validation covers structure and referential integrity, not every
  possible content error.** `data/validate/validate_data.py` runs 18
  automated checks (record counts, uniqueness, FK integrity, status
  coverage, running-day validity, stop ordering, seat-capacity
  consistency, settings/circular consistency, future/outdated-document
  handling, eval-set shape and citation resolution, action ownership
  and expiry, and a basic real-PII pattern scan). It does **not**
  perform a human editorial review of the rules/circulars/FAQ prose
  for tone, completeness, or subtle factual self-consistency beyond
  what the checks above cover — see `docs/ai-prompts.md` for exactly
  what manual validation has and has not happened so far.
