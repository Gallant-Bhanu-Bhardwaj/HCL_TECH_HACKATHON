"""Document loader + chunker tests."""
from __future__ import annotations

import pytest

from app.rag.chunker import chunk_document
from app.rag.loader import DocumentParseError, load_all_documents, parse_document


def test_loads_all_38_documents():
    docs = load_all_documents()
    assert len(docs) == 38
    doc_types = {d.doc_type for d in docs}
    assert doc_types == {"rule", "circular", "faq"}


def test_rul_can_01_parses_with_expected_metadata():
    docs = {d.doc_id: d for d in load_all_documents()}
    doc = docs["RUL-CAN-01"]
    assert doc.doc_type == "rule"
    assert doc.effective_from == "2026-01-01"
    assert doc.supersedes == ()
    assert doc.language == "en"
    assert doc.status == "active"
    section_titles = [s.section for s in doc.sections]
    assert "3. Refund table (confirmed travellers)" in section_titles


def test_cir_2026_11_supersedes_two_documents():
    docs = {d.doc_id: d for d in load_all_documents()}
    doc = docs["CIR-2026-11"]
    assert set(doc.supersedes) == {"RUL-CAN-01", "CIR-2026-07"}
    assert doc.effective_from == "2026-12-10"


def test_faq_07_declares_superseded_by():
    docs = {d.doc_id: d for d in load_all_documents()}
    doc = docs["FAQ-07"]
    assert set(doc.superseded_by) == {"CIR-2026-07", "CIR-2026-11"}


def test_chunker_preserves_source_metadata_per_section():
    docs = {d.doc_id: d for d in load_all_documents()}
    chunks = chunk_document(docs["RUL-CAN-01"])
    assert len(chunks) == len(docs["RUL-CAN-01"].sections)
    sample = next(c for c in chunks if c.section == "3. Refund table (confirmed travellers)")
    assert sample.chunk_id == "RUL-CAN-01#3. Refund table (confirmed travellers)"
    assert sample.doc_id == "RUL-CAN-01"
    assert sample.doc_type == "rule"
    assert "Rs 150" in sample.text  # the table itself, not lost to chunking
    assert sample.effective_from == "2026-01-01"


def test_malformed_document_raises_not_silently_skipped(tmp_path):
    bad = tmp_path / "BAD-01.md"
    bad.write_text("no front matter here\n## Just a heading\ntext", encoding="utf-8")
    with pytest.raises(DocumentParseError):
        parse_document(bad)


def test_document_with_no_sections_is_rejected(tmp_path):
    bad = tmp_path / "BAD-02.md"
    bad.write_text(
        "---\ndoc_id: BAD-02\ndoc_type: rule\ntitle: Empty\neffective_from: 2026-01-01\nlanguage: en\n---\nno headings at all\n",
        encoding="utf-8",
    )
    with pytest.raises(DocumentParseError):
        parse_document(bad)
