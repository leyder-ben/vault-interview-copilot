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


class FailingEmbeddingProvider(FakeEmbeddingProvider):
    """Embedding provider that raises after `fail_after` successful embed_batch calls.

    Used to simulate a mid-file embedding-provider failure, to verify indexer.py
    doesn't mutate Note/Chunk state until chunks and embeddings are fully computed.
    `fail_after=0` fails on the very first call.
    """

    def __init__(self, fail_after: int = 0, dim: int = 768):
        super().__init__(dim=dim)
        self._fail_after = fail_after

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if len(self.calls) >= self._fail_after:
            raise RuntimeError("simulated embedding provider failure")
        return super().embed_batch(texts)
