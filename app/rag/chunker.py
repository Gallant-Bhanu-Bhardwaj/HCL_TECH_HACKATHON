"""Chunker (architecture §7.1): section-aware — each `##` heading the
loader already split out IS one chunk, carrying its full source
metadata (doc_id, section, effective dates, language, doc_type). This
deliberately does not sub-split a section's text further: every
section in data/documents/ is already a self-contained policy
statement (one refund table, one rule, one FAQ answer); splitting
mid-table or mid-explanation would lose exactly the policy context
RUL-CAN-01 §3's numbers depend on (e.g. the table header and its rows
must stay together).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.rag.loader import ParsedDocument


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    doc_type: str
    section: str
    text: str
    language: str
    effective_from: str
    effective_to: str | None
    status: str


def chunk_document(doc: ParsedDocument) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"{doc.doc_id}#{section.section}",
            doc_id=doc.doc_id,
            doc_type=doc.doc_type,
            section=section.section,
            text=section.text,
            language=doc.language,
            effective_from=doc.effective_from,
            effective_to=doc.effective_to,
            status=doc.status,
        )
        for section in doc.sections
    ]


def chunk_documents(docs: list[ParsedDocument]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(chunk_document(doc))
    return chunks
