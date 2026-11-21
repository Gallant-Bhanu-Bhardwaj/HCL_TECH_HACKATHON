"""Embeddings: real Ollama client + SQLite BLOB storage (architecture
§5.2, §10; api-contracts §13).

MOCK_LLM contract (api-contracts §13): "embeddings fall back to
keyword-only" under MOCK_LLM=true — that is decided one layer up, in
app/rag/retrieve.py, which skips calling this module entirely in that
mode. This module itself never fabricates a vector: if Ollama is
unreachable or returns something unusable, `OllamaEmbedder.embed()`
raises EmbeddingBackendUnavailable — it is never silently skipped, and
no caller may claim a real embedding was produced unless this method
actually returned one (task rule: "Do not claim real embeddings were
generated unless verified").
"""
from __future__ import annotations

import sqlite3
import struct
from typing import Protocol, runtime_checkable

import httpx

from app.config import settings as default_settings


class EmbeddingBackendUnavailable(Exception):
    """Ollama could not be reached, or returned an unusable response.
    Never caught-and-ignored by this module — callers decide whether
    to surface it as an error or fall back to keyword-only."""


@runtime_checkable
class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...

    @property
    def model(self) -> str: ...


class OllamaEmbedder:
    """Calls the real Ollama embeddings API. Raises
    EmbeddingBackendUnavailable on any connection failure, timeout, or
    malformed response — this class never returns a fabricated vector.
    """

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float = 30.0) -> None:
        self._base_url = (base_url or default_settings.ollama_url).rstrip("/")
        self._model = model or default_settings.embed_model
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float]:
        try:
            # trust_env=False: Ollama is always a local service for this
            # project (architecture §10 — host/container, never a public
            # endpoint). Without this, httpx inherits the OS/environment
            # proxy configuration, which on this machine intercepts and
            # blocks the localhost call with an unrelated HTTP 403 from
            # a proxy — not a real Ollama failure.
            with httpx.Client(trust_env=False, timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model, "prompt": text},
                )
        except httpx.HTTPError as exc:
            raise EmbeddingBackendUnavailable(
                f"could not reach Ollama at {self._base_url} (model={self._model}): {exc}"
            ) from exc

        if response.status_code != 200:
            raise EmbeddingBackendUnavailable(
                f"Ollama returned HTTP {response.status_code} for model={self._model}: {response.text[:200]}"
            )

        try:
            data = response.json()
            vector = data["embedding"]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingBackendUnavailable(
                f"Ollama's response did not contain a usable 'embedding' field: {exc}"
            ) from exc

        if not isinstance(vector, list) or not vector or not all(isinstance(x, (int, float)) for x in vector):
            raise EmbeddingBackendUnavailable("Ollama returned an empty or non-numeric embedding")
        return [float(x) for x in vector]


def pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def unpack_vector(blob: bytes, dim: int) -> list[float]:
    return list(struct.unpack(f"{dim}f", blob))


def store_embedding(conn: sqlite3.Connection, chunk_id: str, vector: list[float]) -> None:
    conn.execute(
        """
        INSERT INTO chunk_vectors (chunk_id, embedding, dim) VALUES (?, ?, ?)
        ON CONFLICT(chunk_id) DO UPDATE SET embedding = excluded.embedding, dim = excluded.dim
        """,
        (chunk_id, pack_vector(vector), len(vector)),
    )


def embed_missing_chunks(conn: sqlite3.Connection, embedder: Embedder) -> dict:
    """Embeds every chunk that doesn't yet have a chunk_vectors row.
    Re-raises on any REAL embedding failure (unreachable backend, a
    malformed response) — never skips one of those silently (task
    rule: "Do not silently skip embedding failures").

    The one deliberate exception: a chunk whose `text` is empty or
    whitespace-only is skipped, loudly, and listed in the returned
    `skipped_empty` list — never passed to the embedder at all. An
    empty string has no content to embed, and Ollama correctly refuses
    it (observed: a real, verified failure against this project's
    actual data — RUL/CIR documents are someone else's content, not
    this module's to edit; see the RAG completion report for which
    chunk and why).
    """
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.text FROM chunks c
        LEFT JOIN chunk_vectors v ON v.chunk_id = c.chunk_id
        WHERE v.chunk_id IS NULL
        """
    ).fetchall()

    embedded = 0
    skipped_empty: list[str] = []
    for row in rows:
        if not row["text"] or not row["text"].strip():
            skipped_empty.append(row["chunk_id"])
            continue
        vector = embedder.embed(row["text"])  # raises EmbeddingBackendUnavailable on a real failure, not caught here
        store_embedding(conn, row["chunk_id"], vector)
        embedded += 1
    conn.commit()
    return {
        "chunks_embedded": embedded,
        "already_had_embeddings": max(0, len(rows) - embedded - len(skipped_empty)),
        "skipped_empty": skipped_empty,
    }
