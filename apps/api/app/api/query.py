from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import QueryRun
from app.generation.schema import QueryAnswer, QueryRequest, QueryResponse, QuerySource
from app.generation.service import answer as generate_answer
from app.providers.embeddings import OllamaEmbeddingProvider
from app.providers.llm import OllamaLLMProvider
from app.retrieval.context import select as select_context
from app.retrieval.search import search

router = APIRouter()


@router.post("/api/query")
def query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    embedding_provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_workstation_url, model=settings.embedding_model
    )
    llm_provider = OllamaLLMProvider(
        base_url=settings.ollama_workstation_url, model=settings.generation_model
    )

    retrieval_result = search(db, embedding_provider, request.query)
    context = select_context(retrieval_result.fused_results, db, max_sources=request.max_sources)

    generation_start = time.perf_counter()
    result = generate_answer(db, llm_provider, request.query, request.mode, context)
    generation_ms = (time.perf_counter() - generation_start) * 1000
    retrieval_ms = retrieval_result.timing_ms["total"]

    response = QueryResponse(
        answer=QueryAnswer(
            say_this=result.draft.say_this,
            supporting_points=result.draft.supporting_points,
            personal_examples=result.draft.personal_examples,
        ),
        sources=[
            QuerySource(
                path=s.citation.path,
                heading=s.citation.heading,
                start_line=s.citation.start_line,
                end_line=s.citation.end_line,
                score=s.score,
            )
            for s in result.sources
        ],
        confidence=result.draft.confidence,
        limitations=result.draft.limitations,
        timing_ms={
            "retrieval": retrieval_ms,
            "generation": generation_ms,
            "total": retrieval_ms + generation_ms,
        },
    )

    if settings.query_logging:
        db.add(
            QueryRun(
                created_at=datetime.now(UTC),
                raw_query=request.query,
                normalized_query=retrieval_result.normalized_query,
                response_mode=request.mode.value,
                retrieval_latency_ms=int(retrieval_ms),
                generation_latency_ms=int(generation_ms),
                total_latency_ms=int(retrieval_ms + generation_ms),
                retrieved_chunk_ids=[c.chunk_id for c in context],
                retrieval_scores={str(c.chunk_id): c.rrf_score for c in context},
                selected_source_ids=[s.citation.chunk_id for s in result.sources],
                provider_name="ollama",
                model_name=settings.generation_model,
                confidence=result.draft.confidence.value,
                limitations=result.draft.limitations,
            )
        )
        db.commit()

    return response
