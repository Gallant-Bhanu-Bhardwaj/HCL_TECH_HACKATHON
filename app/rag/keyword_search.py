"""Keyword retrieval via the existing FTS5 virtual table (architecture
§5.2). `chunks_fts` already exists in db/schema.sql, kept in sync with
`chunks` by triggers — this module creates nothing, it only queries.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class KeywordHit:
    chunk_id: str
    score: float  # higher = better match (negated bm25; bm25 itself is "lower is better")


# NOT `\w+`: Python's `\w` only matches Unicode categories L/N/_ , which
# EXCLUDES combining marks (category Mc/Mn) — Devanagari vowel signs
# (matras) are exactly that category. "टिकट" (ticket) = ट + ि(Mc) + क + ट
# would fragment into "ट" and "कट" under `\w+`, silently breaking every
# Hindi word containing a matra (nearly all of them) into nonsense
# pieces. Verified directly: `unicodedata.category('ि')` is `Mc`.
# Splitting on whitespace and ASCII punctuation instead keeps any
# contiguous run of other characters — Devanagari consonant+matra
# clusters included — as one token.
_WORD_RE = re.compile(r"[^\s.,!?;:'\"()\[\]{}]+")

# A small English stopword list — without this, OR-matching every raw
# token means a genuinely off-topic question ("What is the weather
# like tomorrow?") still matches SOME chunk purely via a trivial
# common word ("what", "is", "the", "like"), which defeats the point
# of keyword relevance entirely. Short on purpose: better to under-
# filter (leave a rare borderline word in) than to accidentally strip
# a real content word in a short query.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am",
    "i", "me", "my", "you", "your", "it", "its", "this", "that",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "do", "does", "did", "can", "could", "will", "would", "should",
    "to", "of", "in", "on", "at", "for", "and", "or", "but", "if",
    "with", "about", "like", "please", "have", "has", "had",
}


def _build_match_expression(query: str) -> str | None:
    """FTS5's default MATCH syntax treats space-separated terms as an
    implicit AND — fine for a short, deliberate keyword query, but it
    means a natural-language sentence ("Can I bring my pet dog on the
    train?") almost never matches anything, since no chunk contains
    every single word. Tokenising and joining with OR instead lets any
    significant word match, with bm25 still ranking chunks that match
    more terms higher. Each token is double-quoted so punctuation
    inside the original query (hyphens in "UR-30418", question marks,
    Devanagari text) can never be parsed as FTS5 query syntax.
    """
    tokens = [t for t in _WORD_RE.findall(query) if t.lower() not in _STOPWORDS]
    if not tokens:
        return None
    return " OR ".join(f'"{t}"' for t in tokens)


def fts5_search(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[KeywordHit]:
    match_expr = _build_match_expression(query)
    if match_expr is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT chunks.chunk_id AS chunk_id, bm25(chunks_fts) AS raw_score
            FROM chunks_fts
            JOIN chunks ON chunks.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY raw_score
            LIMIT ?
            """,
            (match_expr, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        # A malformed FTS5 query string — treat as "no keyword matches"
        # rather than letting a user query 500.
        return []
    return [KeywordHit(chunk_id=row["chunk_id"], score=-row["raw_score"]) for row in rows]
