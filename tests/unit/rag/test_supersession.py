"""Direct unit tests for app/rag/supersession.py (previously only
exercised indirectly through retrieve_context's integration tests;
added during the final audit, which also found `_is_effective` was
dead code — now wired into `resolve_cluster` and covered here)."""
from __future__ import annotations

from datetime import date

from app.rag.loader import DocumentSection, ParsedDocument
from app.rag.supersession import _is_effective, build_clusters, resolve_cluster


def _doc(doc_id, effective_from="2026-01-01", effective_to=None, status="active",
         supersedes=(), superseded_by=()) -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id, doc_type="rule", title=doc_id, effective_from=effective_from,
        effective_to=effective_to, supersedes=tuple(supersedes), superseded_by=tuple(superseded_by),
        language="en", status=status, sections=(DocumentSection("1. Scope", "text"),), source_path="x",
    )


def test_is_effective_true_within_window():
    doc = _doc("A", effective_from="2026-01-01")
    assert _is_effective(doc, date(2026, 6, 1)) is True


def test_is_effective_false_before_effective_from():
    doc = _doc("A", effective_from="2026-06-01")
    assert _is_effective(doc, date(2026, 1, 1)) is False


def test_is_effective_false_after_effective_to():
    doc = _doc("A", effective_from="2026-01-01", effective_to="2026-06-01")
    assert _is_effective(doc, date(2026, 7, 1)) is False


def test_is_effective_false_when_withdrawn():
    doc = _doc("A", status="withdrawn")
    assert _is_effective(doc, date(2026, 6, 1)) is False


def test_build_clusters_links_forward_and_reverse_edges():
    docs = [
        _doc("RUL-X"),
        _doc("CIR-Y", supersedes=["RUL-X"]),
        _doc("FAQ-Z", superseded_by=["CIR-Y"]),
        _doc("UNRELATED"),
    ]
    clusters = build_clusters(docs)
    assert clusters["RUL-X"] == clusters["CIR-Y"] == clusters["FAQ-Z"] == frozenset({"RUL-X", "CIR-Y", "FAQ-Z"})
    assert clusters["UNRELATED"] == frozenset({"UNRELATED"})


def test_resolve_cluster_picks_latest_effective_as_winner():
    docs = {
        "RUL-X": _doc("RUL-X", effective_from="2026-01-01"),
        "CIR-Y": _doc("CIR-Y", effective_from="2026-06-01"),
    }
    cluster = frozenset(docs)
    resolution = resolve_cluster(cluster, docs, as_of=date(2026, 7, 1))
    assert resolution.winner_doc_id == "CIR-Y"
    assert resolution.excluded["RUL-X"] == "superseded"


def test_resolve_cluster_future_doc_is_not_yet_effective_not_the_winner():
    docs = {
        "RUL-X": _doc("RUL-X", effective_from="2026-01-01"),
        "CIR-Y": _doc("CIR-Y", effective_from="2026-12-10"),  # future relative to as_of below
    }
    cluster = frozenset(docs)
    resolution = resolve_cluster(cluster, docs, as_of=date(2026, 6, 1))
    assert resolution.winner_doc_id == "RUL-X"
    assert resolution.excluded["CIR-Y"] == "not_yet_effective"


def test_resolve_cluster_withdrawn_doc_is_excluded_as_withdrawn():
    docs = {
        "RUL-X": _doc("RUL-X", effective_from="2026-01-01"),
        "RUL-OLD": _doc("RUL-OLD", status="withdrawn"),
    }
    cluster = frozenset(docs)
    resolution = resolve_cluster(cluster, docs, as_of=date(2026, 6, 1))
    assert resolution.excluded["RUL-OLD"] == "withdrawn"


def test_resolve_cluster_closed_window_is_excluded_as_withdrawn():
    docs = {
        "RUL-X": _doc("RUL-X", effective_from="2026-01-01"),
        "CIR-OLD": _doc("CIR-OLD", effective_from="2025-01-01", effective_to="2025-06-01"),
    }
    cluster = frozenset(docs)
    resolution = resolve_cluster(cluster, docs, as_of=date(2026, 6, 1))
    assert resolution.excluded["CIR-OLD"] == "withdrawn"


def test_resolve_cluster_nothing_effective_yet_has_no_winner():
    docs = {"CIR-FUTURE": _doc("CIR-FUTURE", effective_from="2099-01-01")}
    cluster = frozenset(docs)
    resolution = resolve_cluster(cluster, docs, as_of=date(2026, 1, 1))
    assert resolution.winner_doc_id is None
    assert resolution.excluded["CIR-FUTURE"] == "not_yet_effective"
