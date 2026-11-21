"""Semantic (cosine) retrieval tests, using MockEmbedder — deterministic
and offline, so these never depend on Ollama actually running."""
from __future__ import annotations

import pytest
from tests.fakes.embedder import MockEmbedder

from app.rag.embeddings import embed_missing_chunks
from app.rag.ingest import ingest_all
from app.rag.semantic_search import semantic_search


def test_semantic_search_ranks_by_cosine_similarity_descending(conn):
    ingest_all(conn)
    embedder = MockEmbedder(dim=16)
    embed_missing_chunks(conn, embedder)

    query_vector = embedder.embed("cancellation charge refund rules")
    hits = semantic_search(conn, query_vector, limit=10)

    assert len(hits) == 10
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_identical_text_to_a_chunk_scores_highest(conn):
    ingest_all(conn)
    embedder = MockEmbedder(dim=16)
    embed_missing_chunks(conn, embedder)

    chunk_text = conn.execute(
        "SELECT text FROM chunks WHERE chunk_id = ?",
        ("RUL-LUG-01#4. Pets",),
    ).fetchone()["text"]

    query_vector = embedder.embed(chunk_text)
    hits = semantic_search(conn, query_vector, limit=1)
    assert hits[0].chunk_id == "RUL-LUG-01#4. Pets"
    assert hits[0].score == pytest.approx(1.0)  # identical vector -> cosine similarity ~1


def test_dimension_mismatch_is_skipped_not_crashed(conn):
    ingest_all(conn)
    embed_missing_chunks(conn, MockEmbedder(dim=16))
    # A query vector of a different dimension (e.g. a different EMBED_MODEL) must not raise.
    hits = semantic_search(conn, [0.1] * 8, limit=5)
    assert hits == []
