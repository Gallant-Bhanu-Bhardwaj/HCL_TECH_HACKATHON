"""Retrieval-quality evaluation harness (Recall@k, MRR) against
eval/eval_set.json's expected_document_citations — the only questions
that carry RAG ground truth (tool-only/behavioral questions have none
and are correctly excluded, not treated as 0).

Added as a permanent, reusable part of app/rag/ rather than an ad-hoc
script, since retrieval-ranking work needs to re-run this repeatedly
(flagged as missing in the prior RAG task's report).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.rag.embeddings import Embedder
from app.rag.retrieve import retrieve_context

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_PATH = REPO_ROOT / "eval" / "eval_set.json"
DEFAULT_AS_OF = date(2026, 12, 3)  # the data kit's own reference date


@dataclass(frozen=True)
class QuestionResult:
    test_id: str
    category: str
    hit_rank: int | None  # 1-based rank of the first expected citation found, None if missed
    top_passages: tuple[tuple[str, str], ...]  # (doc_id, section) actually returned, for inspection


@dataclass(frozen=True)
class EvalReport:
    n: int
    recall_at_k: float
    mrr: float
    per_question: tuple[QuestionResult, ...]

    def misses(self) -> list[QuestionResult]:
        return [q for q in self.per_question if q.hit_rank is None]


def _as_of_for(question: dict) -> date:
    raw = question.get("as_of")
    if raw:
        return date.fromisoformat(raw.split("T")[0])
    return DEFAULT_AS_OF


def load_ground_truth_questions(eval_path: Path | str = DEFAULT_EVAL_PATH) -> list[dict]:
    data = json.loads(Path(eval_path).read_text(encoding="utf-8"))
    return [q for q in data if q.get("expected_document_citations")]


def evaluate_retrieval(
    conn: sqlite3.Connection,
    embedder: Embedder | None = None,
    eval_path: Path | str = DEFAULT_EVAL_PATH,
    top_k: int = 5,
    keyword_only: bool | None = None,
    **retrieve_kwargs,
) -> EvalReport:
    """Runs retrieve_context() for every eval question that has
    expected_document_citations and scores Recall@top_k and MRR
    against those citations. Extra `retrieve_kwargs` are forwarded to
    retrieve_context() unchanged, so experimental parameters (fusion
    method, weights, ...) can be A/B tested without editing this file.
    """
    questions = load_ground_truth_questions(eval_path)
    results: list[QuestionResult] = []
    hits = 0
    reciprocal_ranks = 0.0

    for q in questions:
        expected = {(c["doc_id"], c["section"]) for c in q["expected_document_citations"]}
        result = retrieve_context(
            conn, q["user_query"], as_of=_as_of_for(q), top_k=top_k,
            embedder=embedder, keyword_only=keyword_only, **retrieve_kwargs,
        )
        ranked = [(p.doc_id, p.section) for p in result.passages]
        hit_rank = next((i for i, pair in enumerate(ranked, start=1) if pair in expected), None)
        if hit_rank is not None:
            hits += 1
            reciprocal_ranks += 1.0 / hit_rank
        results.append(QuestionResult(
            test_id=q["test_id"], category=q["category"], hit_rank=hit_rank, top_passages=tuple(ranked),
        ))

    n = len(questions)
    return EvalReport(
        n=n, recall_at_k=hits / n if n else 0.0, mrr=reciprocal_ranks / n if n else 0.0,
        per_question=tuple(results),
    )
