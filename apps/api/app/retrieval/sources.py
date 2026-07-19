from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Chunk, Note


@dataclass
class SourceCitation:
    chunk_id: int
    path: str
    heading: str | None
    start_line: int
    end_line: int


def resolve_sources(session: Session, chunk_ids: list[int]) -> list[SourceCitation]:
    """Resolve chunk IDs to path/heading/line metadata, strictly through the DB.

    Never takes a raw filesystem path — the only input is chunk IDs already
    known to the backend (from retrieval or a generated answer's citations).
    Preserves the caller's requested order; silently skips any ID that
    doesn't resolve (e.g. a chunk deleted since it was cited).
    """
    if not chunk_ids:
        return []

    rows = (
        session.query(
            Chunk.id, Note.vault_path, Chunk.heading_path, Chunk.start_line, Chunk.end_line
        )
        .join(Note, Chunk.note_id == Note.id)
        .filter(Chunk.id.in_(chunk_ids))
        .all()
    )
    by_id = {
        chunk_id: SourceCitation(
            chunk_id=chunk_id,
            path=vault_path,
            heading=heading_path,
            start_line=start_line,
            end_line=end_line,
        )
        for chunk_id, vault_path, heading_path, start_line, end_line in rows
    }
    return [by_id[cid] for cid in chunk_ids if cid in by_id]
