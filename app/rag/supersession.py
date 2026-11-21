"""Versioning / supersession resolution (R6, R11; architecture D4/D6;
master data-generation prompt's "future-effective circular" and
"outdated FAQ" edge cases).

Builds, from the loaded documents' `supersedes`/`superseded_by` edges,
connected clusters of mutually-related documents (e.g. {RUL-CAN-01,
CIR-2026-07, CIR-2026-11}), then for a given `as_of` date resolves each
cluster to exactly one winner: the cluster member with the latest
`effective_from` that is <= as_of, status='active', and not yet past
its `effective_to`. Every other matched member of that cluster is
EXCLUDED and the clash is recorded as a Conflict — never silently
dropped (task requirement: "flag conflicting sources instead of
silently hiding conflicts").

A future-effective circular can never win before its own
effective_from, however relevant it is to the query — it is excluded
as "not_yet_effective" and the current winner (an older, still-
effective document) is what's actually returned.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.rag.loader import ParsedDocument


@dataclass(frozen=True)
class ClusterResolution:
    winner_doc_id: str | None  # None only if nothing in the cluster is effective yet
    excluded: dict[str, str]  # doc_id -> "not_yet_effective" | "superseded" | "withdrawn"


def build_clusters(docs: list[ParsedDocument]) -> dict[str, frozenset[str]]:
    """doc_id -> the frozenset of doc_ids in its connected component
    (itself included), via BOTH supersedes (forward) and
    superseded_by (reverse, FAQ-only) edges."""
    adjacency: dict[str, set[str]] = {d.doc_id: set() for d in docs}
    known = set(adjacency)
    for doc in docs:
        for other in doc.supersedes:
            if other in known:
                adjacency[doc.doc_id].add(other)
                adjacency[other].add(doc.doc_id)
        for other in doc.superseded_by:
            if other in known:
                adjacency[doc.doc_id].add(other)
                adjacency[other].add(doc.doc_id)

    clusters: dict[str, frozenset[str]] = {}
    visited: set[str] = set()
    for start in adjacency:
        if start in visited:
            continue
        component: set[str] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            stack.extend(adjacency[node] - component)
        frozen = frozenset(component)
        for node in component:
            clusters[node] = frozen
        visited |= component
    return clusters


def _is_effective(doc: ParsedDocument, as_of: date) -> bool:
    if doc.status != "active":
        return False
    if date.fromisoformat(doc.effective_from) > as_of:
        return False
    if doc.effective_to and date.fromisoformat(doc.effective_to) <= as_of:
        return False
    return True


def resolve_cluster(cluster_doc_ids: frozenset[str], docs_by_id: dict[str, ParsedDocument], as_of: date) -> ClusterResolution:
    excluded: dict[str, str] = {}
    effective_candidates: list[ParsedDocument] = []

    for doc_id in cluster_doc_ids:
        doc = docs_by_id.get(doc_id)
        if doc is None:
            continue
        if _is_effective(doc, as_of):
            effective_candidates.append(doc)
        elif doc.status != "active":
            excluded[doc_id] = "withdrawn"
        elif date.fromisoformat(doc.effective_from) > as_of:
            excluded[doc_id] = "not_yet_effective"
        else:
            excluded[doc_id] = "withdrawn"  # its own effective_to window has closed

    if not effective_candidates:
        return ClusterResolution(winner_doc_id=None, excluded=excluded)

    winner = max(effective_candidates, key=lambda d: d.effective_from)
    for doc in effective_candidates:
        if doc.doc_id != winner.doc_id:
            excluded[doc.doc_id] = "superseded"

    return ClusterResolution(winner_doc_id=winner.doc_id, excluded=excluded)


def resolve_all_clusters(docs: list[ParsedDocument], as_of: date) -> dict[str, ClusterResolution]:
    """doc_id -> that doc's cluster's resolution (every doc_id in the
    same cluster maps to the identical ClusterResolution object)."""
    clusters = build_clusters(docs)
    docs_by_id = {d.doc_id: d for d in docs}
    resolved: dict[str, ClusterResolution] = {}
    seen_clusters: dict[frozenset[str], ClusterResolution] = {}
    for doc_id, cluster in clusters.items():
        if cluster not in seen_clusters:
            seen_clusters[cluster] = resolve_cluster(cluster, docs_by_id, as_of)
        resolved[doc_id] = seen_clusters[cluster]
    return resolved
