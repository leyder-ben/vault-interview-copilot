from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.ingestion.embeddings import OllamaEmbeddingProvider
from app.retrieval.search import search

router = APIRouter()


@router.get("/api/debug/retrieve")
def debug_retrieve(q: str, db: Session = Depends(get_db)) -> dict:
    provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_workstation_url, model=settings.embedding_model
    )
    result = search(db, provider, q)

    return {
        "raw_query": result.raw_query,
        "normalized_query": result.normalized_query,
        "fulltext_results": [
            {
                "chunk_id": c.chunk_id,
                "vault_path": c.vault_path,
                "heading": c.heading_path,
                "rank": c.rank,
                "score": c.score,
            }
            for c in result.fulltext_results
        ],
        "vector_results": [
            {
                "chunk_id": c.chunk_id,
                "vault_path": c.vault_path,
                "heading": c.heading_path,
                "rank": c.rank,
                "score": c.score,
            }
            for c in result.vector_results
        ],
        "fused_results": [
            {
                "chunk_id": f.chunk_id,
                "vault_path": f.vault_path,
                "heading": f.heading_path,
                "fused_rank": f.fused_rank,
                "rrf_score": f.rrf_score,
                "fulltext_rank": f.fulltext_rank,
                "vector_rank": f.vector_rank,
            }
            for f in result.fused_results
        ],
        "timing_ms": result.timing_ms,
    }
