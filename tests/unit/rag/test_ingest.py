"""Ingestion idempotency: duplicate ingestion must not duplicate rows."""
from __future__ import annotations

from app.rag.ingest import ingest_all, ingest_document
from app.rag.loader import load_all_documents


def test_ingest_all_populates_documents_and_chunks(conn):
    # db/seed_data.sql already populated these via generate_data.py's
    # own (separate) parser — init_db() in the conftest fixture already
    # ran it. This call must not fail or duplicate on top of that.
    result = ingest_all(conn)
    assert result["documents"] == 38
    assert result["chunks"] > 0

    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert doc_count == 38
    assert chunk_count == result["chunks"]


def test_ingesting_twice_does_not_duplicate_chunks(conn):
    ingest_all(conn)
    first_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    first_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    ingest_all(conn)  # re-run, same files
    second_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    second_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    assert first_chunks == second_chunks
    assert first_docs == second_docs


def test_updating_a_document_on_reingest_updates_its_chunk_text(conn, tmp_path):
    docs_root = tmp_path / "documents"
    (docs_root / "rules").mkdir(parents=True)
    path = docs_root / "rules" / "RUL-TEST-01.md"
    path.write_text(
        "---\ndoc_id: RUL-TEST-01\ndoc_type: rule\ntitle: Test\neffective_from: 2026-01-01\nlanguage: en\n---\n"
        "## 1. Scope\nOriginal text.\n",
        encoding="utf-8",
    )
    (docs_root / "circulars").mkdir()
    (docs_root / "faqs").mkdir()

    docs = load_all_documents(docs_root)
    ingest_document(conn, docs[0])
    before = conn.execute("SELECT text FROM chunks WHERE chunk_id = ?", ("RUL-TEST-01#1. Scope",)).fetchone()
    assert before["text"] == "Original text."

    path.write_text(
        "---\ndoc_id: RUL-TEST-01\ndoc_type: rule\ntitle: Test\neffective_from: 2026-01-01\nlanguage: en\n---\n"
        "## 1. Scope\nUpdated text.\n",
        encoding="utf-8",
    )
    docs = load_all_documents(docs_root)
    ingest_document(conn, docs[0])

    after = conn.execute("SELECT text FROM chunks WHERE chunk_id = ?", ("RUL-TEST-01#1. Scope",)).fetchone()
    assert after["text"] == "Updated text."
    count = conn.execute("SELECT COUNT(*) FROM chunks WHERE doc_id = 'RUL-TEST-01'").fetchone()[0]
    assert count == 1  # not duplicated
