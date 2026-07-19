from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ingestion.embeddings import EmbeddingProvider
from app.retrieval.fulltext import ScoredChunk, search_fulltext
from app.retrieval.fusion import FusedResult, reciprocal_rank_fusion
from app.retrieval.normalize import normalize_query
from app.retrieval.vector import search_vector_similarity


@dataclass
class RetrievalResult:
    raw_query: str
    normalized_query: str
    fulltext_results: list[ScoredChunk]
    vector_results: list[ScoredChunk]
    fused_results: list[FusedResult]
    timing_ms: dict[str, float]


def search(
    session: Session, embedding_provider: EmbeddingProvider, raw_query: str
) -> RetrievalResult:
    total_start = time.perf_counter()

    normalized = normalize_query(raw_query)
    query_embedding = embedding_provider.embed_batch([normalized])[0]

    fulltext_start = time.perf_counter()
    fulltext_results = search_fulltext(session, normalized, limit=20)
    fulltext_ms = (time.perf_counter() - fulltext_start) * 1000

    vector_start = time.perf_counter()
    vector_results = search_vector_similarity(session, query_embedding, limit=20)
    vector_ms = (time.perf_counter() - vector_start) * 1000

    fusion_start = time.perf_counter()
    fused_results = reciprocal_rank_fusion(fulltext_results, vector_results, k=60)
    fusion_ms = (time.perf_counter() - fusion_start) * 1000

    total_ms = (time.perf_counter() - total_start) * 1000

    return RetrievalResult(
        raw_query=raw_query,
        normalized_query=normalized,
        fulltext_results=fulltext_results,
        vector_results=vector_results,
        fused_results=fused_results,
        timing_ms={
            "fulltext": fulltext_ms,
            "vector": vector_ms,
            "fusion": fusion_ms,
            "total": total_ms,
        },
    )
