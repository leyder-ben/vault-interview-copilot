from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import Chunk, Note


@dataclass
class ScoredChunk:
    chunk_id: int
    vault_path: str
    heading_path: str | None
    rank: int
    score: float


def search_fulltext(session: Session, query: str, limit: int = 20) -> list[ScoredChunk]:
    tsquery = sa.func.websearch_to_tsquery("english", query)
    rank_expr = sa.func.ts_rank(Chunk.search_vector, tsquery).label("score")

    rows = (
        session.query(Chunk.id, Note.vault_path, Chunk.heading_path, rank_expr)
        .join(Note, Chunk.note_id == Note.id)
        .filter(Chunk.search_vector.op("@@")(tsquery))
        .order_by(rank_expr.desc())
        .limit(limit)
        .all()
    )

    return [
        ScoredChunk(
            chunk_id=chunk_id,
            vault_path=vault_path,
            heading_path=heading_path,
            rank=i + 1,
            score=float(score),
        )
        for i, (chunk_id, vault_path, heading_path, score) in enumerate(rows)
    ]
