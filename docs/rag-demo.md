# Ujjwal Rail RAG — demo, evaluation, and operations guide

Owner: RAG module (`app/rag/`). This document covers only RAG — not
the backend tools, LLM orchestration, or frontend, which are separate
modules with their own docs.

## Prerequisites

- Python 3.12 with this repo's `.venv` (`pip install -r requirements.txt`).
- `httpx` is used for the Ollama HTTP calls — already in `requirements.txt`, no new dependency.
- [Ollama](https://ollama.com) installed locally, with these two models pulled:
  - `nomic-embed-text` (embeddings, 768-dim)
  - `phi3:mini` (not used by RAG itself — AI/LLM module's concern)
- `db/schema.sql` and `db/seed_data.sql` already present in the repo (RAG does not generate these — Data & Testing owns them).

## Ollama startup

```bash
ollama serve &              # start the local server (if not already running)
ollama list                 # confirm nomic-embed-text is pulled
# if not pulled yet:
ollama pull nomic-embed-text
```

Check it's actually reachable before running anything RAG-related:

```bash
curl -s http://localhost:11434/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"test"}' | python3 -m json.tool
```

**Known environment gotcha**: on some machines, Python's `httpx` picks
up an OS-level proxy configuration that blocks the local Ollama call
with an unrelated HTTP 403, even though `curl` to the same URL works
fine. `app/rag/embeddings.py`'s `OllamaEmbedder` already works around
this (`trust_env=False`) — if you see a 403 from a Squid-style proxy
error page when calling Ollama any other way, that's the same issue.

## Database setup

The RAG module reads/writes the `documents`, `chunks`, `chunks_fts`,
and `chunk_vectors` tables, which already exist in `db/schema.sql`.
Nothing here changes the schema or the seed data.

```bash
# DB_PATH defaults to ujjwal_rail.db in the repo root (see .env.example).
# Any command below that calls init_db() creates/opens it automatically —
# there is no separate "create the database" step.
```

## Indexing documents and generating embeddings

Both are idempotent — safe to re-run any time, including against an
already-populated database; neither duplicates rows.

```python
from app.db.connection import init_db
from app.rag.ingest import ingest_all
from app.rag.embeddings import OllamaEmbedder, embed_missing_chunks

conn = init_db()                    # uses the configured DB_PATH
ingest_all(conn)                    # parses data/documents/**/*.md -> documents, chunks
embed_missing_chunks(conn, OllamaEmbedder())   # embeds any chunk without a real vector yet
```

`app/rag/demo.py` (below) does exactly this automatically every time it runs, so in practice you rarely need to call these by hand.

## Demo command

```bash
python -m app.rag.demo
```

This:
1. Connects to the configured database (fails clearly, exit code 1, if it can't).
2. Checks real Ollama connectivity with the real `OllamaEmbedder` — **never** `MockEmbedder` (fails clearly, exit code 1, if Ollama is unreachable).
3. Ensures every document/chunk is indexed and every chunk has a real embedding, indexing/embedding whatever's missing.
4. Runs real hybrid retrieval (FTS5 + real embeddings) for 5 fixed demonstration queries.
5. Re-runs the last of those 5 queries at two different reference dates to show supersession and future-effective-circular filtering changing the answer live.

### Sample queries used by the demo

- `What is the cancellation refund policy?`
- `Mera 3AC ticket waitlist mein hai, chart banne tak kya hoga?`
- `Am I allowed to travel with a small dog in a private compartment?`
- `What is the Tatkal surcharge for Sleeper class?`
- `What happens if a newer circular replaces an older cancellation rule?` (run twice: `as_of=2026-12-03` and `as_of=2026-12-10`)

### Expected output format

For each query:
```
QUERY: "<query text>"   (as_of=<date>)
  1. [<doc_id> / <section>]
     score=<float>  effective_from=<date>  effective_to=<date or None>
     text: "<first non-empty line of the chunk, truncated>"
     citation: <doc_id>, section "<section>"
  ...
  excluded (flagged, not silently dropped):      <- only for the supersession demo
    - <doc_id> (<section>) -> superseded | not_yet_effective | withdrawn
  conflicts flagged:
    - winner=<doc_id>/<section>  superseded=<doc_id>/<section>
      reason: <why>
```
Ending with `[7/7] Demonstration complete.` and exit code 0.

**Actually observed** (real run, this session): at `as_of=2026-12-03`
the query about circulars replacing rules returns `CIR-2026-07` as the
top passage, with `CIR-2026-11` listed under `excluded` as
`not_yet_effective`; at `as_of=2026-12-10` the same query returns
`CIR-2026-11` as a top passage instead, with `CIR-2026-07` now
`superseded`. This is the real, live behavior, not a scripted example.

## Evaluation command

```python
from app.db.connection import init_db
from app.rag.embeddings import OllamaEmbedder
from app.rag.evaluate import evaluate_retrieval

conn = init_db()
report = evaluate_retrieval(conn, embedder=OllamaEmbedder(), keyword_only=False)
print(report.n, report.recall_at_k, report.mrr)
print([m.test_id for m in report.misses()])
```
Scores Recall@5 and MRR against `eval/eval_set.json`'s
`expected_document_citations` — **only** the questions that actually
carry a document citation (21 of the set's 34 questions; the other 13
are tool-only/behavioral and correctly excluded, not scored as misses).

**Latest real run, this session**: `N=21, Recall@5=0.571, MRR=0.325`.

## Known limitations

- **Document-level supersession granularity.** A circular that revises
  one specific class/bracket (e.g. `CIR-2026-07` only revises
  `2AC`/`over_48h`) currently excludes the *entire* superseded
  document from every query, even one about a class/bracket that
  circular never touched. This is the single biggest cause of
  retrieval misses on `eval/eval_set.json` — see the retrieval-quality
  report for the full analysis. Fixing it means section-level
  supersession, a larger change intentionally left alone so as not to
  risk "breaking supersession."
- **One chunk is permanently un-embeddable as data stands**:
  `CIR-2026-11#2. Effective date...` has empty text due to a markdown
  heading accidentally split across two `## ` lines in that document.
  Not a RAG-module bug (the document belongs to Data & Testing); the
  pipeline skips and reports it rather than fabricating a vector.
- **Full document re-parse per call.** `retrieve_context()` re-reads
  and re-parses all 38 `.md` files on every call (for the supersession
  graph). Fine at this corpus size (milliseconds); would need caching
  if the document count grows substantially.
- **No chunk-size guard.** Nothing truncates or splits a section that
  might exceed the embedding model's context window — not an issue
  with the current corpus (largest section is well within limits).
- **Score fusion is tuned, not theoretically optimal.** `fusion="rrf"`
  with `rrf_k=1` was chosen by sweeping values against the 21-question
  ground truth, not derived analytically — it could shift again if the
  eval set or corpus grows.
- **Not wired into the live `/chat` orchestrator with real embeddings
  by default.** `MOCK_LLM=true` (the project default) makes
  `retrieve_context()` keyword-only; this is correct per the
  documented contract, but means the semantic/hybrid path above is
  only exercised when a caller explicitly passes a real embedder, as
  this demo does.

## Issues that need another team's input

- **Data & Testing**: please fix `data/documents/circulars/CIR-2026-11.md` — the heading
  `## 2. Effective date — this circular is NOT yet in effect at the time` /
  `## this data kit's reference "today" is set` is split across two `##` lines;
  it should be one heading, one line.
- **Backend/AI-LLM**: when wiring real (non-mock) retrieval into the
  live orchestrator, call `retrieve_context(..., keyword_only=False,
  embedder=OllamaEmbedder())` explicitly — the default `keyword_only`
  defers to `settings.mock_llm`, so nothing needs to change in
  `app/rag/` itself, but the call site needs to pass a real embedder
  once `MOCK_LLM=false`.
