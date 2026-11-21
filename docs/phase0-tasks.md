# Phase 0 – Skeleton, Contracts, Schema (two-hour MVP scope)

**Status: TASK PLAN ONLY – nothing here has been executed.** Implements architecture v1.1 / api-contracts v1.1. Out of scope for Phase 0: any tool logic, refund math, RAG, LLM, UI behaviour, data generation, Docker, eval.

**Exit criteria (all must hold):**
1. Repo skeleton merged to `main`; all five feature branches rebased on it.
2. `app/contracts/` importable; every model/Protocol mirrors api-contracts.
3. `db/schema.sql` creates an empty DB containing all 10 mandatory tables (+ approved extras) with no errors.
4. A FastAPI app boots with all 7 routes returning contract-shaped **stub** responses; `/health` returns 200.
5. Contract round-trip tests pass (examples in api-contracts parse into the models).

**Dependencies for Phase 0 (installed only once you approve execution):** `fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`. Nothing else (no Streamlit, FAISS, torch, Ollama client yet).

**Git flow:** Backend does Phase 0 on a short-lived branch `phase0/skeleton` off `main`, PR → `main`; the other four then `git merge main` into their feature branches. Nothing is committed or pushed until you say so.

---

## Timeline (120 min)

| Min | Backend | Data & Testing | AI/LLM | RAG | Frontend |
|---|---|---|---|---|---|
| 0–20 | T1 skeleton | T5 schema draft | read contracts, flag issues | read contracts, flag issues | read contracts |
| 20–60 | T2 contracts (lead), T3 stubs | T5 finish, T6 settings keys | T2 review: §6–§8 types | T2 review: §7 types | T9 stub-server fixtures |
| 60–90 | T4 app wiring, T7 tests | T8 DB-create check | T10 MockClient *interface only* | T11 doc-format sample check | T9 continue |
| 90–120 | Integrate, merge | Review schema vs contracts | Rebase | Rebase | Rebase |

---

## Tasks

### T1 – Repository skeleton (Backend, ≤20 min)
Create empty packages and placeholder files only:
```
app/__init__.py  main.py  config.py
app/contracts/{__init__,schemas,interfaces,enums,settings_keys}.py
app/{api,tools,actions,handoff,privacy,audit,db,rag,llm}/__init__.py
ui/  data/{documents,generator,validate,prompts}/  eval/  tests/{unit,integration,e2e}/  db/
pyproject.toml (or requirements.txt)  .env.example  README.md (skeleton)
```
`.gitignore`: add `*.db`, `*.sqlite*`, `*.faiss`, `.streamlit/secrets.toml`, `node_modules/`, `.ruff_cache/`.
`config.py`: reads `MOCK_LLM, DB_PATH, OLLAMA_URL, LLM_MODEL, EMBED_MODEL, TZ_NAME, TRACE_STORE_PROMPTS`.
**Accept:** tree matches architecture §6; `python -c "import app"` works.

### T2 – Shared contracts (Backend lead; AI/LLM + RAG review; ≤40 min)
Files: `enums.py`, `schemas.py`, `interfaces.py`. Pydantic v2 models / `typing.Protocol`:
* Enums per api-contracts §3.
* HTTP models: `ChatRequest`, `ChatResponse` (guide §6.1 exact + optional `conflicts`, `language`), `SourceRef`, `ToolCall`, `PendingActionRef`, `HandoffRef`, `ConfirmResponse`, `CancelResponse`, `BookingView`, `IngestRequest` (with `SettingsChange` requiring name/value/effective_from/source_doc), `IngestResponse`, `TraceRecord`, `ErrorBody`, `HealthResponse`.
* Domain models: `PassengerContext`, `StationMatch`, `TrainSearchResult`, `Availability`, `FareQuote`, `RefundQuote`, `CancelEligibility`, `BookingSpec`, `PendingAction`, `ConfirmResult`, `HandoffRecord`, `SessionState`.
* RAG models: `RetrievalResult`, `Passage`, `Conflict`, `IngestDoc`.
* LLM models: `ParsedIntent`.
* Protocols: `ToolRegistry`, `ActionService`, `HandoffService`, `SessionStore`, `Retriever`, `LLMClient`, `Orchestrator`, `Clock`, `TraceRecorder`.
* Constraints in models: money as `int`, datetimes timezone-aware, `answer_type` enum, clarification cap constant `MAX_CLARIFICATIONS = 2`.
**Accept:** each JSON example in api-contracts parses with `model_validate`; no logic beyond validation.

### T3 – Stub implementations of interfaces (Backend, ≤20 min)
Fake `ToolRegistry`/`Retriever`/`Orchestrator` returning canned, contract-valid objects, in `tests/fakes/`. **No business logic.** Lets AI/LLM, RAG and Frontend develop independently.

### T4 – FastAPI wiring with stub routes (Backend, ≤20 min)
`app/main.py` + `app/api/*`: all 7 endpoints; header → `PassengerContext` dependency (401 if missing); error model; routes call the fakes. `/health` real.
**Accept:** `GET /health`=200; `POST /chat` returns the §4.1 example shape; `confirm` twice returns `idempotent_replay` on 2nd (stub state); foreign booking → 404 same body as missing.

### T5 – SQLite schema (Data & Testing draft, Backend review; ≤40 min)
`db/schema.sql`, `PRAGMA foreign_keys=ON`, `strftime`-free (times stored as ISO text). Mandatory tables and columns exactly as guide §4.2, plus:

| Table | Additive columns / notes |
|---|---|
| `stations` | guide columns only |
| `trains` | guide columns |
| `train_stops` | guide columns; PK `(train_no, stop_order)` |
| `fares` | guide columns; PK `(train_no, class, from_code, to_code)` |
| `seats` | + `capacity`, `rac_capacity` (O4); PK `(train_no, journey_date, class)` |
| `passengers` | guide columns |
| `bookings` | guide columns; `status` CHECK in BookingStatus values; index `(passenger_id)` |
| `booking_travellers` | guide columns; `status` CHECK `CNF/RAC/WL`; PK `(booking_id, traveller_name)` |
| `actions` | guide columns + `as_of` NOT NULL, `params_json`, `preview_json`, `trace_id` (D6) |
| `settings` | guide columns + `effective_from`, `effective_to`, `unit`; PK `(name, effective_from)` (D2) |

New tables (allowed: "you may add more"):
* `settings_history` – append-only audit (D2): `id, name, old_value, new_value, effective_from, source_doc, changed_at, trace_id, changed_by`; trigger or repository rule forbidding UPDATE/DELETE.
* `documents`, `chunks` (+ FTS5 virtual table `chunks_fts`), `chunk_vectors` – RAG.
* `traces` – `trace_id PK, passenger_id, endpoint, created_at, record_json`.
* `sessions` – `session_id PK, passenger_id, state_json, updated_at`.
* `handoffs` – `handoff_id PK, passenger_id, desk, summary, booking_id, session_id, created_at`.
**Accept:** `sqlite3 :memory: < db/schema.sql` succeeds; FTS5 available; every contract field backed by a column.

### T6 – Settings key registry (Data & Testing + Backend; ≤20 min)
`app/contracts/settings_keys.py`: dict `name → {type, unit, description, owner_doc}` for all key families in api-contracts §10, with bracket boundary note (inclusive, D4). **No values** (values come with rules docs in Phase 1).
**Accept:** every key referenced in contracts exists; naming consistent.

### T7 – Contract tests (Backend, ≤20 min)
`tests/unit/contracts/`: examples from api-contracts parse; `SettingsChange` missing any of four fields is rejected; naive datetime rejected; money float rejected; clarification cap constant exists.

### T8 – Schema smoke test (Data & Testing, ≤15 min)
`tests/unit/db/test_schema.py`: schema applies to a fresh DB; mandatory table/column names present (checks against the guide's list); constraint checks (status CHECKs, FK).

### T9 – Frontend stub (Frontend, ≤30 min)
Fixture JSON for each `answer_type` copied from contracts into `ui/fixtures/`; a stub server (or the Backend stub app) so Phase 1 UI work does not wait. **No Streamlit code required in Phase 0** beyond confirming the dev-server approach.

### T10 – Interface review sign-offs (AI/LLM, RAG, ≤15 min each)
Each owner confirms in writing (PR comment) that their Protocol signatures are implementable; changes allowed only now, per architecture §8 rule 2.

### T11 – Sample document check (RAG + Data, ≤15 min)
Hand-write **one** tiny sample document in the §5.1 format only inside a test fixture (not part of the dataset) to prove the parser contract is unambiguous. No dataset generation.

---

## Definition of done and hand-off
* Backend runs the tests, opens PR `phase0/skeleton`; all five owners approve (shared-file rule).
* Merge to `main`; the four other worktrees merge `main`.
* Phase 1 starts: Data begins documents/generator; Backend tools; RAG index; AI/LLM mock orchestrator; Frontend Streamlit.

## Risks specific to Phase 0
* Over-modelling: keep contracts to what appears in api-contracts; resist adding fields.
* Schema churn: freeze column names before Phase 1; additive columns later via PR.
* Time: if T2 overruns, ship `enums.py` + HTTP models first; domain models can land at minute 120 before Phase 1 consumes them.
