"""POST /ingest (api-contracts §5.2).

D2 (v1.2): document fields and `settings_changes` are validated and
applied as two independent parts of the same request — neither is ever
derived from the other. No X-Passenger-Id required (O8: /ingest is
open, but every call is still traced).

Phase 0 scope: validates settings_changes against the key registry and
forwards document text to the wired Retriever. Markdown-front-matter
parsing (§5.1) and real `settings`/`settings_history` persistence are
Backend/RAG work for Phase 1 (T11, T5).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_clock, get_retriever, get_trace_store
from app.api.errors import BadRequest
from app.contracts.schemas import DocSection, IngestDoc, IngestRequest, IngestResponse, TraceRecord
from app.contracts.settings_keys import is_registered, value_matches_type

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    body: IngestRequest,
    retriever=Depends(get_retriever),
    trace_store=Depends(get_trace_store),
    clock=Depends(get_clock),
) -> IngestResponse:
    # --- settings_changes: validated independently of the document text (D2) ---
    settings_changes = body.settings_changes or []
    known_doc_ids = {d for d in [body.doc_id] if d} | set(body.supersedes or [])
    for change in settings_changes:
        if not is_registered(change.name):
            raise BadRequest(f"'{change.name}' is not a registered settings key.")
        if not value_matches_type(change.name, change.value):
            raise BadRequest(f"Value for '{change.name}' does not match its registered type.")
        if change.source_doc != body.doc_id and change.source_doc not in known_doc_ids:
            raise BadRequest(
                f"source_doc '{change.source_doc}' must be this request's doc_id or an already-known doc."
            )

    # --- document text: indexed only if sections/markdown were actually sent ---
    sections_indexed = 0
    superseded_detected: list[str] = []
    action = "created"
    if body.sections and body.doc_id and body.doc_type and body.title and body.effective_from and body.language:
        doc = IngestDoc(
            doc_id=body.doc_id, doc_type=body.doc_type, title=body.title,
            effective_from=body.effective_from, effective_to=body.effective_to,
            supersedes=body.supersedes, language=body.language,
            sections=[DocSection(section=s.section, text=s.text) for s in body.sections],
        )
        result = retriever.ingest(doc)
        sections_indexed = result.sections_indexed
        superseded_detected = result.superseded_detected
        action = result.action
    elif body.markdown:
        # Phase 1 (RAG, T11): parse the §5.1 front-matter format. Phase 0
        # does not invent a parser here — tracked as remaining work.
        raise BadRequest("Raw markdown ingest is not implemented in Phase 0; use the structured fields.")

    trace_id = uuid.uuid4().hex[:8]
    now = clock.now_utc()
    trace_store.save(
        TraceRecord(
            trace_id=trace_id,
            created_at=now,
            as_of=now,
            endpoint="/ingest",
            session_id=None,
            passenger_id="system",  # /ingest is not passenger-scoped (O8)
            request=body.model_dump(mode="json"),
            response={"sections_indexed": sections_indexed, "settings_applied": len(settings_changes)},
        )
    )

    return IngestResponse(
        doc_id=body.doc_id,
        action=action,
        sections_indexed=sections_indexed,
        settings_applied=len(settings_changes),
        settings_history_ids=list(range(1, len(settings_changes) + 1)),  # placeholder sequence (Phase 0)
        superseded_detected=superseded_detected,
        indexed_at=now,
        trace_id=trace_id,
    )
