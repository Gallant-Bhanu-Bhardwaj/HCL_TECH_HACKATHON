"""
rag.py - search over Ujjwal Rail rules, circulars and FAQs (brief R3, R6, R11).

  search(query, as_of)  -> the best matching sections, each with doc_id and section for citing
  ingest(doc)           -> add or update a document while the server runs (no restart)

How it works:
  - Every document in data/docs is split at its "## " headings; each section is one chunk.
  - Chunks are ranked by BM25 keywords and, if the model loads, multilingual embeddings.
    The two rankings are merged. Without the model, keyword search still works.
  - Date rules: a document counts only between its effective_from and effective_to.
    A circular or FAQ replaced by a newer circular that is already in force is dropped.
    A rule is kept (it holds other values too), but the newer circular is added next to it.
"""
import os
import re
from datetime import date
from pathlib import Path

import yaml
from rank_bm25 import BM25Okapi

from app.db import connect

DOCS_DIR = Path(os.getenv("DOCS_DIR", "data/docs"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")  # "" turns embeddings off
TOP_K = 4
MIN_SIMILARITY = 0.35          # embedding score a chunk needs when it shares no keyword
MIN_KEYWORD = 2.5              # below this best keyword score the question is off-topic

CHUNKS = []                    # one dict per section
INDEX = {"bm25": None, "vectors": None, "embedder": None}


# ---------- loading ----------

def tokens(text):
    return re.findall(r"[\wऀ-ॿ]+", text.lower())   # keeps Hindi words whole


def parse(markdown):
    """Front matter (between the first two '---' lines) + one chunk per '## ' section."""
    _, head, body = markdown.split("---", 2)
    meta = yaml.safe_load(head)
    doc = {"doc_id": meta["doc_id"], "doc_type": meta.get("doc_type", "rule"),
           "title": meta.get("title", ""), "language": meta.get("language", "en"),
           "effective_from": str(meta.get("effective_from") or "2000-01-01"),
           "effective_to": str(meta["effective_to"]) if meta.get("effective_to") else None,
           "supersedes": meta.get("supersedes") or [],
           "superseded_by": meta.get("superseded_by") or [],
           "outdated": bool(meta.get("outdated"))}
    chunks = []
    for part in body.split("\n## ")[1:]:
        section, _, text = part.partition("\n")
        chunks.append({**doc, "section": section.strip(), "text": text.strip()})
    return chunks


def load_docs():
    CHUNKS.clear()
    for path in sorted(DOCS_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):            # skips INDEX.md and other notes
            CHUNKS.extend(parse(text))
    rebuild()


def rebuild():
    texts = [f"{c['title']} {c['section']} {c['text']}" for c in CHUNKS]
    INDEX["bm25"] = BM25Okapi([tokens(t) for t in texts])
    if INDEX["embedder"] is None and EMBED_MODEL:
        try:
            from sentence_transformers import SentenceTransformer
            INDEX["embedder"] = SentenceTransformer(EMBED_MODEL)
        except Exception as e:                 # no internet / no model: keywords only
            print(f"rag: embeddings off ({e.__class__.__name__}), using keyword search only")
            INDEX["embedder"] = False
    if INDEX["embedder"]:
        INDEX["vectors"] = INDEX["embedder"].encode(texts, normalize_embeddings=True)


def ensure_loaded():
    if not CHUNKS:
        load_docs()


# ---------- date rules ----------

def live_circulars(day):
    return {c["doc_id"] for c in CHUNKS if c["doc_type"] == "circular" and in_dates(c, day)}


def in_dates(c, day):
    return c["effective_from"] <= day and (c["effective_to"] is None or day <= c["effective_to"])


def counts_on(c, day, live, replaced):
    """Should this chunk be used for an answer given on this day?"""
    if not in_dates(c, day):
        return False
    if c["doc_type"] == "faq" and c["outdated"]:
        # an outdated FAQ is dropped once a circular that replaces it is in force
        return not c["superseded_by"] or not (set(c["superseded_by"]) & live)
    if c["doc_type"] == "circular" and c["doc_id"] in replaced:
        return False                           # an older circular replaced by a newer one
    return True


# ---------- search ----------

def search(query, passenger_id=None, as_of=None, k=TOP_K):
    """Best sections for the query on the day of as_of. Each result can be cited by doc_id + section."""
    ensure_loaded()
    day = str(as_of or date.today())[:10]
    live = live_circulars(day)
    replaced = {old for c in CHUNKS if c["doc_id"] in live for old in c["supersedes"]}

    keyword = INDEX["bm25"].get_scores(tokens(query))
    meaning = None
    if INDEX["embedder"]:
        meaning = INDEX["vectors"] @ INDEX["embedder"].encode([query], normalize_embeddings=True)[0]

    # merge the two rankings (reciprocal rank fusion), keeping only relevant chunks
    score = {}
    rankings = [sorted(range(len(CHUNKS)), key=lambda i: -keyword[i])]
    if meaning is not None:
        rankings.append(sorted(range(len(CHUNKS)), key=lambda i: -meaning[i]))
    for ranking in rankings:
        for pos, i in enumerate(ranking):
            score[i] = score.get(i, 0) + 1 / (60 + pos)
    on_topic = max(keyword, default=0) >= MIN_KEYWORD
    relevant = [i for i in score if (on_topic and keyword[i] > 0)
                or (meaning is not None and meaning[i] >= MIN_SIMILARITY)]
    ranked = sorted(relevant, key=lambda i: -score[i])

    hits = [CHUNKS[i] for i in ranked if counts_on(CHUNKS[i], day, live, replaced)][:k]

    # a rule changed by a circular that is in force: put the circular next to it (R6)
    for c in list(hits):
        for i in ranked:
            newer = CHUNKS[i]
            if newer["doc_id"] in live and c["doc_id"] in newer["supersedes"] and newer not in hits \
                    and counts_on(newer, day, live, replaced):
                hits.append(newer)
                break

    return [{"doc_id": c["doc_id"], "section": c["section"], "title": c["title"],
             "doc_type": c["doc_type"], "effective_from": c["effective_from"],
             "note": newer_note(c, live), "text": c["text"]} for c in hits]


def newer_note(c, live):
    newer = sorted(x["doc_id"] for x in CHUNKS if x["doc_id"] in live and c["doc_id"] in x["supersedes"])
    return f"Revised by {', '.join(dict.fromkeys(newer))}: the circular wins where they differ." if newer else ""


# ---------- ingest ----------

def ingest(doc):
    """Add or replace a document. Send either
         {"markdown": "<full file with front matter>"}
       or {"doc_id", "doc_type", "title", "effective_from", "text", ...optional "supersedes", "effective_to", "language"}.
       Optional "settings": [{"name", "value", "effective_from"}] adds rows to the settings table,
       so refund and fare code uses the new numbers from that date."""
    ensure_loaded()
    markdown = doc.get("markdown") or to_markdown(doc)
    new = parse(markdown)
    if not new:
        return {"error": "the document has no '## ' sections"}
    doc_id, doc_type = new[0]["doc_id"], new[0]["doc_type"]

    folder = DOCS_DIR / f"{doc_type}s"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{doc_id}.md").write_text(markdown, encoding="utf-8")

    CHUNKS[:] = [c for c in CHUNKS if c["doc_id"] != doc_id] + new   # replaces an older version
    rebuild()

    settings = doc.get("settings") or []
    with connect() as con:
        for s in settings:
            con.execute("INSERT INTO settings (name, value, source_doc, effective_from) VALUES (?, ?, ?, ?)",
                        (s["name"], s["value"], doc_id, s.get("effective_from", new[0]["effective_from"])))
    return {"doc_id": doc_id, "chunks": len(new), "settings_added": len(settings)}


def to_markdown(doc):
    meta = {key: doc[key] for key in ["doc_id", "doc_type", "title", "effective_from", "effective_to",
                                       "supersedes", "language"] if doc.get(key)}
    text = doc.get("text", "")
    if not text.lstrip().startswith("## "):
        text = "## 1. Text\n" + text
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n" + text + "\n"
