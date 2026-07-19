from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.fulltext import ScoredChunk


@dataclass
class FusedResult:
    chunk_id: int
    vault_path: str
    heading_path: str | None
    fused_rank: int
    rrf_score: float
    fulltext_rank: int | None
    vector_rank: int | None


def reciprocal_rank_fusion(
    fulltext_results: list[ScoredChunk], vector_results: list[ScoredChunk], k: int = 60
) -> list[FusedResult]:
    by_chunk: dict[int, dict] = {}

    for chunk in fulltext_results:
        by_chunk[chunk.chunk_id] = {
            "vault_path": chunk.vault_path,
            "heading_path": chunk.heading_path,
            "fulltext_rank": chunk.rank,
            "vector_rank": None,
        }

    for chunk in vector_results:
        entry = by_chunk.setdefault(
            chunk.chunk_id,
            {
                "vault_path": chunk.vault_path,
                "heading_path": chunk.heading_path,
                "fulltext_rank": None,
                "vector_rank": None,
            },
        )
        entry["vector_rank"] = chunk.rank

    scored = []
    for chunk_id, entry in by_chunk.items():
        score = 0.0
        if entry["fulltext_rank"] is not None:
            score += 1 / (k + entry["fulltext_rank"])
        if entry["vector_rank"] is not None:
            score += 1 / (k + entry["vector_rank"])
        scored.append((chunk_id, entry, score))

    scored.sort(key=lambda item: item[2], reverse=True)

    return [
        FusedResult(
            chunk_id=chunk_id,
            vault_path=entry["vault_path"],
            heading_path=entry["heading_path"],
            fused_rank=i + 1,
            rrf_score=score,
            fulltext_rank=entry["fulltext_rank"],
            vector_rank=entry["vector_rank"],
        )
        for i, (chunk_id, entry, score) in enumerate(scored)
    ]
