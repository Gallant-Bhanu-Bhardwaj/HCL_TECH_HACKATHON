# Ujjwal Rail Assistant

An AI travel assistant for **Ujjwal Rail**, a fictional train operator, built for the HCLTech Future Ready AI Engineer Hackathon. Passengers can find trains, check seats and fares, ask about the rules, work out refunds, and book, cancel or change tickets in English, Hindi or Hinglish.

The assistant only answers from its rule documents and its database. Every change to a booking needs the passenger to press **Confirm**.

## Design in one paragraph

One LLM, a handful of plain Python tools, and no multi-agent setup. The LLM understands the question, picks which tool to call, and writes the reply. Python does everything exact: train search, seats, fares, refund amounts, deadlines and privacy checks. The LLM can only *propose* a booking, cancellation or change. The change happens only when the passenger presses Confirm, which calls `POST /actions/{id}/confirm` directly and never goes through the LLM.

```
Streamlit UI ──► FastAPI (app/main.py) ──► agent (app/agent.py) ──► LLM (Ollama)
                       │                        │
                       │                        ├─► tools.py    trains, seats, fares, bookings, refunds
                       │                        ├─► actions.py  propose cancel / book / change boarding, hand-over
                       │                        └─► rag.py      rules, circulars, FAQs
                       │
                       └─ /actions/{id}/confirm ─► actions.confirm()   (no LLM)
```

### Why it is built this way

| Decision | Reason |
| --- | --- |
| Refunds are a plain Python function | A refund is a rule in a table, not a judgement. Tests check every cut-off. |
| Every number lives in the `settings` table with an effective date | A circular adds a new row from its date, so the newer rule wins automatically (R6), even for a future-dated circular. |
| Only `actions.confirm()` writes to bookings | A booking can never change without the passenger's confirmation. One conditional UPDATE makes a second confirm do nothing. |
| The passenger comes from the `X-Passenger-Id` header | Typed claims like "I am P012" are ignored. Every booking query filters on the passenger, and someone else's booking gets the same reply as a missing one. |
| Keyword (BM25) plus embedding search | Keywords catch exact terms like "Tatkal" or "RUL-CAN-01". Embeddings catch paraphrases and Hindi. Search still works with keywords alone if the model can't load. |
| Mock mode (`MOCK_LLM=true`) | The whole system can be tested without a model, quickly and repeatably. |

## Project layout

```
app/
  main.py        the 7 API endpoints, saves a trace of every reply
  agent.py       the orchestrator: LLM + tool calls, keyword guards, answer type
  llm.py         talks to Ollama (or any OpenAI-compatible API), plus mock mode
  tools.py       read-only facts: stations, trains, seats, fares, bookings, refunds
  actions.py     the only module that changes data: propose, confirm, cancel, hand-over
  rag.py         search over rules, circulars and FAQs, plus live ingest
  db.py          SQLite connection and date-aware settings lookup
ui/app.py        Streamlit chat page
data/
  documents/     12 rules, 6 circulars, 20 FAQs (markdown with front matter)
  generator/     generate_data.py, policy_values.py, edge_cases.py
  validate/      validate_data.py
db/
  schema.sql     database tables
  seed_data.sql  generated synthetic data (committed; the .db file is not)
tests/           70 automated tests
init_db.py       builds db/ujjwal.db from schema + seed data
run.sh           starts the API
smoke_test.sh    calls every endpoint once against a running server
docs/            architecture, API contracts, task plan, problem statement
```

## Setup

The whole team uses **Python 3.11**, with the same pinned package versions.

```bash
# 1. Python 3.11 with uv (Ubuntu 26.04 ships only 3.14)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11
uv venv --python 3.11 .venv
source .venv/bin/activate

# 2. Packages (on Linux, --torch-backend=cpu avoids the large GPU build of PyTorch)
uv pip install -r requirements.txt -r requirements-ui.txt --torch-backend=cpu

# 3. LLM
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma4:e4b
```

The first time the API runs a rules search, it downloads the embedding model (about 470 MB).

## Data

```bash
python data/generator/generate_data.py   # writes db/seed_data.sql (seed 42, base date 2026-12-03)
python data/validate/validate_data.py    # checks the data
python init_db.py                        # builds db/ujjwal.db
```

The data's reference "today" is **2026-12-03**, and seats exist for 14 days from then. Use that date as `as_of` when testing.

## Run

```bash
./run.sh                    # API on http://localhost:8000 with gemma4:e4b (rebuilds the database first)
./run.sh mock               # API without any LLM
streamlit run ui/app.py     # chat page on http://localhost:8501
```

Change the model with `LLM_MODEL=qwen2.5:7b ./run.sh`. For a hosted model, set `LLM_URL`, `LLM_MODEL` and `LLM_API_KEY`.

Interactive API docs are at http://localhost:8000/docs.

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /chat` | Send a message. Header `X-Passenger-Id`. Body `{"session_id", "message", "as_of"?}`. |
| `POST /actions/{id}/confirm` | Confirm a proposed change. Optional body `{"as_of"}`. A second call changes nothing. |
| `POST /actions/{id}/cancel` | Drop a proposed change. |
| `GET /bookings/{id}` | One booking, for its owner only. 404 for a missing booking or someone else's. |
| `POST /ingest` | Add or update a rule, circular or FAQ while the server runs. |
| `GET /trace/{trace_id}` | The saved record of a reply: request, tools used, documents, answer. |
| `GET /health` | `{"status": "ok"}` when ready. |

Example:

```bash
curl -X POST localhost:8000/chat -H "X-Passenger-Id: P007" -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "If I cancel UR-30418, how much will I get back?", "as_of": "2026-12-03T10:00:00+05:30"}'
```

`/ingest` accepts either a full markdown file or separate fields. An optional `settings` list updates the numbers the refund code uses from the circular's date:

```json
{
  "doc_id": "CIR-2026-20", "doc_type": "circular", "title": "Revised SL charge",
  "effective_from": "2026-12-04", "supersedes": ["RUL-CAN-01"],
  "text": "## 1. Revised charge\nFrom 4 December 2026 the SL charge 48 hours or more before departure is Rs 80.",
  "settings": [{"name": "cancel_charge_SL_over_48h", "value": 80}]
}
```

## Refund rules (from RUL-CAN-01, RUL-REF-01, RUL-OPC-01)

- Each traveller is charged by class and time band: 48 h or more, 12–48 h, 4–12 h, under 4 h. The lower bound is inclusive, so exactly 48 h counts as "48 h or more".
- RAC travellers pay a flat Rs 50. Waitlisted travellers pay nothing.
- A mixed booking adds up each traveller's own charge.
- A train cancelled by Ujjwal Rail gets a full refund.
- Hours are measured to departure from the passenger's boarding station.

## Testing

```bash
python -m pytest -q tests                        # 70 tests, about 5 seconds, no LLM needed
python -m pytest -q tests/test_edge_cases.py -v  # each awkward case from the data kit
./smoke_test.sh                                  # every endpoint against a running server (./run.sh mock)
```

| Edge case | Data | Expected |
| --- | --- | --- |
| Worked example | UR-30418 (P007) | Rs 2040 paid, Rs 200 charge (CIR-2026-07), Rs 1840 back |
| Exactly 48 h / one minute after | UR-30001, UR-30002 | SL charge Rs 60 / Rs 120 |
| Train after midnight | UR-30003 | Leaves 4 Dec at 00:40 |
| Mixed CNF + WL | UR-30004 | Rs 760 − Rs 60 = Rs 700 |
| RAC / waitlisted | UR-30008 / UR-30009 | Rs 50 charge / full refund |
| Fully booked class | 12123, 3AC, 5 Dec | 0 available, RAC 1, waitlist 2 |
| Operator-cancelled train | UR-30011 | Full Rs 575 refund (RUL-OPC-01) |
| Expired request | ACT-EDGE-0003, ACT-EDGE-0005 | Confirm refused |
| Duplicate confirm | ACT-EDGE-0004 | "Already done", nothing changes |
| No bookings | P026 | Empty list |
| Similar station names | Delhi, Hyderabad | Asks which station |
| Future circular | CIR-2026-11 | Rs 200 until 9 Dec, Rs 250 from 10 Dec |

## Known limitations

- `eval/eval_set.json` (the evaluation questions) is not in the repo yet, so validator check 14 fails.
- Docker Compose is not set up yet.
- New bookings are confirmed while seats last, then waitlisted. RAC allocation is left out to keep the code simple.
- Mock mode understands only simple message patterns. Use the real model for natural questions.

## Use of AI tools

TODO: list which parts were written with AI assistance (brief Section 8).

## Team

TODO: who built what (brief Section 8).
