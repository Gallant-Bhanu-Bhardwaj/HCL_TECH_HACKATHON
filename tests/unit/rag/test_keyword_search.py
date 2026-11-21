"""FTS5 keyword retrieval tests."""
from __future__ import annotations

from app.rag.ingest import ingest_all
from app.rag.keyword_search import _build_match_expression, fts5_search


def test_devanagari_words_are_not_fragmented_by_combining_marks():
    """Regression test for a real bug found during retrieval-quality
    work: Python's `\\w+` excludes Unicode category Mc/Mn (combining
    marks) — Devanagari vowel signs (matras) are exactly that
    category, so `\\w+` split "टिकट" into "ट" + "कट". The tokenizer
    must keep the whole word intact."""
    tokens = _build_match_expression("मेरा टिकट रद्द करने पर")
    assert '"टिकट"' in tokens
    assert '"ट"' not in tokens.split(" OR ")  # the old, broken fragment must not appear
    assert '"कट"' not in tokens.split(" OR ")


def test_booking_id_with_hyphen_stays_one_token():
    tokens = _build_match_expression("Cancel my booking UR-30418.")
    assert '"UR-30418"' in tokens


def test_finds_relevant_chunks_for_cancellation_query(conn):
    ingest_all(conn)
    hits = fts5_search(conn, "cancellation charge refund", limit=10)
    chunk_ids = [h.chunk_id for h in hits]
    assert any("RUL-CAN-01" in cid for cid in chunk_ids)
    # bm25-derived score: higher must mean better (first hit scores >= last hit)
    assert hits[0].score >= hits[-1].score


def test_empty_query_returns_nothing(conn):
    ingest_all(conn)
    assert fts5_search(conn, "") == []


def test_no_match_returns_empty_list_not_an_error(conn):
    ingest_all(conn)
    assert fts5_search(conn, "xylophone nonexistent gibberish term") == []


def test_hindi_query_finds_the_hindi_faq(conn):
    ingest_all(conn)
    hits = fts5_search(conn, "वापस", limit=10)
    assert any(h.chunk_id.startswith("FAQ-19") for h in hits)
