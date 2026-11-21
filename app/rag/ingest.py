"""Ingestion (architecture §7.1 ingest(); R11: visible to the very next
answer, no restart). Upsert-based (`INSERT ... ON CONFLICT ... DO
UPDATE`), so re-running this against an already-seeded database never
duplicates a chunk or loses data — "avoid duplicate chunks and
embeddings... preserve existing documents" (task rule).

Writes only to `documents`/`chunks` (RAG's own tables). Never touches
`settings`/`settings_history` — that split is D2/architecture §8, not
this module's concern.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.rag.chunker import Chunk, chunk_document
from app.rag.loader import DEFAULT_DOCS_ROOT, ParsedDocument, load_all_documents


def ingest_document(conn: sqlite3.Connection, doc: ParsedDocument) -> dict:
    conn.execute(
        """
        INSERT INTO documents (doc_id, doc_type, title, effective_from, effective_to, supersedes_json, language, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            doc_type = excluded.doc_type, title = excluded.title,
            effective_from = excluded.effective_from, effective_to = excluded.effective_to,
            supersedes_json = excluded.supersedes_json, language = excluded.language,
            status = excluded.status
        """,
        (
            doc.doc_id, doc.doc_type, doc.title, doc.effective_from, doc.effective_to,
            json.dumps(list(doc.supersedes)), doc.language, doc.status,
        ),
    )

    chunks = chunk_document(doc)
    for chunk in chunks:
        conn.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, section, text, language)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chunk_id) DO UPDATE SET
                doc_id = excluded.doc_id, section = excluded.section,
                text = excluded.text, language = excluded.language
            """,
            (chunk.chunk_id, chunk.doc_id, chunk.section, chunk.text, chunk.language),
        )
    conn.commit()
    return {"doc_id": doc.doc_id, "sections_indexed": len(chunks)}


def ingest_all(conn: sqlite3.Connection, docs_root: Path | str = DEFAULT_DOCS_ROOT) -> dict:
    docs = load_all_documents(docs_root)
    results = [ingest_document(conn, doc) for doc in docs]
    return {
        "documents": len(results),
        "chunks": sum(r["sections_indexed"] for r in results),
    }
