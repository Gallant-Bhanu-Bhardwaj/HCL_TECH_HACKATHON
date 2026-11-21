"""Canned FakeRetriever — no indexing, no scoring, no business logic (T3).

RAG does not touch settings (D2): ingest() here only ever returns a
document-indexing result.
"""
from __future__ import annotations

from datetime import datetime

from app.contracts.enums import DocType, Language
from app.contracts.schemas import IngestDoc, IngestResult, Passage, RetrievalResult


class FakeRetriever:
    def __init__(self) -> None:
        self._docs = 0
        self._chunks = 0

    def retrieve(
        self, query: str, as_of: datetime, k: int = 5,
        language: str | None = None, doc_types: list[str] | None = None,
    ) -> RetrievalResult:
        passage = Passage(
            chunk_id="RUL-CAN-01#3",
            doc_id="RUL-CAN-01",
            doc_type=DocType.RULE,
            section="3. Refund table",
            text="Cancelling 2AC 48h or more before departure costs Rs 200.",
            score=0.81,
            language=Language.EN,
        )
        return RetrievalResult(passages=[passage])

    def ingest(self, doc: IngestDoc) -> IngestResult:
        self._docs += 1
        self._chunks += len(doc.sections)
        return IngestResult(
            doc_id=doc.doc_id, action="created", sections_indexed=len(doc.sections)
        )

    def stats(self) -> dict[str, int]:
        return {"docs": self._docs, "chunks": self._chunks}
