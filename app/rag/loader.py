"""Document loader (architecture §7.1, api-contracts §5.1): parses the
Markdown + YAML-front-matter files under data/documents/ directly —
RAG owns this parsing, independent of the Data & Testing seed script
(data/generator/generate_data.py has its own, cruder copy; the two are
intentionally separate per architecture §8's module-ownership rule).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_ROOT = REPO_ROOT / "data" / "documents"

_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass(frozen=True)
class DocumentSection:
    section: str
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    doc_id: str
    doc_type: str  # 'rule' | 'circular' | 'faq'
    title: str
    effective_from: str  # ISO date, e.g. "2026-01-01"
    effective_to: str | None
    supersedes: tuple[str, ...]
    # Additive, FAQ-only (data/documents/faqs/*.md): the inverse of
    # `supersedes` — this doc has been superseded by these doc_ids.
    # Not written by data/generator/generate_data.py into
    # documents.supersedes_json (that column only ever holds the
    # *forward* `supersedes:` key), so the loader reads it straight
    # from the file to build a correct supersession graph (see
    # app/rag/supersession.py) without touching the seed data.
    superseded_by: tuple[str, ...]
    language: str
    status: str
    sections: tuple[DocumentSection, ...]
    source_path: str


class DocumentParseError(Exception):
    """A .md file under data/documents/ is missing front matter or a
    required field. Raised, never silently skipped — a malformed
    document must not be indexed as if it were valid."""


def _parse_front_matter(raw: str) -> dict:
    meta: dict = {}
    for line in raw.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [v.strip() for v in inner.split(",") if v.strip()]
        elif value == "":
            meta[key] = None
        else:
            meta[key] = value
    return meta


def _split_sections(body: str) -> tuple[DocumentSection, ...]:
    sections: list[DocumentSection] = []
    heading, lines = None, []
    for line in body.splitlines():
        if line.startswith("## "):
            if heading is not None:
                sections.append(DocumentSection(heading, "\n".join(lines).strip()))
            heading, lines = line[3:].strip(), []
        else:
            lines.append(line)
    if heading is not None:
        sections.append(DocumentSection(heading, "\n".join(lines).strip()))
    return tuple(sections)


def parse_document(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        raise DocumentParseError(f"{path}: missing --- front matter ---")
    meta = _parse_front_matter(match.group(1))

    required = ["doc_id", "doc_type", "title", "effective_from", "language"]
    missing = [k for k in required if not meta.get(k)]
    if missing:
        raise DocumentParseError(f"{path}: missing required front-matter field(s) {missing}")

    sections = _split_sections(match.group(2))
    if not sections:
        raise DocumentParseError(f"{path}: no '## ' sections found — refuses to index an empty document")

    supersedes = tuple(meta.get("supersedes") or [])
    superseded_by = tuple(meta.get("superseded_by") or [])

    return ParsedDocument(
        doc_id=meta["doc_id"],
        doc_type=meta["doc_type"],
        title=meta["title"],
        effective_from=meta["effective_from"],
        effective_to=meta.get("effective_to"),
        supersedes=supersedes,
        superseded_by=superseded_by,
        language=meta["language"],
        status=meta.get("status") or "active",
        sections=sections,
        source_path=str(path),
    )


def load_all_documents(docs_root: Path | str = DEFAULT_DOCS_ROOT) -> list[ParsedDocument]:
    """Loads every *.md under rules/, circulars/, faqs/ — NOT INDEX.md,
    which is a human-readable table of contents, not a policy document."""
    root = Path(docs_root)
    docs: list[ParsedDocument] = []
    for subdir in ("rules", "circulars", "faqs"):
        for path in sorted((root / subdir).glob("*.md")):
            docs.append(parse_document(path))
    return docs
