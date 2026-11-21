# AI prompts and generation provenance

Guide §4.1/§8: "the exact prompts you used, word for word, and the
model that produced the data" / "a note on which parts were written
with AI tools". This file covers the data-generation phase only; the
architecture/API-contracts/Phase-0 phases have their own provenance in
`docs/architecture.md` §3 (decision log) and git history.

## Model used

* **This data-generation phase** (Phases 1–10 below): **Claude Sonnet
  5**, model ID `claude-sonnet-5`, run inside Claude Code.
* The earlier architecture/API-contracts/Phase-0-skeleton work in this
  same repository was done in the same conversation but before the
  user switched models with `/model claude-sonnet-5`; that earlier
  work was produced with **Claude Sonnet 5.5**, model ID
  `claude-sonnet-5-5`. Both are stated here so neither is misattributed.

## Generation date

2026-11-21 (session date; `BASE_DATE` used *inside* the generated data
is a separate, independent value, `2026-12-03` — see
`data/generator/policy_values.py` and `docs/data-sources-and-limitations.md`).

## Exact prompt (verbatim, word for word)

The user's instruction for this phase, reproduced exactly as given,
including its own internal phase numbering (its "Phase 1–10" are not
the same as this repository's architecture Phase 0–5):

~~~text
# MASTER PROMPT: COMPLETE DATA GENERATION – UJJWAL RAIL

Act as a Senior Data Engineer, Synthetic Dataset Architect and Data Quality Engineer.

Your task is to generate a complete, reproducible, internally consistent and validated synthetic data kit for our HCLTech AI Engineer Hackathon project.

**Project:** Ujjwal Rail – AI-Powered Train Travel Assistant for Bookings, Refunds and Journey Help.

The generated data will be consumed by five engineering modules:
1. Backend
2. RAG
3. AI/LLM
4. Frontend
5. Data & Testing

Your output must be realistic, internally consistent, lightweight and integration-ready.

---

## PHASE 1 — REPOSITORY INSPECTION

Before creating anything, inspect the current repository.

Read these files completely:

1. `docs/architecture.md`
2. `docs/api-contracts.md`
3. `docs/phase0-tasks.md`
4. Official hackathon problem statement DOCX.
5. Existing data schemas and application files, if any.

Verify:
- Current working directory.
- Current Git branch.
- Git status.
- Architecture and API contract versions.
- Existing data directory structure.

**Authoritative requirements:**
- Official hackathon participant guide.
- Approved architecture v1.2.
- Approved API contracts v1.2.

Follow exact table names, columns, document ID conventions, settings keys, action schemas, evaluation schemas and directory requirements.

Do not invent alternative schemas.

If a critical conflict exists, stop and report it before generation.

Do not overwrite existing work.

---

## PHASE 2 — KNOWLEDGE BASE GENERATION

Generate a fictional Ujjwal Rail knowledge base.

### A. Rules — minimum 12 documents

Create individual documents covering:

1. Booking rules and booking lifecycle.
2. Train classes.
3. Cancellation rules and charges.
4. Refund eligibility and calculations.
5. RAC and waitlist rules.
6. Tatkal booking rules.
7. Passenger ID requirements.
8. Luggage and pets.
9. Concessions.
10. Boarding station changes.
11. Cancelled and delayed train refunds.
12. Complaints and grievance handling.

Every document must contain:
- Unique document ID.
- Title.
- Version.
- Document type.
- Effective date.
- Expiry date, if applicable.
- Sections with unique section IDs.
- Clear policy statements.
- Relevant numeric values.
- Related document references where applicable.

Do not create superficial placeholder documents.

### B. Circulars — minimum 6

Requirements:
- At least 2 circulars supersede older rules.
- At least 1 circular has a future effective date.
- Include supersedes relationships.
- Include publication and effective dates.
- Include version and source-priority metadata according to architecture.
- Include at least one Hindi/Hinglish circular.
- Include explicit policy-change examples.

Ensure old and new policy versions can be distinguished.

### C. FAQs — minimum 20

Cover:
- Train search.
- Availability.
- Fares.
- Booking.
- Cancellation.
- Refunds.
- RAC.
- Waitlist.
- Tatkal.
- Boarding station.
- Luggage.
- Complaints.

Requirements:
- At least 2 FAQs must be outdated due to newer circulars.
- Include English, Hindi and Hinglish questions and answers.
- Every FAQ must reference a valid document ID and section ID.
- Answers must be concise and user-friendly.

All policies must be fictional Ujjwal Rail policies. Never present them as actual Indian Railways rules.

---

## PHASE 3 — POLICY SETTINGS

Generate centralized policy settings according to the exact approved architecture schema.

Include:
- Cancellation charges by class.
- Refund percentage or amount by time bracket.
- Refund cutoff values.
- Tatkal charges.
- Pending action expiry duration.
- Boarding station change deadline.
- All other numerical policy values referenced in the documents.

For each setting, include the fields required by the approved architecture.

Requirements:
1. Use exact approved setting key names.
2. Reference valid source document IDs.
3. Keep values consistent across rules, circulars and FAQs.
4. Maintain effective-date semantics.
5. Support structured settings changes through the approved ingestion contract.
6. Include examples of settings changes introduced by circulars.
7. Text-only ingestion must never silently modify settings.

### Refund boundary semantics

- Lower boundary of every refund bracket is inclusive.
- Exactly at a cutoff belongs to the bracket beginning at that cutoff.
- One minute beyond the cutoff uses the appropriate next bracket.
- Keep semantics consistent in policy documents, settings and evaluation expectations.

Never delegate numerical refund calculations to the LLM.

---

## PHASE 4 — STRUCTURED RAILWAY DATA

Generate synthetic structured data following the exact official guide and approved architecture schemas.

### Stations
Minimum 15.

Official fields:
- station_code
- name
- other_names
- city

Include aliases and similar station names.

### Trains
Minimum 25 fictional trains.

Fields:
- train_no
- name
- runs_on
- classes

### Train stops

Fields:
- train_no
- station_code
- stop_order
- arrival
- departure
- day_offset

Generate valid stop sequences and include after-midnight journeys.

### Fares

Fields:
- train_no
- class
- from_code
- to_code
- fare

Use deterministic fictional fares.

### Seats

Generate seat availability for the next 14 days from a configurable base date.

Fields:
- train_no
- journey_date
- class
- available
- rac
- waitlist

Include:
- Available seats.
- Fully booked trains.
- RAC cases.
- Waitlisted cases.

### Passengers

Minimum 25 fictional passengers.

Fields:
- passenger_id
- name
- phone_last4
- preferred_language

Use synthetic identities only. Never use real passenger information.

### Bookings

Minimum 50 bookings.

Fields:
- booking_id
- passenger_id
- train_no
- journey_date
- from_code
- to_code
- class
- amount_paid
- status
- booked_at

Include:
- Confirmed bookings.
- RAC bookings.
- Waitlisted bookings.
- Passenger-cancelled bookings.
- Operator-cancelled train bookings.

### Booking travellers

Follow the official schema exactly:

- booking_id
- traveller_name
- age
- status (CNF/RAC/WL)
- coach
- berth

Include multiple travellers and mixed CNF/WL travellers.

### Actions

Generate a small realistic synthetic action dataset according to the exact approved architecture schema.

Include representative:
- Pending actions.
- Confirmed actions.
- Cancelled actions.
- Expired actions.

Respect exact action IDs, passenger ownership, booking references, action types, status values, timestamps, expiry timestamps and results.

Do not invent additional fields.

### Settings

Follow the approved guide and architecture schema. Ensure compatibility with the settings history design.

---

## PHASE 5 — MANDATORY EDGE CASES

Create clearly identifiable records for:

1. Cancellation exactly at refund cutoff.
2. Cancellation one minute after refund cutoff.
3. After-midnight train.
4. Mixed confirmed and waitlisted travellers.
5. Passenger without bookings.
6. Similar station names.
7. Fully booked train.
8. RAC passenger.
9. Waitlisted passenger.
10. Operator-cancelled train.
11. Expired pending action.
12. Duplicate confirmation attempt.
13. Future-effective circular.
14. Outdated FAQ superseded by circular.

Create an edge-case reference document containing actual record IDs.

---

## PHASE 6 — EVALUATION DATASET

Generate at least 34 evaluation questions.

Minimum coverage:

- 5 train search, seat and fare questions.
- 5 refund or deadline questions, including cutoff boundary cases.
- 4 policy questions, including newer circulars.
- 4 change requests: a booking, a cancellation, a confirm sent twice, and a change that is not allowed.
- 3 situations that must go to a person, and 3 vague questions.
- 3 questions in Hindi or mixed Hindi and English.
- 2 attempts to see someone else's booking, and 2 attempts to slip in instructions.

Each evaluation record must follow the approved evaluation schema and contain the applicable fields:

- test_id
- category
- user_query
- passenger_id where applicable
- expected_answer_type
- expected_facts
- expected_tool
- expected_document_citations
- expected_safety_behavior
- expected_result

All expected document citations must resolve to real document IDs and sections.

Do not fabricate actual evaluation scores.

---

## PHASE 7 — GENERATOR AND VALIDATOR

Create deterministic scripts:

- `scripts/generate_data.py`
- `scripts/validate_data.py`

Adjust paths only when required by the approved architecture.

### Generator requirements

- Fixed random seed.
- Reproducible output.
- Configurable base date.
- Referential integrity.
- Safe handling of existing files.
- No overwriting unrelated application files.

### Validator requirements

Validate:

1. Required record counts.
2. Unique primary identifiers.
3. Foreign-key integrity.
4. Booking-to-passenger references.
5. Booking-to-train references.
6. Train running-day validity.
7. Valid station routes.
8. Correct stop ordering.
9. Seat capacity consistency.
10. Refund settings and policy consistency.
11. Circular supersession validity.
12. Future-effective circular handling.
13. Outdated FAQ references.
14. Evaluation category counts.
15. Document and section citations.
16. Action ownership and booking references.
17. Action expiry timestamp validity.
18. No real passenger PII.

Critical validation errors must return a non-zero exit code.

Never report tests as passed unless they actually ran.

---

## PHASE 8 — DOCUMENTATION

Generate:

### `docs/data-dictionary.md`
- Dataset descriptions.
- Field descriptions.
- Types.
- Relationships.
- Enumerated values.

### `docs/data-sources-and-limitations.md`
- Synthetic-data disclaimer.
- Fictional-policy disclaimer.
- Assumptions.
- Limitations.

### `docs/data-generation-report.md`
- Actual record counts.
- Files generated.
- Validation results.
- Edge-case IDs.
- Known limitations.

### `docs/ai-prompts.md`
- Exact generation prompt.
- Actual Claude model used.
- Generation date.
- AI-generated files.
- Manual validation performed.
- Known limitations.

Never invent model names or claim validation that did not occur.

---

## PHASE 9 — QUALITY REQUIREMENTS

- Follow approved architecture v1.2.
- Follow approved API contracts v1.2.
- Follow official table names and column names.
- Ensure all datasets are internally consistent.
- No contradictory policy values unless intentionally versioned.
- No missing document references.
- No placeholder datasets.
- No real passenger information.
- Keep the dataset lightweight for MacBook Air M4, 256GB.
- Avoid unnecessary dependencies.
- Do not implement RAG.
- Do not implement backend business logic.
- Do not implement frontend.
- Do not implement LLM orchestration.
- Do not modify architecture or API contracts.

---

## PHASE 10 — FINAL EXECUTION

After generation:

1. Run the data generator.
2. Run the independent validator.
3. Fix all critical validation failures.
4. Run validation again.
5. Report actual record counts.
6. Report actual validation results.
7. List every generated file.
8. List edge-case IDs.
9. List known limitations.
10. Show Git status.

Do not commit, push, merge or switch branches.

Wait for explicit approval before any Git operation.

### FINAL GOAL

Deliver a complete, reproducible, internally consistent and validated synthetic data kit that Backend, RAG, AI/LLM, Frontend and Testing modules can consume without schema, policy or reference conflicts.
~~~

### Deviation from the prompt, recorded (not silent)

The prompt's Phase 7 names the scripts `scripts/generate_data.py` /
`scripts/validate_data.py`. The approved architecture (`docs/
architecture.md` §6) already defines `data/generator/` and
`data/validate/` as the canonical, Data & Testing–owned locations for
exactly this purpose (and Phase 0 had already created those
directories). Per the prompt's own instruction — "adjust paths only
when required by the approved architecture" — the scripts were placed
at `data/generator/generate_data.py` and `data/validate/
validate_data.py` instead of under a new top-level `scripts/`.

## AI-generated files (this phase)

* `data/documents/INDEX.md` and all 38 files under `data/documents/
  {rules,circulars,faqs}/` — drafted directly, not script-generated.
* `data/generator/policy_values.py`, `data/generator/generate_data.py`,
  `data/generator/edge_cases.py`
* `data/validate/validate_data.py`
* `eval/eval_set.json`
* `db/seed_data.sql` — **generated output**, produced by running
  `generate_data.py`, not hand-written.
* `docs/data-dictionary.md`, `docs/data-sources-and-limitations.md`,
  `docs/data-generation-report.md`, this file.

All of the above were written by Claude Sonnet 5 in this session, from
the prompt quoted above, with no other input data source.

## Manual validation performed

**Automated validation:** `data/validate/validate_data.py` was
actually executed against the actual generated `db/seed_data.sql` in
this session (not simulated), 55 assertions, 0 failures on the final
run — see `docs/data-generation-report.md` for the full results and
the three real bugs that were found and fixed along the way.

**Human (user) review: not yet performed.** At the time of writing,
the user has not yet reviewed the specific document wording, the
exact policy figures, or the eval questions — they approved the
*master prompt that requested this generation*, not this output. That
review, and any requested changes, are expected as a follow-up step.
This is stated plainly here rather than implied, per the master
prompt's own instruction not to claim validation that did not occur.

**What the automated validation does and does not cover:** it checks
structure, referential integrity, numeric/effective-date consistency,
and that eval citations resolve to real document sections. It does
**not** independently fact-check the prose of the rules/circulars/FAQs
for tone, completeness, or policy "common sense" beyond what the 18
checks test — that is squarely a human-review step, still pending.

## Known limitations

See `docs/data-sources-and-limitations.md` for the full list (seats-
table reconciliation scope, no live delay data, formula-based fares,
empty `chunk_vectors`, unconsumed additive front-matter fields, and
the exact scope of automated vs. human validation).
