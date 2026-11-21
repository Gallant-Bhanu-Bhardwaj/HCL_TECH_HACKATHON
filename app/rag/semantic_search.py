"""Semantic retrieval: cosine similarity over the embeddings stored in
`chunk_vectors` (architecture §5.2/§10 — "FAISS-flat or plain NumPy is
equally fine; interface hides which"). Pure Python/stdlib: with ~105
chunks there is no need for a vector index or an extra dependency.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

from app.rag.embeddings import unpack_vector


@dataclass(frozen=True)
class SemanticHit:
    chunk_id: str
    score: float  # cosine similarity, -1..1, higher = more similar


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_search(conn: sqlite3.Connection, query_vector: list[float], limit: int = 20) -> list[SemanticHit]:
    rows = conn.execute("SELECT chunk_id, embedding, dim FROM chunk_vectors").fetchall()
    hits = [
        SemanticHit(chunk_id=row["chunk_id"], score=_cosine(query_vector, unpack_vector(row["embedding"], row["dim"])))
        for row in rows
        if row["dim"] == len(query_vector)  # a dimension mismatch (different EMBED_MODEL) is skipped, not crashed on
    ]
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]
