"""Embedding storage tests (MockEmbedder — Ollama is not required to
be running for these) and a real test of OllamaEmbedder's error path.
"""
from __future__ import annotations

import pytest

from tests.fakes.embedder import MockEmbedder

from app.rag.embeddings import (
    EmbeddingBackendUnavailable,
    OllamaEmbedder,
    embed_missing_chunks,
    pack_vector,
    store_embedding,
    unpack_vector,
)
from app.rag.ingest import ingest_all


def test_pack_unpack_roundtrip():
    vector = [0.1, -0.5, 3.25, 0.0]
    packed = pack_vector(vector)
    assert unpack_vector(packed, len(vector)) == pytest.approx(vector)


def test_store_and_read_back_embedding(conn):
    ingest_all(conn)
    chunk_id = "RUL-CAN-01#3. Refund table (confirmed travellers)"
    store_embedding(conn, chunk_id, [1.0, 2.0, 3.0])
    row = conn.execute("SELECT embedding, dim FROM chunk_vectors WHERE chunk_id = ?", (chunk_id,)).fetchone()
    assert row["dim"] == 3
    assert unpack_vector(row["embedding"], 3) == pytest.approx([1.0, 2.0, 3.0])


def test_store_embedding_upserts_without_duplicating(conn):
    ingest_all(conn)
    chunk_id = "RUL-CAN-01#3. Refund table (confirmed travellers)"
    store_embedding(conn, chunk_id, [1.0, 2.0])
    store_embedding(conn, chunk_id, [9.0, 9.0])  # overwrite, not a second row
    count = conn.execute("SELECT COUNT(*) FROM chunk_vectors WHERE chunk_id = ?", (chunk_id,)).fetchone()[0]
    assert count == 1
    row = conn.execute("SELECT embedding, dim FROM chunk_vectors WHERE chunk_id = ?", (chunk_id,)).fetchone()
    assert unpack_vector(row["embedding"], 2) == pytest.approx([9.0, 9.0])


def test_embed_missing_chunks_with_mock_embedder_embeds_every_nonempty_chunk(conn):
    """One real chunk in the actual data (CIR-2026-11's second section)
    has empty text — a genuine markdown-heading-split defect in that
    document, discovered by actually trying to embed every chunk
    against the real Ollama backend. It is data/documents/ content
    (Data & Testing's, not this module's), so this test documents the
    correct, honest handling: skipped and reported, never embedded as
    if it had content, and never silently ignored."""
    ingest_all(conn)
    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    empty_chunks = conn.execute("SELECT COUNT(*) FROM chunks WHERE trim(text) = ''").fetchone()[0]
    assert empty_chunks == 1  # CIR-2026-11#2.* — documented, not silently assumed away

    result = embed_missing_chunks(conn, MockEmbedder(dim=16))

    assert result["chunks_embedded"] == total_chunks - empty_chunks
    assert len(result["skipped_empty"]) == empty_chunks
    vector_count = conn.execute("SELECT COUNT(*) FROM chunk_vectors").fetchone()[0]
    assert vector_count == total_chunks - empty_chunks


def test_embed_missing_chunks_skips_already_embedded(conn):
    ingest_all(conn)
    embed_missing_chunks(conn, MockEmbedder(dim=16))
    second_run = embed_missing_chunks(conn, MockEmbedder(dim=16))
    assert second_run["chunks_embedded"] == 0  # nothing left unembedded


def test_ollama_embedder_raises_a_clear_error_when_server_is_unreachable():
    """This is a REAL test against the REAL OllamaEmbedder — not
    mocked. It verifies the actual, current state of this machine's
    Ollama server (as of writing this: not running) produces a clear,
    typed exception rather than a fabricated vector or a silent
    failure. If Ollama is started later, this test's behaviour
    documents what WOULD happen if it then goes down again."""
    embedder = OllamaEmbedder(base_url="http://localhost:11434", timeout=2.0)
    try:
        embedder.embed("test query")
    except EmbeddingBackendUnavailable:
        pass  # expected: server unreachable
    else:
        pytest.skip("Ollama server is actually running right now — error path not exercised")


def test_ollama_embedder_raises_for_an_unreachable_host():
    embedder = OllamaEmbedder(base_url="http://localhost:1", timeout=1.0)
    with pytest.raises(EmbeddingBackendUnavailable):
        embedder.embed("anything")
