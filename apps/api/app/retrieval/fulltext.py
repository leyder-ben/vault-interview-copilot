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


def _run_tsquery(session: Session, tsquery, limit: int) -> list[tuple]:
    rank_expr = sa.func.ts_rank(Chunk.search_vector, tsquery).label("score")

    return (
        session.query(Chunk.id, Note.vault_path, Chunk.heading_path, rank_expr)
        .join(Note, Chunk.note_id == Note.id)
        .filter(Chunk.search_vector.op("@@")(tsquery))
        .order_by(rank_expr.desc())
        .limit(limit)
        .all()
    )


def _or_fallback_tsquery(query: str):
    """Build an OR-of-terms tsquery from individual words.

    `websearch_to_tsquery` ANDs every unquoted term, which is too strict for
    terse shorthand queries: a single word with no lexical match anywhere in
    the vault (e.g. a filler/context word not present in the target note)
    zeroes out the entire result set even when the other terms are strong
    exact matches. This fallback only runs when the strict AND query returns
    nothing, so it never changes ranking for queries that already match.
    """
    words = [w for w in query.split() if w]
    if not words:
        return None

    combined = sa.func.plainto_tsquery("english", words[0])
    for word in words[1:]:
        combined = combined.op("||")(sa.func.plainto_tsquery("english", word))
    return combined


def search_fulltext(session: Session, query: str, limit: int = 20) -> list[ScoredChunk]:
    tsquery = sa.func.websearch_to_tsquery("english", query)
    rows = _run_tsquery(session, tsquery, limit)

    if not rows:
        fallback_tsquery = _or_fallback_tsquery(query)
        if fallback_tsquery is not None:
            rows = _run_tsquery(session, fallback_tsquery, limit)

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
