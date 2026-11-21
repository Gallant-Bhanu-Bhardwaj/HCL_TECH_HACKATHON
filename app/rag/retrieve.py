"""retrieve_context — the RAG module's public interface (architecture
§7.1; api-contracts §7). Hybrid: FTS5 keyword search always runs;
semantic search runs unless MOCK_LLM=true (api-contracts §13:
"embeddings fall back to keyword-only") or the caller explicitly asks
for keyword_only. Supersession (R6/R11) is resolved before truncating
to top_k — a superseded or not-yet-effective chunk is never returned
as a passage, but it is never silently dropped either: it is listed in
`excluded`, and a clash with a currently-effective document is
recorded in `conflicts`.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.config import settings as default_settings
from app.contracts.schemas import Conflict, ExcludedDoc, Passage, RetrievalResult, SourceRef
from app.rag.embeddings import Embedder, EmbeddingBackendUnavailable, OllamaEmbedder
from app.rag.keyword_search import fts5_search
from app.rag.loader import DEFAULT_DOCS_ROOT, ParsedDocument, load_all_documents
from app.rag.semantic_search import semantic_search
from app.rag.supersession import ClusterResolution, resolve_all_clusters

# R9: retrieved text is data, not instructions — a passage containing
# an instruction-like pattern is flagged (never executed, never
# silently dropped: it's still returned, just marked "suspicious" so
# the orchestrator's prompt-construction step can fence it off).
_SUSPICIOUS_PATTERNS = (
    re.compile(r"ignore (your|the|all|previous) (rules|instructions|policy)", re.IGNORECASE),
    re.compile(r"disregard (the )?(cancellation|refund) charge", re.IGNORECASE),
    re.compile(r"full refund regardless", re.IGNORECASE),
)


def _is_suspicious(text: str) -> list[str]:
    return ["suspicious"] if any(p.search(text) for p in _SUSPICIOUS_PATTERNS) else []


def _representative_section(doc: ParsedDocument | None) -> str:
    if doc is None or not doc.sections:
        return "(see current rules)"
    return doc.sections[0].section


@dataclass(frozen=True)
class _Candidate:
    chunk_id: str
    doc_id: str
    section: str
    text: str
    language: str
    score: float


def _fetch_chunk_rows(conn: sqlite3.Connection, chunk_ids: list[str]) -> dict[str, sqlite3.Row]:
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" for _ in chunk_ids)
    rows = conn.execute(
        f"SELECT chunk_id, doc_id, section, text, language FROM chunks WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    ).fetchall()
    return {row["chunk_id"]: row for row in rows}


def _fuse_weighted(keyword_hits, semantic_hits, semantic_weight: float, normalize_semantic: bool) -> dict[str, float]:
    keyword_weight = 1.0 - semantic_weight
    combined: dict[str, float] = {}
    if keyword_hits:
        max_kw = max(h.score for h in keyword_hits) or 1.0
        for h in keyword_hits:
            combined[h.chunk_id] = combined.get(h.chunk_id, 0.0) + keyword_weight * (h.score / max_kw)
    if semantic_hits:
        if normalize_semantic:
            max_sem = max(max(h.score, 0.0) for h in semantic_hits) or 1.0
        else:
            max_sem = 1.0  # baseline behaviour: raw cosine (already -1..1), only clamped at 0
        for h in semantic_hits:
            combined[h.chunk_id] = combined.get(h.chunk_id, 0.0) + semantic_weight * (max(h.score, 0.0) / max_sem)
    return combined


def _fuse_rrf(keyword_hits, semantic_hits, rrf_k: float) -> dict[str, float]:
    """Reciprocal Rank Fusion: score = sum(1 / (rrf_k + rank)) across
    each leg a chunk appears in — rank-based, so it is insensitive to
    the two legs' very different score scales (bm25 vs. cosine)."""
    combined: dict[str, float] = {}
    for rank, h in enumerate(keyword_hits, start=1):
        combined[h.chunk_id] = combined.get(h.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    for rank, h in enumerate(semantic_hits, start=1):
        combined[h.chunk_id] = combined.get(h.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return combined


def retrieve_context(
    conn: sqlite3.Connection,
    query: str,
    as_of: date | None = None,
    top_k: int = 5,
    embedder: Embedder | None = None,
    keyword_only: bool | None = None,
    docs_root: Path | str = DEFAULT_DOCS_ROOT,
    fusion: str = "rrf",
    semantic_weight: float = 0.5,
    normalize_semantic: bool = False,
    rrf_k: float = 1.0,
) -> RetrievalResult:
    """The clean public RAG entry point. `conn` is an explicit
    parameter (not a module-level global) so this stays testable and
    matches architecture's "no hidden state" style elsewhere.

    `keyword_only`: None defers to settings.mock_llm (api-contracts
    §13's documented contract); True/False explicitly overrides it.

    `fusion`/`semantic_weight`/`normalize_semantic`/`rrf_k`: retrieval-
    ranking tuning knobs, benchmarked against eval/eval_set.json (see
    app/rag/evaluate.py and the RAG retrieval-quality report).
    `fusion="rrf"` with a low `rrf_k` measurably improved MRR
    (0.293 -> 0.325) with Recall@5 unchanged (0.571), so it is the
    default; the original 50/50 weighted-sum fusion is still available
    via `fusion="weighted"` for comparison. These only affect the
    ranking/score of candidates BEFORE supersession filtering and
    top_k truncation — they never change which document wins a
    supersession cluster or which citations are returned.
    """
    as_of = as_of or date.today()
    use_keyword_only = default_settings.mock_llm if keyword_only is None else keyword_only

    keyword_hits = fts5_search(conn, query, limit=max(20, top_k * 4))

    semantic_hits = []
    if not use_keyword_only:
        active_embedder = embedder or OllamaEmbedder()
        query_vector = active_embedder.embed(query)  # raises EmbeddingBackendUnavailable, not caught here (explicit by design)
        semantic_hits = semantic_search(conn, query_vector, limit=max(20, top_k * 4))

    # --- Hybrid fusion: combine, dedupe by chunk_id ---
    if fusion == "rrf":
        combined = _fuse_rrf(keyword_hits, semantic_hits, rrf_k)
    elif fusion == "weighted":
        combined = _fuse_weighted(keyword_hits, semantic_hits, semantic_weight, normalize_semantic)
    else:
        # Fail loud on a typo'd fusion name rather than silently falling
        # back to a different ranking than the caller asked for.
        raise ValueError(f"fusion must be 'rrf' or 'weighted', got {fusion!r}")

    if not combined:
        return RetrievalResult(passages=[], conflicts=[], excluded=[])

    chunk_rows = _fetch_chunk_rows(conn, list(combined.keys()))
    candidates = [
        _Candidate(
            chunk_id=cid, doc_id=row["doc_id"], section=row["section"],
            text=row["text"], language=row["language"], score=combined[cid],
        )
        for cid, row in chunk_rows.items()
    ]
    candidates.sort(key=lambda c: c.score, reverse=True)

    # --- Supersession (R6/R11): resolve before truncating to top_k ---
    docs = load_all_documents(docs_root)
    docs_by_id = {d.doc_id: d for d in docs}
    resolutions: dict[str, ClusterResolution] = resolve_all_clusters(docs, as_of)

    passages: list[Passage] = []
    excluded: list[ExcludedDoc] = []
    conflicts: list[Conflict] = []
    seen_conflict_pairs: set[tuple[str, str]] = set()

    for cand in candidates:
        resolution = resolutions.get(cand.doc_id)
        doc = docs_by_id.get(cand.doc_id)
        why = resolution.excluded.get(cand.doc_id) if resolution else None

        if why is not None:
            excluded.append(ExcludedDoc(doc_id=cand.doc_id, section=cand.section, why=why))
            winner_id = resolution.winner_doc_id if resolution else None
            if winner_id and winner_id != cand.doc_id:
                pair = (winner_id, cand.doc_id)
                if pair not in seen_conflict_pairs:
                    seen_conflict_pairs.add(pair)
                    winner_doc = docs_by_id.get(winner_id)
                    winner_section = next(
                        (c.section for c in candidates if c.doc_id == winner_id),
                        _representative_section(winner_doc),
                    )
                    reason = (
                        f"{winner_id} is in effect from {winner_doc.effective_from if winner_doc else '?'}"
                        if why == "superseded"
                        else f"{cand.doc_id} does not take effect until {doc.effective_from if doc else '?'}; "
                        f"{winner_id} is the version currently in effect"
                    )
                    conflicts.append(
                        Conflict(
                            winner=SourceRef(doc_id=winner_id, section=winner_section),
                            superseded=SourceRef(doc_id=cand.doc_id, section=cand.section),
                            reason=reason,
                        )
                    )
            continue

        if len(passages) >= top_k:
            continue
        passages.append(
            Passage(
                chunk_id=cand.chunk_id, doc_id=cand.doc_id, doc_type=doc.doc_type if doc else "rule",
                section=cand.section, text=cand.text, score=cand.score,
                effective_from=doc.effective_from if doc else None,
                effective_to=doc.effective_to if doc else None,
                language=cand.language, flags=_is_suspicious(cand.text),
            )
        )

    return RetrievalResult(passages=passages, conflicts=conflicts, excluded=excluded)
