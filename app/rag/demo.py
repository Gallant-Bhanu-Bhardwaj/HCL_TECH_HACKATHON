#!/usr/bin/env python3
"""Executable RAG demonstration — real Ollama embeddings only, no mock.

Run:
    python -m app.rag.demo

Connects to the configured SQLite database (DB_PATH, api-contracts
§13), checks real Ollama connectivity, ensures every document/chunk is
indexed and every chunk has a real embedding (indexing the ones
missing it if needed), then runs real hybrid retrieval for a fixed set
of demonstration queries and shows the retrieved chunk, its citation,
score and effective date — including two queries run at two different
`as_of` dates to show supersession and future-effective-circular
filtering in action, not just assert it in a test.

Fails clearly (non-zero exit, no traceback soup) if either the
database or Ollama is unavailable — it never falls back to a mock or a
partial result and calls that success.
"""
from __future__ import annotations

import sys
from datetime import date

from app.config import settings
from app.db.connection import check_connectivity, init_db
from app.rag.embeddings import EmbeddingBackendUnavailable, OllamaEmbedder, embed_missing_chunks
from app.rag.ingest import ingest_all
from app.rag.retrieve import retrieve_context

DEMO_AS_OF = date(2026, 12, 3)  # the data kit's own reference "today"

# The 5 demonstration queries exactly as specified for this task.
DEMO_QUERIES: tuple[str, ...] = (
    "What is the cancellation refund policy?",
    "Mera 3AC ticket waitlist mein hai, chart banne tak kya hoga?",
    "Am I allowed to travel with a small dog in a private compartment?",
    "What is the Tatkal surcharge for Sleeper class?",
    "What happens if a newer circular replaces an older cancellation rule?",
)

# The 5th query above is also the supersession/future-effective
# demonstration: run it a second time, at a date after CIR-2026-11
# takes effect, so the audience sees the answer actually change.
SUPERSESSION_AS_OF_BEFORE = date(2026, 12, 3)
SUPERSESSION_AS_OF_AFTER = date(2026, 12, 10)


def _fail(message: str) -> None:
    print(f"\nFAILED: {message}", file=sys.stderr)
    sys.exit(1)


def _show_result(query: str, as_of: date, result, show_excluded: bool = False) -> None:
    print(f'QUERY: "{query}"   (as_of={as_of.isoformat()})')
    if not result.passages:
        print("  (no passages retrieved)")
    for i, p in enumerate(result.passages, start=1):
        snippet = next((line for line in p.text.strip().splitlines() if line.strip()), "")[:110]
        print(f"  {i}. [{p.doc_id} / {p.section}]")
        print(f"     score={p.score:.4f}  effective_from={p.effective_from}  effective_to={p.effective_to}")
        print(f"     text: \"{snippet}{'...' if len(snippet) == 110 else ''}\"")
        print(f"     citation: {p.doc_id}, section \"{p.section}\"")
    if show_excluded and result.excluded:
        print("  excluded (flagged, not silently dropped):")
        for e in result.excluded:
            print(f"    - {e.doc_id} ({e.section}) -> {e.why}")
    if result.conflicts:
        print("  conflicts flagged:")
        for c in result.conflicts:
            print(f"    - winner={c.winner.doc_id}/{c.winner.section}  "
                  f"superseded={c.superseded.doc_id}/{c.superseded.section}")
            print(f"      reason: {c.reason}")
    print()


def main() -> None:
    print("=== Ujjwal Rail RAG — live demonstration (real Ollama, no mock) ===")
    print(f"DB_PATH     = {settings.db_path}")
    print(f"OLLAMA_URL  = {settings.ollama_url}")
    print(f"EMBED_MODEL = {settings.embed_model}")
    print()

    # 1. Connect to the configured database
    print("[1/7] Connecting to the configured database...")
    try:
        conn = init_db()
    except Exception as exc:  # noqa: BLE001 - this is the top-level demo entry point
        _fail(f"could not initialize/connect to the database at {settings.db_path!r}: {exc}")
        return
    if not check_connectivity(settings.db_path):
        _fail(f"database at {settings.db_path!r} did not pass a connectivity check after init")
        return
    print(f"      OK\n")

    # 2/3. Check Ollama connectivity using the real OllamaEmbedder (never MockEmbedder)
    print("[2/7] Checking Ollama connectivity with the real OllamaEmbedder...")
    embedder = OllamaEmbedder()
    try:
        probe_vector = embedder.embed("connectivity check")
    except EmbeddingBackendUnavailable as exc:
        _fail(
            f"Ollama is not reachable at {settings.ollama_url!r} with model {settings.embed_model!r}: {exc}\n"
            f"       Start it with:  ollama serve\n"
            f"       Make sure the model is pulled:  ollama pull {settings.embed_model}"
        )
        return
    print(f"      OK — model={embedder.model!r}, dim={len(probe_vector)}\n")

    # 4. Index any missing documents/chunks/embeddings
    print("[3/7] Ensuring every document/chunk is indexed (idempotent)...")
    ingest_result = ingest_all(conn)
    print(f"      documents={ingest_result['documents']}  chunks={ingest_result['chunks']}\n")

    print("[4/7] Embedding any chunk that doesn't have a real vector yet...")
    embed_result = embed_missing_chunks(conn, embedder)
    total_vectors = conn.execute("SELECT COUNT(*) FROM chunk_vectors").fetchone()[0]
    print(f"      newly embedded this run = {embed_result['chunks_embedded']}")
    if embed_result["skipped_empty"]:
        print(f"      skipped (empty text, never fabricated): {embed_result['skipped_empty']}")
    print(f"      total real embeddings now stored = {total_vectors}\n")

    # 5/6. Real hybrid retrieval for each demonstration query
    print("[5/7] Running real hybrid retrieval (FTS5 + real embeddings) for the demonstration queries...\n")
    for query in DEMO_QUERIES:
        result = retrieve_context(conn, query, as_of=DEMO_AS_OF, top_k=3, embedder=embedder, keyword_only=False)
        _show_result(query, DEMO_AS_OF, result)

    # 7. Explicit supersession / future-effective-circular demonstration
    print("[6/7] Demonstrating supersession and future-effective filtering "
          "(same query, two different reference dates)...\n")
    query5 = DEMO_QUERIES[-1]
    print("--- BEFORE CIR-2026-11 takes effect ---")
    before = retrieve_context(conn, query5, as_of=SUPERSESSION_AS_OF_BEFORE, top_k=5, embedder=embedder, keyword_only=False)
    _show_result(query5, SUPERSESSION_AS_OF_BEFORE, before, show_excluded=True)

    print("--- AFTER CIR-2026-11 takes effect (as_of moved to 2026-12-10) ---")
    after = retrieve_context(conn, query5, as_of=SUPERSESSION_AS_OF_AFTER, top_k=5, embedder=embedder, keyword_only=False)
    _show_result(query5, SUPERSESSION_AS_OF_AFTER, after, show_excluded=True)

    print("[7/7] Demonstration complete.")
    conn.close()


if __name__ == "__main__":
    main()
