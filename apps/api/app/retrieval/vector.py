from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Chunk, Note
from app.retrieval.fulltext import ScoredChunk


def search_vector_similarity(
    session: Session, query_embedding: list[float], limit: int = 20
) -> list[ScoredChunk]:
    distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")

    rows = (
        session.query(Chunk.id, Note.vault_path, Chunk.heading_path, distance_expr)
        .join(Note, Chunk.note_id == Note.id)
        .filter(Chunk.embedding.is_not(None))
        .order_by(distance_expr.asc())
        .limit(limit)
        .all()
    )

    return [
        ScoredChunk(
            chunk_id=chunk_id,
            vault_path=vault_path,
            heading_path=heading_path,
            rank=i + 1,
            score=1.0 - float(distance),
        )
        for i, (chunk_id, vault_path, heading_path, distance) in enumerate(rows)
    ]
