from __future__ import annotations

import hashlib


class FakeEmbeddingProvider:
    """Deterministic embedding provider for tests — no live Ollama dependency."""

    def __init__(self, dim: int = 768):
        self._dim = dim
        self.calls: list[list[str]] = []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [digest[i % len(digest)] / 255.0 for i in range(self._dim)]
