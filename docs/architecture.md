# Ujjwal Rail – Architecture Proposal

**Status: APPROVED with amendments (v1.2). No application code exists yet.** v1.1 incorporated decisions D1–D8 (§3.1); v1.2 finalizes D2 (document ingestion vs. settings updates are independent, never inferred from text) and D6 (business `as_of` vs. operational expiry clock are two separate, distinct mechanisms).
Source of truth for requirements: `docs/AI-Powered_Train_Travel_Assistant_for_Bookings_Refunds_and_Journey_Help.docx` (the guide). Section numbers (§) and requirement IDs (R1–R12) below refer to it. Companion document: [api-contracts.md](api-contracts.md).

---

## 1. Repository analysis

### 1.1 Current state

| Item | Finding |
|---|---|
| Commits | One: `0afd336 chore: initialize Ujjwal Rail hackathon project` |
| Tracked files | `.gitignore`, and two files in `docs/` |
| `docs/AI-Powered_Train_Travel_Assistant_…Journey_Help.docx` | Official participant guide (31 KB of text) |
| `docs/problem_statement.docx` | **Byte-for-byte identical text** to the file above (verified by diff of extracted text). A duplicate, not a second document |
| `README.md` | **Missing** (a graded deliverable) |
| Application code, tests, data, Docker files | **None.** Nothing is implemented |
| `.gitignore` | Python-oriented. Ignores `.env*` (keeps `.env.example`), venvs, caches. Does **not** yet ignore `*.db`/`*.sqlite`, FAISS/index files, `node_modules`, `.streamlit/secrets.toml`, model caches |
| Branches | `main`, `feature/rag` (also on `origin`), and local-only `feature/ai-llm`, `feature/backend`, `feature/data-testing`, `feature/frontend` – all at `0afd336` |
| Worktrees | Five extra sibling worktrees already exist: `HCL_TECH_HACKATHON` (rag), `_AI_LLM`, `_BACKEND`, `_DATA_TESTING`, `_FRONTEND`, `_MAIN` (main). Branch-per-role is already in place |
| Working tree | Clean |

### 1.2 Completed work

Only repository scaffolding and the branch/worktree layout. **All 12 requirements, all 7 endpoints, all 10 tables and all 9 submission items are open.**

### 1.3 Remote status

Only `feature/rag` and `main` are on `origin`. The other four feature branches need pushing before teammates on other machines can see them (not done – you asked for no pushes).

---

## 2. Requirements baseline (nothing added, nothing dropped)

### 2.1 Behavioural requirements → owner

| Req | Summary | Primary owner | Supporting |
|---|---|---|---|
| R1 | Understand English/Hindi/Hinglish; extract stations, date, time, class, pax, booking | AI/LLM | Backend (station resolver) |
| R2 | Ask when unsure; ≤2 follow-ups in a row; never re-ask known slots | AI/LLM | Backend (session store) |
| R3 | Rules answers from documents, cite doc ID + section | RAG | AI/LLM (compose), Data (docs) |
| R4 | Search, seats, fares, refunds, deadlines, status come from code | Backend | AI/LLM (explain only) |
| R5 | Preview → separate confirm call → code change → verify | Backend | AI/LLM (propose), Frontend (buttons) |
| R6 | Newer circular / official rule beats old; record the clash | RAG | Backend (effective-dated settings) |
| R7 | Hand over complaints, disputes, safety, "human please", low confidence; with summary + booking details; no promised outcome | AI/LLM (decision) | Backend (handoff record) |
| R8 | Identity from header only; own bookings only; non-revealing refusals; mask phone/ID | Backend | AI/LLM (never given other data) |
| R9 | Retrieved/FAQ/user content is data, not orders | AI/LLM | RAG (flagging), Backend (structural limits) |
| R10 | Per-reply audit record with trace ID, replayable | Backend | everyone writes into it |
| R11 | `/ingest` visible to the very next answer, no restart; structured `settings_changes` (D2) | RAG (documents) | Backend (validated settings + history), Data (test) |
| R12 | Own eval set (≥30 Qs) + report of the §7 metrics | Data & Testing | all |

### 2.2 Fixed interface requirements

* **Endpoints (§6):** `POST /chat`, `POST /actions/{id}/confirm`, `POST /actions/{id}/cancel`, `GET /bookings/{id}`, `POST /ingest`, `GET /trace/{trace_id}`, `GET /health`.
* **Answer types (§6.2):** `answer`, `clarification`, `confirm_needed`, `action_done`, `handed_to_human`, `not_found`, `refusal`.
* **Change levels (§6.3):** 0 lookup · 1 own-booking change after confirm · 2 staff decides (file request, never promise) · 3 never (over-refund, waitlist promotion, fare change, someone else's booking).
* **Tables (§4.2):** `stations, trains, train_stops, fares, seats, passengers, bookings, booking_travellers, actions, settings` – names and key columns are mandatory (judges add their own data); extra columns/tables allowed.
* **Stack (§5):** Streamlit/web chat with Confirm + Cancel buttons · FastAPI · Ollama or approved hosted LLM with `MOCK_LLM=true` · embeddings (FAISS/Chroma) **plus** keyword search · SQLite · `docker compose up`. Swaps are allowed if justified in the README.
* **Minimum data (§4):** ≥12 rules docs, ≥6 circulars (≥2 changing earlier rules, ≥1 future-dated), ≥20 FAQs (≥2 outdated by a circular), settings table, a few Hindi/mixed docs; 15 stations, 25 trains, 14 days of seats, 25 passengers, 50 bookings in all five statuses, the listed awkward cases, a validation script.
* **Eval (§7):** ≥30 questions with the mandatory category counts; the 7 metrics reported honestly.
* **Disqualifiers (§10):** fabricated eval results; any booking/cancel without confirm; code sharing; real personal data; changes after freeze.

### 2.3 Submission checklist → owner

| Deliverable (§8) | Owner |
|---|---|
| Git repo, README, final tag | Backend (README skeleton), all contribute their section |
| `docker compose up` (API + UI + DB) | Backend |
| Rules/circulars/FAQs + doc-ID list | Data & Testing |
| Data kit: exact prompts, model name, generator, checker, one-page data note | Data & Testing |
| Eval set + results | Data & Testing |
| 3 sample audit records (incl. one full cancel preview→confirm→change→check) | Data & Testing (captures from Backend traces) |
| AI-tools disclosure note | everyone writes their part; Data & Testing assembles |
| Who built what | Data & Testing assembles |
| Signed original-work declaration per member | each member, individually |

> **Team-size note (D1):** the official guide §1 states "Up to 4 people"; the organizers separately permitted five contributors. The guide is quoted unchanged; the README states the permission.

---

## 3. Decisions and open items

### 3.1 Approved decisions (v1.1)

| # | Decision | Where it lands |
|---|---|---|
| D1 (was C1) | **Five contributors proceed.** Recorded discrepancy: the official guide (§1) says "up to 4 people"; the organizers separately permitted five. The guide is not altered and is quoted as-is. The README's "who built what" must state this permission. Each of the five still signs an individual declaration and must be able to explain the whole system (§9.4) | §2.3, §11 |
| D2 (was C3, C4) | **`/ingest` keeps document ingestion and settings updates as two distinct, independently-optional parts of one request.** `sections`/`markdown` (document text) and `settings_changes` (policy numbers) are separate fields with separate validation; **neither implies the other**. A text-only `/ingest` call (no `settings_changes`) stores and indexes the document and **never, under any circumstance, infers or changes a setting value from that text** – not by the LLM, not by any heuristic. Each `settings_changes` item **must** carry `name`, `value`, `effective_from`, `source_doc` (a registered doc ID); it is validated against the registered settings keys and applied atomically with the document write, and recorded in an append-only `settings_history` audit table. **The LLM never writes settings** – only this validated, explicit `/ingest` path and the Data & Testing seed script do. This is stated in the README so judges testing a text-only circular know the refund will not change unless `settings_changes` is also sent | api-contracts §5.2, §10 |
| D3 (was C5, part) | **At most two consecutive clarification questions** per session; the third turn must give a best-effort `answer`/`not_found`/hand-over | api-contracts §4.1, §8 |
| D4 (was C6) | **Cut-off boundaries are inclusive** unless a specific Ujjwal Rail policy document explicitly defines otherwise. Bracket lower bounds are inclusive: exactly 48h before departure belongs to the "48h or more" bracket. One convention applies consistently in the rules documents, `settings`, and Python; the Data & Testing oracle and Backend tests assert it at each threshold and at threshold −1 minute | api-contracts §10 |
| D5 (was C8, part) | **No automatic waitlist promotion.** Cancelling increments `available` only | api-contracts §9 |
| D6 (was C12) | **`as_of` is reserved exclusively for business calculation and policy evaluation** (refund amounts, cut-off brackets, which settings/circular apply, date resolution) – it is saved on the action at proposal and reused for the confirm-time recompute, so the quote cannot drift. **Action expiry is a separate, operational concern** on the real server clock: `expires_at` is computed and stored as an **actual UTC timestamp** at proposal time (`server_now_utc() + action_expiry_minutes`), and expiry is decided by comparing the **injectable clock's current UTC time** to that stored timestamp – never by `as_of`. The optional `as_of` override on confirm stays **removed** | api-contracts §4.2, §9 |
| D7 | Booking, seat, fare and refund calculations stay deterministic Python; the LLM never does arithmetic or edits money | §4 principles, api-contracts §6 |
| D8 | R1–R12 and module ownership boundaries are unchanged | §2, §7 |

### 3.2 Remaining open items (none block Phase 0)

| # | Item | Working default (used until told otherwise) |
|---|---|---|
| O1 (was C3 residual) | What judges send to `/ingest` is unknown. Per D2, a text-only circular (no `settings_changes`) **by design** changes no setting, so the refund will not reflect it until a `settings_changes` entry is also sent | Ask organizers at kickoff whether their live test sends `settings_changes` alongside the circular text, or expects us to seed the new rate ourselves before the demo. State the D2 behaviour plainly in the README and the demo script so it is never a surprise live |
| O3 (was C5, rest) | Booking needs traveller names/ages; R2 limits follow-ups | Ask ≤2 per turn for route/date/class/pax; first traveller defaults to the passenger's profile name; other travellers collected in one question at preview time |
| O4 (was C8, rest) | `seats` has no capacity | Add `capacity`, `rac_capacity` columns. New booking → CNF if `available>0`, else RAC if space, else WL |
| O5 (was C7) | Mixed CNF/WL booking cancellation | Cancel whole booking; refund = sum of per-traveller quotes |
| O6 (was C9) | Boarding-station change rules | Later stop on the same journey, before `boarding_change_cutoff_hours`, no fare adjustment |
| O7 (was C10) | "Very late" refunds have no delay data | Answer rule from documents; claim → hand-over. "Train cancelled by operator" is computed from status |
| O8 (was C11) | `/trace` and `/ingest` access | Trace readable by owning passenger; `/ingest` open but traced |
| O9 (was C13) | Seed data anchored to a date | Generator takes `--anchor-date`; seats re-based to today at start if outside window |
| O10 (was C14) | Hindi script | Reply in the passenger's script/style |
| O11 (was C15) | Guide's "triage tools / control plane / critic" wording | Not a requirement; not built |
| O12 (was C16) | Tatkal in booking | Tatkal answered from rules/settings; assistant books general quota only |

## 4. Design principles

1. **Simplest design that works.** One FastAPI process, one SQLite file, one orchestrator function. **No multi-agent framework.** The LLM does two jobs only: (a) turn text into a validated structured intent, (b) turn tool/doc results into a reply. That is the answer to "why did you do it this way?".
2. **Code decides, LLM explains.** All money, dates, seat counts, deadlines and statuses are computed in Python from SQLite + `settings`. A post-generation guard rejects any ₹ amount, fare, date or train number in the reply that is not present in a tool output.
3. **The LLM cannot act.** It can only emit an intent (enum + typed slots). Mutations go through `propose → /confirm`, and `/confirm` does not call the LLM at all.
4. **Identity is injected, never inferred.** `passenger_id` comes from `X-Passenger-Id` and is added to every tool call by the server; it is not a tool parameter the LLM can fill in.
5. **Content is data.** User text and retrieved passages are placed in delimited data blocks; no component executes instructions found in them. The safety property is structural (above), not a prompt-only filter.
6. **Config in one place.** Every number from the rules lives in `settings` with `source_doc`; code never hard-codes a charge or cut-off.
7. **Mock-first.** `MOCK_LLM=true` runs the whole system with deterministic rule-based intent parsing and templated replies, so Backend, Frontend and Data work needs no model.

---

## 5. System architecture

```
 Streamlit UI ──HTTP──▶ FastAPI (app/main.py)
 (Frontend)               │  X-Passenger-Id → PassengerContext
                          ▼
                 ┌──────────────────┐
  /chat ────────▶│  Orchestrator    │  (AI/LLM)  intent → policy → tools/RAG → compose → guards
                 └───┬────────┬─────┘
          calls      │        │ calls
        ┌────────────▼──┐  ┌──▼───────────────┐
        │ Tool layer    │  │ RAG              │
        │ (Backend)     │  │ ingest/retrieve  │
        │ search, fare, │  │ FTS5 + vectors,  │
        │ refund, status│  │ effective-date   │
        │ actions, hand-│  │ + supersession   │
        │ off, privacy  │  └──┬───────────────┘
        └──────┬────────┘     │
               ▼              ▼
          SQLite (one file): domain tables · settings · documents/chunks · actions · traces · sessions
 /actions/{id}/confirm|cancel, /bookings/{id}, /ingest, /trace, /health ─▶ Backend / RAG (no LLM involved)
```

### 5.1 Request flows

**Lookup (Level 0)** – `/chat` → orchestrator parses intent (LLM) → backend tool runs with injected `passenger_id` → composer writes reply from tool output → number guard → trace saved → `answer`.

**Rules question** – intent `rules_question` → `rag.retrieve(query, as_of)` returns passages already filtered by `effective_from ≤ as_of` and ordered newer-wins, plus any recorded `conflicts` → composer cites `doc_id` + `section` → `answer`.

**Change (Level 1)** – intent `cancel_booking | book_ticket | change_boarding` → backend `actions.propose()` validates ownership, allowed-ness and computes the preview (refund/fare) in code → `confirm_needed` with `pending_action`. Passenger presses Confirm → `POST /actions/{id}/confirm` (no LLM) → compare-and-swap to `executing` → apply in a DB transaction → re-read booking and verify → `action_done`. A second confirm replays the stored result.

**Hand-over (Level 2)** – intent/rule triggers → backend `handoff.create(desk, summary, booking_details)` → `handed_to_human`. No outcome is promised.

**Level 3** – policy layer maps these intents straight to `refusal`; no tool is called.

### 5.2 Retrieval design (lightweight)

* Documents stored as sections; each section is one retrieval chunk carrying `doc_id, section, doc_type, effective_from, supersedes, language`.
* Hybrid score: SQLite **FTS5** (BM25, no extra dependency) + vector similarity, fused (e.g. reciprocal-rank fusion).
* Embeddings: via the Ollama embeddings endpoint (small model) rather than a torch/sentence-transformers install. Vectors held in SQLite and searched in memory (a few hundred chunks – FAISS-flat or plain NumPy is equally fine; interface hides which). Under `MOCK_LLM=true`, embeddings fall back to keyword-only.
* R11: ingest writes the chunk, FTS row and vector in one transaction and updates the in-memory index – no restart.
* R6: a pre-ranking filter drops chunks not yet effective or superseded as of `as_of`; if both an old and a new chunk match, the old one is excluded from the answer set and the pair is written to `conflicts` (and the trace). Official rule/circular outranks `FAQ` when they disagree.
* R9: passages matching instruction-like patterns are flagged `suspicious` (kept as data, flagged in trace, never concatenated outside the data delimiter).

### 5.3 LLM design

* `LLMClient` protocol with `OllamaClient`, optional hosted client, and `MockClient`.
* Intent extraction returns JSON validated by a Pydantic model; an invalid result is retried once, then falls back to `clarification` or `not_found`, never to guessing.
* Language detection (en/hi/hinglish) drives the reply language; mock mode uses simple script/keyword detection.
* Prompts are versioned files in `app/llm/prompts/` so Data & Testing can quote them verbatim in the data kit/eval notes where relevant.

---

## 6. Repository layout and ownership

```
app/
  main.py                    FastAPI app + router wiring                 [SHARED-FROZEN after Phase 0; Backend edits via PR]
  config.py                  env/settings loader (MOCK_LLM, DB_PATH …)   [SHARED-FROZEN]
  contracts/                 Pydantic schemas + Protocols                [SHARED-FROZEN – see §8]
    schemas.py  interfaces.py  enums.py  settings_keys.py
  api/                       routers: chat, actions, bookings, ingest, trace, health   [Backend]
  tools/                     deterministic tools                          [Backend]
    stations.py timetable.py availability.py fares.py refund.py deadlines.py booking_status.py
  actions/                   propose / confirm / cancel / idempotency      [Backend]
  handoff/                   desk routing + record                         [Backend]
  privacy/                   passenger context, ownership checks, masking  [Backend]
  audit/                     trace writer / reader                         [Backend]
  db/                        connection, migrations loader, repositories   [Backend]
  rag/                       parse, chunk, index, retrieve, supersession   [RAG]
  llm/                       clients, mock, prompts, intent, compose,
                             orchestrator, guards, language, handoff_policy [AI/LLM]
ui/                          Streamlit app                                 [Frontend]
db/schema.sql                canonical DDL (mandatory tables + extras)     [SHARED-FROZEN; Data & Testing drafts, all approve]
data/
  documents/{rules,circulars,faqs}/   LLM-drafted, human-edited docs       [Data & Testing]
  generator/ validate/        generator + checker scripts                  [Data & Testing]
  prompts/                    exact generation prompts + model note        [Data & Testing]
eval/                         eval set, runner, report                     [Data & Testing]
tests/
  unit/<module>/              owned by each module's owner
  integration/ e2e/           [Data & Testing]
docker-compose.yml  Dockerfile(s)  pyproject/requirements  .env.example  README.md   [SHARED-FROZEN, Backend integrates]
docs/                         architecture.md api-contracts.md + submission notes
```

---

## 7. Module responsibilities

### 7.1 RAG Engineer (`feature/rag`, `app/rag/`)
* Document file parser (front-matter format defined in api-contracts §5.1), section chunker, doc registry.
* FTS5 + vector index, fusion, `retrieve()` implementing the `Retriever` protocol.
* Effective-date filtering, supersession, FAQ-vs-official precedence, **conflict records** (R6).
* `ingest()` for create/update with immediate availability (R11); idempotent on `doc_id`+version.
* Suspicious-passage flagging (R9 input).
* Hindi / mixed-language retrieval quality (query normalisation, Devanagari tokenisation in FTS5).
* **Does not:** call the LLM for answers, compute any amounts, write settings.
* Tests: ranking on a hand-built mini corpus, supersession, future-dated circular excluded until effective, ingest-then-retrieve without restart.

### 7.2 Backend Engineer (`feature/backend`, `app/api, tools, actions, handoff, privacy, audit, db`)
* FastAPI app, all 7 endpoints, error model, request validation, header → `PassengerContext`.
* **All deterministic logic:** station resolver (aliases, similar names), train search (running days, after-midnight via `day_offset`, time-of-day filter), availability, fare lookup, `refund_quote`, `can_cancel`/deadlines, booking status, settings reader with effective dating.
* Actions: propose → confirm → verify with compare-and-swap idempotency; expiry on the real server clock against a stored `expires_at` UTC timestamp; ownership and Level 3 refusals; re-validation at confirm using the `as_of` saved on the action for the business recompute (D6, two separate clocks); append-only `settings_history`, explicit settings-changes validation on ingest, independent of document text (D2).
* Hand-over records; session store; trace store; privacy masking.
* Docker/Compose, README skeleton, `/health`.
* **Does not:** call the LLM, parse natural language.
* Tests: refund at every cut-off ±1 minute, midnight departure dates, double confirm, cross-passenger access, mixed CNF/WL booking.

### 7.3 AI/LLM Engineer (`feature/ai-llm`, `app/llm/`)
* `LLMClient` (Ollama, optional hosted, **MockClient**), prompt files.
* Intent + slot extraction (R1), slot memory across turns, ≤2 follow-ups (R2), language handling (Hindi/Hinglish).
* Orchestrator: policy level mapping (0–3), tool/RAG calls via the shared interfaces, composition with citations (R3), conflict mention (R6).
* Guards: number/ID/train-no verification against tool outputs; prompt-injection hygiene (data delimiters, intent enum constraint); no passenger_id from the LLM (R8, R9).
* Hand-over decision (R7): complaint, refund dispute, safety/harassment, "human please", low confidence, with a ≤3-line summary; avoid handing over answerable questions.
* **Does not:** compute money/dates, touch SQL, write to the DB (except through Backend interfaces).
* Tests: intent parsing table (en/hi/hinglish), injection corpus, follow-up cap, mock-mode determinism.

### 7.4 Frontend Engineer (`feature/frontend`, `ui/`)
* Streamlit chat bound to `/chat`; passenger selector sends `X-Passenger-Id`; `session_id` management; optional `as_of` control for demos.
* Renders `answer_type`, sources, tool outputs (collapsible), trace ID link, handover banner.
* **Confirm / Cancel buttons** for `confirm_needed`, calling the two action endpoints; shows `action_done` verification; expired/duplicate states.
* Developer panel: ingest a circular, view `/trace/{id}`, `/health`.
* Works against a **stub server** built from the contract examples until Backend lands.
* **Does not:** compute anything, hold secrets, bypass the API.

### 7.5 Data & Testing Engineer (`feature/data-testing`, `data/`, `eval/`, `tests/integration|e2e`, `db/schema.sql` draft)
* Drafts canonical `db/schema.sql` (mandatory tables/columns + approved extras).
* Writes (LLM-drafted, human-edited) ≥12 rules, ≥6 circulars, ≥20 FAQs, settings seed with `source_doc`, Hindi/mixed content, outdated-FAQ pairs.
* Generator (stations, trains, stops, fares, seats, passengers, bookings, awkward cases) and **checker script**; exact prompts + model name recorded.
* Eval set (≥30 Qs, category quotas from §7), eval runner producing the 7 metrics, honest report; refund hand-calculation oracle independent of the Backend code.
* Integration/E2E tests, sample audit-record capture, submission notes (data note, AI-tools disclosure, who-built-what).
* **Does not:** change application logic; reports defects to the owner.
* *Starts only after approval – no data is generated in this analysis phase.*

---

## 8. Shared files and change protocol

These are changed **only** by a PR that all five contributors have acknowledged (in practice: post in the team chat, wait for 👍 from each module owner). Never edit them directly on a feature branch as part of other work.

| File / area | Why frozen | Proposer typically |
|---|---|---|
| `docs/api-contracts.md`, `docs/architecture.md` | The agreement | any |
| `app/contracts/*` (schemas, enums, Protocols, settings keys) | Every module imports them | owner of the affected side |
| `db/schema.sql` | Mandatory table/column names; all modules query it | Data & Testing |
| `app/main.py`, `app/config.py`, `.env.example` | Wiring and env names | Backend |
| `docker-compose.yml`, `Dockerfile*`, `pyproject.toml`/`requirements*.txt` | One dependency set, light footprint | Backend |
| `README.md` | Judged deliverable; single voice | Backend, sections from each |
| `.gitignore` | Repo hygiene | Backend |
| `data/documents/**` doc IDs (`RUL-*`, `CIR-*`, `FAQ-*`) and `settings_keys` | Citations and code both depend on them | Data & Testing |

Rules:
0. **Never edit the official guide** (`docs/*.docx`); the five-contributor discrepancy (D1) is recorded only in our own documents.
1. Additive contract changes (new optional field, new enum value) → announce + PR, others adapt.
2. Breaking changes (rename/remove) → only before Phase 2 ends; afterwards require unanimous agreement.
3. Each person edits only their owned paths. Cross-module needs go through the interface, or a request to the owner.
4. Merge into `main` via PR; Backend is integration owner and runs the full test suite before merging.
5. Each dependency added must be justified by its owner (footprint matters, §10).

---

## 9. Integration sequence and dependencies

```
Phase 0  Contracts freeze (~45 min, all)
           approve docs · skeleton · contracts/ · schema.sql · .env.example · settings key names
Phase 1  Parallel build against interfaces/fakes (to checkpoint, ~3.5 h)
           Data:     schema, rules/circulars/FAQs, settings seed, generator+checker
           Backend:  db layer, tools, refund fn, actions, endpoints, traces (tiny hand fixtures first)
           RAG:      parser, index, retrieve, ingest (on 3–4 hand-written sample docs)
           AI/LLM:   MockClient, intent parsing, orchestrator against fake tools/retriever
           Frontend: UI against stub server returning contract examples
Phase 2  Vertical slice 1 (checkpoint): "trains Pune→Nagpur after 6pm" + "can I carry a pet?"
           needs: seed DB + docs (Data), search tool (Backend), retrieve (RAG), orchestrator (AI/LLM), UI
Phase 3  Refund + cancel with preview/confirm/verify, idempotency, Level 3 refusals
Phase 4  Booking, boarding change, hand-over, privacy refusals, injection tests, Hindi/Hinglish, R11 live ingest + circular→settings via validated `settings_changes` (D2)
Phase 5  Eval run & honest report, audit samples, docker compose on clean checkout, README, notes
Freeze   Tag; no changes after.
```

| Consumer | Depends on | Blocking artefact |
|---|---|---|
| Backend tools/tests | Data: schema + seed (or own mini fixtures) | `db/schema.sql` |
| AI/LLM orchestrator | Backend tool interfaces; RAG retriever | `app/contracts/interfaces.py` (fakes meanwhile) |
| RAG | Data: documents in the front-matter format | document format §5.1 |
| Frontend | `/chat` + action contracts | contract examples (stub meanwhile) |
| Eval | Everything running | Phase 4 complete |
| Docker | all modules importable | Phase 3+ |

Critical path: **contracts → schema/seed → Backend tools → orchestrator → eval**. RAG and Frontend are off the critical path until Phase 2.

---

## 10. Resource budget (MacBook Air M4, 256 GB)

* Avoid `torch`/`sentence-transformers` (multi-GB). Use FTS5 + Ollama's embedding endpoint (a few hundred MB model) or the keyword-only fallback.
* LLM: one small instruct model (≈3–8B, 4-bit; a few GB) on the **host** via Ollama, reached from containers via `host.docker.internal`; model name is an env var, not hard-coded. Check Hindi quality on the eval set before choosing; fall back to `MOCK_LLM=true` for development.
* SQLite single file; data volume is tiny (25 trains, 50 bookings, ~40 documents).
* Compose = two small Python containers (API, Streamlit). No Redis, vector-DB server, queue or Postgres.
* Docker Desktop disk image is capped; keep images slim (`python:3.x-slim`), single shared base layer.

---

## 11. Key risks

| Risk | Mitigation |
|---|---|
| Judge ingests a text-only circular, so settings do not change (O1) | Support `settings_changes` (D2); ask organizers what judges send; test in Phase 4 |
| Small local model weak at Hindi/JSON | Strict schema + one retry, rule-based fallback, mock mode, eval Hindi cases early |
| Time zones / midnight trains | Single `Asia/Kolkata` convention, `day_offset`, dedicated tests (api-contracts §2) |
| Confirm race / double submit | CAS on action status + stored result replay |
| Merge conflicts on shared files | §8 protocol, contracts frozen in Phase 0 |
| Five contributors vs guide's "up to 4" (D1) | Organizers permitted five; record in README; keep the permission message to hand |
| Everyone must explain everything (§9.4) | Short design walkthrough per module before freeze |

---

## 12. Status and next step

Approved with amendments D1–D8, finalized in v1.2 (business/operational clock split, explicit settings-change field – see top of this document and api-contracts.md). No hard blockers remain; open items O1, O3–O12 (§3.2) have working defaults, of which **O1** (what judges actually send to `/ingest`) deserves confirmation at kickoff. Phase 0 tasks are in [phase0-tasks.md](phase0-tasks.md).
