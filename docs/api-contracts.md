# Ujjwal Rail – API & Module Contracts

**Status: APPROVED with amendments (v1.2) – specification only, no code exists.** Decisions D1–D8 are in architecture §3.1; v1.2 finalizes D2 (ingest: document text and settings updates are independent, never inferred) and D6 (business `as_of` vs. operational expiry clock are two distinct mechanisms, never mixed). Read with [architecture.md](architecture.md). Items marked **(D#)** implement an approved decision, **(O#)** rest on an open item with a working default (architecture §3). Anything marked *additive* is an extra optional field layered on the guide's contract; the guide's own fields and names are never altered.

Once approved, this file and `app/contracts/` (Pydantic models + Protocols that mirror it) are **frozen** – see architecture §8.

---

## 1. Scope

* Part A (§4–§5): the public HTTP contract judges script against (guide §6).
* Part B (§6–§9): internal Python interfaces between the five modules.
* Part C (§10–§12): shared data conventions – settings keys, trace record, privacy.

Code snippets are *interface specifications*, not implementations.

---

## 2. Conventions

| Topic | Rule |
|---|---|
| Time zone | All instants are ISO-8601 with offset, canonical zone **Asia/Kolkata (+05:30)**. Naive datetimes are rejected |
| `as_of` | Optional on `/chat`; defaults to server "now" at the moment the chat request is received. **Business/policy computations only** (refund hours, cut-off brackets, which circular/settings row applies, resolving "tomorrow") use `as_of`, never `datetime.now()` directly. **Action expiry does not use `as_of` at all** — it is a separate operational concern on the real clock; see §4.2 and the `Clock` protocol (§6, two distinct clocks: a resolved business `as_of` value, and an injectable `Clock.now_utc()` for operational timestamps) |
| Journey date vs time | Stored separately: `journey_date` = `YYYY-MM-DD` of **the train's origin-station departure date**. Stop times are `HH:MM` + `day_offset` (days after origin departure). Boarding-station departure instant = `journey_date + day_offset days + departure` |
| After-midnight trains | A train leaving 00:30 on "Saturday" has `journey_date` of the day its journey *starts* per the data; the assistant must state the calendar date and time back to the passenger when ambiguous ("tomorrow" resolution is explicit in the preview) |
| Money | Integer rupees (INR). No floats anywhere in money fields; displayed as `Rs 1,840` |
| IDs | `booking_id` `UR-<digits>` · `action_id` `ACT-<digits>` · `trace_id` 8 hex chars · `doc_id` `RUL-*`, `CIR-*`, `FAQ-*` · `handoff_id` `HND-<digits>` |
| Station codes | Upper-case code from `stations.station_code`; free text is resolved by the Backend station resolver, never by the LLM |
| Languages | `en`, `hi`, `hinglish` |
| Content type | JSON, UTF-8 (Devanagari must round-trip) |
| Identity | Header `X-Passenger-Id`. Never taken from the body or message text |
| Errors | See §2.1 |

### 2.1 Error model (non-2xx only)

```json
{ "error": { "code": "not_found", "message": "Human readable, non-revealing", "trace_id": "b17e40c2" } }
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `bad_request` | Validation failure, naive datetime |
| 401 | `unauthenticated` | Missing/unknown `X-Passenger-Id` |
| 404 | `not_found` | Resource missing **or owned by someone else** (identical body in both cases – R8) |
| 409 | `conflict` | Action not in a state that allows the call (e.g. cancel after confirm) |
| 410 | `expired` | Action past `expires_at` |
| 422 | `rule_violation` | Change not allowed by the rules (Level 3) on a direct endpoint call |
| 500 | `internal` | Unexpected; trace still written |

Chat-level refusals (out of scope, someone else's booking) are **200** with `answer_type: "refusal"`, not an HTTP error.

---

## 3. Shared enums

```python
AnswerType  = "answer" | "clarification" | "confirm_needed" | "action_done"
            | "handed_to_human" | "not_found" | "refusal"

ActionType  = "book_ticket" | "cancel_booking" | "change_boarding_station"
ActionStatus= "proposed" | "executing" | "done" | "failed" | "cancelled" | "expired"
TravellerStatus = "CNF" | "RAC" | "WL"                       # booking_travellers.status
BookingStatus   = "confirmed" | "rac" | "waitlisted" | "cancelled" | "train_cancelled_by_operator"
ChangeLevel = 0 | 1 | 2 | 3                                   # guide §6.3
Intent      = "find_train" | "check_seat" | "get_fare" | "booking_status" | "refund_quote"
            | "can_cancel" | "rules_question" | "book_ticket" | "cancel_booking"
            | "change_boarding_station" | "complaint_or_dispute" | "safety_report"
            | "human_request" | "other_booking_or_person" | "out_of_scope"
            | "smalltalk" | "unclear"
Desk        = "complaints" | "refunds" | "safety" | "concessions" | "general"
```

`BookingStatus` mapping to the guide's wording: confirmed, RAC, waitlisted, cancelled, "train cancelled by operator". A booking's status is derived/stored; traveller rows carry CNF/RAC/WL individually.

---

## 4. HTTP endpoints (Backend owns all; guide §6)

### 4.1 `POST /chat`

Headers: `X-Passenger-Id: <passenger_id>` (required), `Content-Type: application/json`.

```json
// ChatRequest
{ "session_id": "sess-123", "message": "Cancel my ticket for tomorrow", "as_of": "2026-12-03T08:15:00+05:30" }
```
`as_of` optional. A `session_id` is bound to the first passenger that uses it; reuse by another passenger returns 404 `not_found`.

```json
// ChatResponse – exactly the guide's §6.1 shape
{
  "trace_id": "b17e40c2",
  "answer_type": "confirm_needed",
  "answer": "Cancelling booking UR-30418 (12123, Pune to Nagpur, 5 Dec, 2AC, 1 seat) now gives you a refund of Rs 1,840. Shall I go ahead?",
  "sources": [ { "doc_id": "RUL-CAN-01", "section": "3. Refund table" },
               { "doc_id": "CIR-2026-07", "section": "Revised charges" } ],
  "tools":   [ { "tool": "refund_quote",
                 "output": { "amount_paid": 2040, "charge": 200, "refund": 1840, "hours_before_departure": 51 } } ],
  "pending_action": { "action_id": "ACT-0091", "type": "cancel_booking", "booking_id": "UR-30418",
                      "expires_at": "2026-12-03T10:15:00+05:30" },
  "handed_to_human": null
}
```

Field rules:

| Field | Rule |
|---|---|
| `answer_type` | One of §3 |
| `sources` | `[]` allowed (tool-only answers). Every document-derived claim has an entry. `section` is the section heading string from the document |
| `tools` | Every deterministic tool executed this turn, with its raw output. Money/date/seat/train facts in `answer` must appear here (enforced by the answer guard) |
| `pending_action` | Non-null **only** for `confirm_needed` |
| `handed_to_human` | `null` or `{ "handoff_id", "desk", "summary", "booking_id": null\|"UR-…" }` – non-null only for `handed_to_human` |
| *additive, optional* `conflicts` | `[{ "winner": {doc_id, section}, "superseded": {doc_id, section}, "reason": "newer circular effective 2026-12-01" }]` – the R6 record, also stored in trace |
| *additive, optional* `language` | reply language `en`/`hi`/`hinglish` |

Behaviour contract:
* Cannot book/cancel/change. `/chat` only ever *proposes* (`confirm_needed`).
* A chat message such as "yes confirm" **does not** confirm; only the endpoint in §4.2 does. The assistant tells the passenger to use the Confirm control.
* **At most two consecutive `clarification` answers (D3)**; the third turn must produce a best-effort `answer`/`not_found`/hand-over.
* Same refusal text and timing class for "booking doesn't exist" and "booking isn't yours".

### 4.2 `POST /actions/{action_id}/confirm`

Headers: `X-Passenger-Id`. Body empty. **No LLM involved.** Two clocks are used, and they are never mixed (D6, v1.2):
* **Business clock (`as_of`):** the `as_of` saved on the action at proposal time. Used only for the refund/fare recompute and policy/settings lookup at step 5 below. Callers cannot override it.
* **Operational clock (expiry):** the real server UTC clock, via an injectable `Clock` protocol (`Clock.now_utc()`), compared against `expires_at` — an actual UTC timestamp computed and stored at proposal time (`expires_at = Clock.now_utc() + action_expiry_minutes`). Tests inject a fake `Clock`; production uses the real one. `as_of` is never read for the expiry decision.

```json
// ConfirmResponse (200)
{
  "trace_id": "c93a1f07",
  "answer_type": "action_done",
  "answer": "Booking UR-30418 is cancelled. Refund of Rs 1,840 is recorded.",
  "action": { "action_id": "ACT-0091", "type": "cancel_booking", "status": "done", "booking_id": "UR-30418" },
  "verification": { "checked": true, "booking_status": "cancelled", "refund": 1840, "matches_preview": true },
  "idempotent_replay": false,
  "sources": [ { "doc_id": "RUL-CAN-01", "section": "3. Refund table" } ]
}
```

Semantics:
1. Look up action; if absent **or** `passenger_id` ≠ header → 404 (indistinguishable).
2. `cancelled` → 409.
3. **Expiry, operational clock (D6):** if `Clock.now_utc() ≥ action.expires_at` → mark `expired`, return 410. This uses only the stored `expires_at` timestamp and the injectable server clock — never `as_of`.
4. If already `done` → **200 with the stored result and `idempotent_replay: true`**; no second change. If `executing` (concurrent call) → return the same stored result; never run twice.
5. Atomic compare-and-swap `proposed → executing`; run the change in **one DB transaction**. **Revalidate using the saved `as_of`, business clock** (D6): booking still exists and is owned by the caller, booking/traveller status unchanged since preview, change still allowed, recomputed refund/fare (evaluated against `settings` as of `as_of`) equals the preview. If anything differs (for example a circular or `settings_changes` ingested in between) → status `failed`, nothing changed, response is `confirm_needed` with a fresh `pending_action` carrying a new preview.
6. After commit, **re-read** booking/seat rows and fill `verification`. A verification failure rolls back, action `failed`, never reported as done.
7. Write trace.

### 4.3 `POST /actions/{action_id}/cancel`

Drops a proposed change. Same ownership rule (404 otherwise). Body empty.

```json
{ "trace_id": "d41b7a90", "answer_type": "answer",
  "answer": "Okay, I have dropped that request. Nothing was changed.",
  "action": { "action_id": "ACT-0091", "status": "cancelled" } }
```
Already `cancelled` → 200 replay. `done` → 409 (cannot undo a confirmed change here).

### 4.4 `GET /bookings/{booking_id}`

Header `X-Passenger-Id`. Same privacy rule as chat: not yours or not existing → identical 404.

```json
{
  "booking_id": "UR-30418", "passenger_id": "P007",
  "train_no": "12123", "train_name": "…", "journey_date": "2026-12-05",
  "from_code": "PUNE", "to_code": "NGP", "class": "2AC",
  "boarding": { "station_code": "PUNE", "departure": "2026-12-05T18:40:00+05:30" },
  "amount_paid": 2040, "status": "confirmed", "booked_at": "2026-11-20T11:02:00+05:30",
  "travellers": [ { "traveller_name": "A. Sharma", "age": 34, "status": "CNF", "coach": "B2", "berth": "21" } ],
  "pending_actions": [ { "action_id": "ACT-0091", "type": "cancel_booking", "status": "proposed" } ]
}
```
Masking: no phone/ID number ever; `phone_last4` only where passenger info is exposed (not needed here). `pending_actions` is *additive*.

### 4.5 `GET /trace/{trace_id}`

Returns the full record in §11. Access: the owning passenger (O8). Non-owner/unknown → 404.

### 4.6 `GET /health`

`200 {"status":"ok","db":"ok","index_docs":<int>,"llm":"mock"|"ollama"|"hosted","mock_llm":true|false}` only when DB opens, index loaded and (if not mock) LLM reachable. Otherwise `503`.

---

## 5. Ingest and document format (RAG owns logic; Backend owns route)

### 5.1 Document file format (Data & Testing writes, RAG parses)

Markdown with YAML front matter, one file per document, `.md`, UTF-8:

```markdown
---
doc_id: RUL-CAN-01
doc_type: rule            # rule | circular | faq
title: Cancellation and refunds
effective_from: 2026-01-01
effective_to:             # optional; empty = open-ended
supersedes: []            # list of doc_ids this one overrides (circulars, newer rules)
language: en              # en | hi | hinglish
status: active            # active | withdrawn
---
## 1. Scope
…text…
## 3. Refund table
…text/table…
```
* Each `##` heading is a **section**; `section` in citations is the heading text exactly (e.g. `3. Refund table`).
* FAQ documents: one document per FAQ answer or one file with `##` per Q; `doc_id` `FAQ-<n>`; `answer_last_reviewed` optional.
* Doc ID inventory is kept in `data/documents/INDEX.md` (needed for the submission list).

### 5.2 `POST /ingest`

**Document ingestion and settings updates are two independent parts of the request body (D2, v1.2).** `doc_id`/`doc_type`/`title`/`effective_from`/`supersedes`/`language`/`sections` (or `markdown`) describe the **document only**; `settings_changes` describes **policy numbers only**. Neither field is derived from the other, by any component, LLM or heuristic — a request may carry either, both, or (if only `settings_changes` with a `source_doc` that already exists) just the latter.

```json
// IngestRequest – text and a settings change together
{
  "doc_id": "CIR-2026-09", "doc_type": "circular", "title": "Revised cancellation charges",
  "effective_from": "2026-12-04", "supersedes": ["RUL-CAN-01"], "language": "en",
  "sections": [ { "section": "Revised charges", "text": "From 4 Dec 2026 the charge for 2AC cancelled 48h or more before departure is Rs 250." } ],
  "settings_changes": [
    { "name": "cancel_charge_2AC_over_48h", "value": 250, "effective_from": "2026-12-04", "source_doc": "CIR-2026-09" }
  ]
}
```
```json
// IngestRequest – text-only circular: stored and indexed, but NO setting changes at all,
// even though the text itself states a new number. The refund amount will not change
// until a separate settings_changes entry is sent (same call or a later one on this doc_id).
{
  "doc_id": "CIR-2026-10", "doc_type": "circular", "title": "Revised cancellation charges",
  "effective_from": "2026-12-04", "supersedes": ["RUL-CAN-01"], "language": "en",
  "sections": [ { "section": "Revised charges", "text": "From 4 Dec 2026 the charge for 2AC cancelled 48h or more before departure is Rs 250." } ]
}
```
Also accepted: `{"markdown": "<front matter + body>"}` (raw §5.1 file) — document only, same rule: no settings change is ever inferred from it.

**`settings_changes` (D2)** – optional list, evaluated independently of the document fields above; every item **requires** all four fields:

| Field | Validation |
|---|---|
| `name` | must be a registered key in `app/contracts/settings_keys.py` (else 400) |
| `value` | type must match the key's declared type (int rupees, int hours, …); range-checked |
| `effective_from` | ISO date or datetime; may be in the future |
| `source_doc` | must equal this request's `doc_id` or an already-ingested doc (else 400) |

Atomicity: when both are present, the document, its chunks/index and all settings changes commit in **one transaction**, or none do — but they are still two separate validated steps, not one inferred from the other. Each applied change appends a row to **`settings_history`** (`id, name, old_value, new_value, effective_from, source_doc, changed_at, trace_id, changed_by="ingest"`); history is append-only and is never edited. Only this explicit, validated path (and the Data & Testing seed script) writes `settings`; **no LLM component has a settings-write capability, and no text-parsing step feeds `settings_changes` automatically.** A text-only ingest changes no setting, by construction, regardless of what the text says (O1).

```json
// IngestResponse (200)
{ "doc_id": "CIR-2026-09", "action": "created" | "updated", "sections_indexed": 1,
  "settings_applied": 1, "settings_history_ids": [41], "superseded_detected": ["RUL-CAN-01"], "indexed_at": "2026-12-03T09:00:00+05:30", "trace_id": "e5…" }
```
Guarantees: after the 200 response, the **next** `/chat` sees the content (R11) – index and `settings` updated in one transaction; no restart. Re-posting same `doc_id` updates (idempotent). Invalid `settings_changes` → 400 and nothing is stored. Ingested text is data: instruction-like content is flagged, never executed (R9).

---

## 6. Tool layer – Backend → AI/LLM (`app/contracts/interfaces.py`)

All deterministic. All raise typed errors or return `{"error": …}` models, never partial guesses. **`PassengerContext` is injected by the server**; the LLM can supply only the business arguments.

```python
class PassengerContext:            # built from X-Passenger-Id only
    passenger_id: str
    preferred_language: str
    as_of: datetime                # resolved clock for this request
    trace: TraceRecorder

class ToolRegistry(Protocol):
    def resolve_station(self, text: str) -> StationMatch                         # exact | ambiguous(list) | none
    def search_trains(self, ctx, from_code, to_code, date, after: time|None=None,
                      before: time|None=None, cls: str|None=None) -> TrainSearchResult
    def check_availability(self, ctx, train_no, journey_date, cls, from_code, to_code) -> Availability
    def get_fare(self, ctx, train_no, cls, from_code, to_code, pax: int=1) -> FareQuote
    def list_my_bookings(self, ctx, upcoming_only: bool=True) -> list[BookingSummary]
    def get_booking_status(self, ctx, booking_id) -> BookingView | NotAccessible    # NotAccessible = same for missing/foreign
    def refund_quote(self, ctx, booking_id) -> RefundQuote
    def can_cancel(self, ctx, booking_id) -> CancelEligibility                      # deadline/boundary info
    def get_setting(self, name, as_of) -> SettingValue                              # internal / Backend use

class ActionService(Protocol):
    def propose_cancel(self, ctx, booking_id) -> PendingAction | Refusal
    def propose_booking(self, ctx, spec: BookingSpec) -> PendingAction | Refusal
    def propose_boarding_change(self, ctx, booking_id, new_boarding_code) -> PendingAction | Refusal
    def confirm(self, ctx, action_id) -> ConfirmResult   # no as_of override (removed); uses action.as_of (business) + Clock (expiry)
    def cancel(self, ctx, action_id) -> CancelResult

class HandoffService(Protocol):
    def create(self, ctx, desk: Desk, summary: str, booking_id: str|None, session_id: str) -> HandoffRecord

class SessionStore(Protocol):
    def load(self, session_id, passenger_id) -> SessionState      # slots, last intent, followup_count, history window
    def save(self, session_id, passenger_id, state: SessionState) -> None
```

Key shapes (all money = int rupees):

```python
RefundQuote(
  booking_id, amount_paid: int, charge: int, refund: int,
  hours_before_departure: float|None, departure_at: datetime,
  rule_basis: list[DocRef],            # doc_id + section (from settings.source_doc)
  per_traveller: list[{traveller_name, status, refund, charge}],
  booking_status_effect: "normal"|"train_cancelled_full_refund"|"not_cancellable",
  can_cancel: bool, reason: str|None, next_cutoff_at: datetime|None)

TrainSearchResult(trains=[{train_no, name, from_code, to_code,
                           depart_at, arrive_at, duration_min, classes, runs_on_date: bool}], note: str|None)
Availability(train_no, journey_date, cls, available:int, rac:int, waitlist:int, outcome:"CNF"|"RAC"|"WL"|"FULL")
FareQuote(train_no, cls, from_code, to_code, fare_per_pax:int, pax:int, total:int, source: "fares table")
PendingAction(action_id, type, booking_id|None, expires_at: datetime,       # real UTC timestamp, operational clock (D6)
              preview: dict)                                                # preview amounts computed from settings as of as_of (business clock)

class Clock(Protocol):             # operational clock, injectable for tests; never used for refund/policy math
    def now_utc(self) -> datetime: ...
```

Rules binding Backend:
* `refund_quote` is a **pure function** of (booking, settings as of `as_of`, `as_of`); cut-off convention per D4 (inclusive); unit-tested at every threshold, ±1 minute.
* The tool output is the only source of any amount/date the assistant may state.
* Cross-passenger access returns the same `NotAccessible` for "unknown" and "someone else's".
* Level 3 requests (over-refund, waitlist promotion, fare edits, others' bookings) have **no tool**; policy refuses them.

---

## 7. RAG interface – RAG → AI/LLM (and Backend for ingest)

```python
class Retriever(Protocol):
    def retrieve(self, query: str, as_of: datetime, k: int = 5,
                 language: str|None = None, doc_types: list[str]|None = None) -> RetrievalResult
    def ingest(self, doc: IngestDoc) -> IngestResult           # immediate visibility (R11)
    def stats(self) -> {"docs": int, "chunks": int}

RetrievalResult(
  passages=[{ chunk_id, doc_id, doc_type, section, text, score,
              effective_from, effective_to, language, flags: ["suspicious"]? }],
  conflicts=[{ winner: DocRef, superseded: DocRef, reason: str }],   # R6
  excluded=[{ doc_id, section, why: "not_yet_effective"|"superseded"|"withdrawn" }])   # for trace
```

Contract:
* Only passages **effective at `as_of`** are returned in `passages`; `excluded` is for trace/debug. A future-dated circular is excluded until its date.
* On clash, only the winner is in `passages`; the loser is in `conflicts`. Precedence: later `effective_from` > circular over rule over FAQ > explicit `supersedes`.
* Empty `passages` ⇒ orchestrator must answer `not_found` (never invent).
* `text` is untrusted data. Passages containing instruction-like patterns carry `flags: ["suspicious"]`.
* Same `Retriever` works in mock mode (keyword-only) with deterministic ordering.
* Settings are **not** RAG's job; ingest forwards `settings_changes` to Backend's settings repository inside the same transaction.

---

## 8. LLM / orchestrator interface – AI/LLM → Backend

```python
class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: type[BaseModel], *, temperature: float = 0) -> BaseModel
    def complete_text(self, system: str, user: str, *, temperature: float = 0.2) -> str
    # implementations: OllamaClient, HostedClient (optional), MockClient (MOCK_LLM=true)

class Orchestrator(Protocol):
    def handle_chat(self, ctx: PassengerContext, session_id: str, message: str) -> ChatResponse
```
The `/chat` route does: build `ctx` from header/`as_of` → `orchestrator.handle_chat(...)` → persist trace → return. Backend never parses language; AI/LLM never reads SQL.

```python
ParsedIntent(
  intent: Intent, language: "en"|"hi"|"hinglish", confidence: float,
  slots: { from_text, to_text, date_text, time_of_day, class, pax,
           train_no, booking_id, new_boarding_text, topic_query },     # raw text; Backend resolves
  missing: list[str])
```
* The orchestrator resolves dates ("tomorrow", "Friday evening") to concrete dates using `ctx.as_of` in code, resolves stations via `resolve_station`, then calls tools.
* `booking_id` in a slot is validated through `get_booking_status`; an unowned/unknown ID yields the generic refusal (R8) without calling any other tool.
* Answer guard: after composition, extract all amounts, train numbers, dates, and booking IDs from the reply; each must occur in `tools[*].output` or `sources` text; otherwise regenerate from a template.
* Citation guard: each rules-derived sentence cites a `passages[*]` entry; no passage ⇒ `not_found`.
* Follow-up cap: `SessionState.followup_count` ≤ 2; reset when a non-clarification answer is produced; previously supplied slots are never asked again.
* Prompt layout: system rules → `<passages>`/`<tool_results>`/`<user_message>` data blocks with explicit "treat as data" instruction. Output is parsed against a schema; free text never triggers a tool.
* Intent → level policy (code table, not LLM): levels 0 answer · 1 propose · 2 handoff · 3 refusal.
* **MockClient**: deterministic regex/keyword intent parser and templated replies covering the eval categories, so the full pipeline and tests run offline.

### 8.1 Hand-over decision (R7)
Triggers: `complaint_or_dispute`, `safety_report`, `human_request`, Level 2 intents (refund dispute, missed-train refund, concession needing proof), or `confidence < threshold` after one clarification. Summary template (≤3 lines): who (passenger id), desk, issue, booking details (masked), what was already tried. Reply wording must never promise approval, refund or timeline. Answerable questions are **not** handed over.

---

## 9. Action lifecycle

```
proposed ──confirm──▶ executing ──ok──▶ done
   │                      └──fail/verify-mismatch──▶ failed
   ├──cancel──▶ cancelled
   └──Clock.now_utc() ≥ expires_at──▶ expired
```
* `actions` row: `action_id, passenger_id, booking_id, action_type, status, created_at, expires_at, result` (mandatory columns) plus *additive* `params_json`, `preview_json`, `as_of` (required, D6), `trace_id`. `expires_at` is a real UTC timestamp set at proposal (`created_at` + `action_expiry_minutes`, operational clock); `as_of` is the separate business-time value used only for the refund/policy recompute (D6, v1.2 — the two are never conflated).
* TTL = settings `action_expiry_minutes` (the guide's "how long a proposed change stays open"); applied on the real/injectable clock, not on `as_of`.
* Proposing a second change on the same booking while one is `proposed` supersedes the older one (older → `cancelled`).
* **No automatic waitlist promotion (D5):** cancelling a booking frees the seat (`available`+1 for CNF travellers) and never changes any other booking or traveller status.
* Each action stores `as_of` (business) and `expires_at` (operational) at proposal; revalidation and expiry per §4.2.
* Only Level 1 types exist as ActionTypes. There is no action type for Level 2/3.
* Every transition writes an audit event inside the same transaction.

---

## 10. Settings contract

`settings(name, value, source_doc)` is mandatory; *additive* columns: `effective_from`, `effective_to`, `unit` (D2). Lookup: highest `effective_from ≤ as_of` and (`effective_to` null or `> as_of`); ties → latest ingest. Every row has a `source_doc`; `refund_quote.rule_basis` is built from it.

Key naming: `snake_case`, mirroring the guide's example (`cancel_charge_2AC_over_48h = 200, RUL-CAN-01`).

| Key family (registered in `app/contracts/settings_keys.py`) | Used by |
|---|---|
| `cancel_charge_<CLASS>_<bracket>` (e.g. `…_over_48h`, `…_12h_to_48h`, `…_4h_to_12h`, `…_under_4h`) and `cancel_charge_wl_*`, `cancel_charge_rac_*` | `refund_quote` |
| `refund_pct_train_cancelled`, `refund_pct_late_over_<n>h` | `refund_quote` |
| `cancel_cutoff_hours_before_departure` | `can_cancel` |
| `tatkal_charge_<CLASS>`, `tatkal_open_hours_before` | fare/rules |
| `boarding_change_cutoff_hours` | change-boarding |
| `action_expiry_minutes` | actions |
| `max_pax_per_booking`, `chart_prepared_hours_before` | booking/rules |

Final list is fixed by Data & Testing together with Backend in Phase 0 (values come from the rules documents; names are the contract). **Boundary convention (D4):** thresholds are inclusive on the lower bound of each bracket: a booking cancelled with `hours_before_departure == 48.0` is charged the "48h or more" rate; at 47h59m the next bracket applies. A key such as `cancel_charge_2AC_over_48h` therefore means "48h or more" (name kept from the guide's example). The same rule appears in RUL-CAN-01, `settings`, `refund_quote`, and the eval oracle. A specific policy document may state otherwise explicitly; if so, the exception is recorded on that key's `unit`/note and tested separately.

`settings_history` (append-only, D2) is mandatory in `db/schema.sql`.

---

## 11. Trace record (R10)

Stored by `audit/` for **every** `/chat`, confirm, cancel and ingest. Returned by `GET /trace/{id}`.

```json
{
  "trace_id": "b17e40c2", "created_at": "2026-12-03T08:15:02+05:30", "as_of": "2026-12-03T08:15:00+05:30",
  "endpoint": "/chat", "session_id": "sess-123", "passenger_id": "P007",
  "request": { "message": "Cancel my ticket for tomorrow" },
  "language": "en",
  "intent": { "intent": "cancel_booking", "confidence": 0.93, "slots": {…} },
  "retrieval": { "query": "…", "passages": [ { "doc_id": "RUL-CAN-01", "section": "3. Refund table", "score": 0.81 } ],
                 "excluded": [ { "doc_id": "CIR-2026-11", "why": "not_yet_effective" } ],
                 "conflicts": [ ] },
  "tools": [ { "tool": "refund_quote", "input": {"booking_id": "UR-30418"}, "output": {…}, "ms": 4 } ],
  "guards": { "answer_guard": "pass", "injection_flags": [], "followup_count": 0 },
  "action": { "proposed": {"action_id": "ACT-0091", "type": "cancel_booking"}, "confirmed": null, "verification": null },
  "handoff": null,
  "llm": { "mode": "ollama", "model": "…", "prompt_versions": { "intent": "v1", "compose": "v1" } },
  "response": { "answer_type": "confirm_needed", "answer": "…", "sources": […] },
  "latency_ms": 812
}
```
A confirm trace holds `action.confirmed` and `action.verification` and links the proposal's `trace_id`, so a full preview → confirm → change → check chain is replayable (also the source of the 3 required sample audit records). Phone/ID values are masked in traces; full prompts are stored only as version IDs plus rendered text when `TRACE_STORE_PROMPTS=true`.

---

## 12. Privacy & security contract

1. `passenger_id` ← header only. Not a tool argument, not parseable from any text.
2. All reads of `bookings`, `booking_travellers`, `actions`, `traces`, `sessions` are filtered by `passenger_id` in the repository layer (not in the route), so no code path can skip the check.
3. Foreign/non-existent → identical response body, status and (approximately) latency; trace records the real reason internally.
4. Masking: phone → last 4 only (`XXXXXX1234`); ID numbers are not stored; never echoed even if a user pastes one.
5. The LLM prompt receives only the current passenger's data needed for the turn.
6. Instruction-like text in messages, FAQs or ingested documents is data; there is **no tool the LLM can call that changes state**, and `confirm` is not reachable from `/chat`.
7. Test data uses invented names/phones/IDs only (guide §4.1 data rules).

---

## 13. Mock mode contract

`MOCK_LLM=true` ⇒ `MockClient` for both intent and composition, embeddings fall back to keyword-only, `/health` reports `mock_llm: true`. Behaviour is deterministic so the same input yields the same trace (except IDs/timestamps). Full API remains available. Environment variables are listed in `.env.example` (frozen): `MOCK_LLM, DB_PATH, OLLAMA_URL, LLM_MODEL, EMBED_MODEL, TZ_NAME, TRACE_STORE_PROMPTS, DEFAULT_AS_OF` (optional).

---

## 14. Requirement ↔ contract map

| Req | Where enforced |
|---|---|
| R1, R2 | §8 `ParsedIntent`, follow-up cap |
| R3, R6 | §7 `RetrievalResult.conflicts`, §4.1 `sources` |
| R4 | §6 tool layer, answer guard §8 |
| R5 | §4.1/§4.2/§9 |
| R7 | §8.1, §6 `HandoffService`, §4.1 `handed_to_human` |
| R8 | §2.1, §4.4, §12 |
| R9 | §5.2, §7, §8, §12 |
| R10 | §11 |
| R11 | §5.2, §7 |
| R12 | outside the API: `eval/` owned by Data & Testing; reads `/chat`, `/actions/*`, `/trace/*` |
