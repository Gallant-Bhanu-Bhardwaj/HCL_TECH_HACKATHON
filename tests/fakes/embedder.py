"""MockEmbedder — deterministic, hash-based pseudo-vectors for tests
ONLY. Never used by the production retrieve_context() default path
(that always uses the real OllamaEmbedder unless MOCK_LLM=true, in
which case semantic search is skipped entirely — api-contracts §13).
This exists solely so app/rag/embeddings.py's storage/retrieval code
can be exercised without a running Ollama server (task rule: "test
using mocked embedding responses").
"""
from __future__ import annotations

import hashlib
import math


class MockEmbedder:
    """Deterministic: the same text always yields the same vector, and
    texts sharing more words are closer in cosine space than unrelated
    ones (a crude bag-of-words hash embedding) — enough to meaningfully
    exercise ranking logic in tests without any real model."""

    def __init__(self, dim: int = 32) -> None:
        self._dim = dim

    @property
    def model(self) -> str:
        return "mock-embedder"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for word in text.lower().split():
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            index = digest[0] % self._dim
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]
