from __future__ import annotations

from dataclasses import dataclass

import tiktoken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Chunk, Note
from app.retrieval.fusion import FusedResult

_ENCODING = tiktoken.get_encoding("cl100k_base")

DEFAULT_MAX_CHUNKS_PER_NOTE = 1
DEFAULT_MAX_CHUNKS_PER_PROJECT_NOTE = 2


@dataclass
class RetrievedChunk:
    chunk_id: int
    vault_path: str
    heading_path: str | None
    content: str
    rrf_score: float


def _hydrate(session: Session, chunk_ids: list[int]) -> dict[int, tuple[str, list[str]]]:
    if not chunk_ids:
        return {}
    rows = (
        session.query(Chunk.id, Chunk.content, Note.tags)
        .join(Note, Chunk.note_id == Note.id)
        .filter(Chunk.id.in_(chunk_ids))
        .all()
    )
    return {chunk_id: (content, tags or []) for chunk_id, content, tags in rows}


def select(
    fused_results: list[FusedResult],
    session: Session,
    max_sources: int,
    budget_tokens: int | None = None,
    max_chunks_per_note: int = DEFAULT_MAX_CHUNKS_PER_NOTE,
    max_chunks_per_project_note: int = DEFAULT_MAX_CHUNKS_PER_PROJECT_NOTE,
) -> list[RetrievedChunk]:
    """Diverse, budget-aware, personal-project-favoring context selection.

    "Prioritize personal project evidence" (docs/architecture/03-retrieval.md)
    is implemented as a higher per-note chunk cap for notes tagged with any of
    settings.personal_project_tags, not a query-intent classifier — that would
    be unmeasured complexity this codebase's conventions deliberately avoid.
    """
    if budget_tokens is None:
        budget_tokens = settings.context_budget_tokens
    if not fused_results:
        return []

    chunk_ids = [r.chunk_id for r in fused_results]
    hydrated = _hydrate(session, chunk_ids)
    project_tags = set(settings.personal_project_tags)

    selected: list[RetrievedChunk] = []
    per_note_count: dict[str, int] = {}
    total_tokens = 0

    for result in fused_results:
        if len(selected) >= max_sources:
            break
        hydrated_entry = hydrated.get(result.chunk_id)
        if hydrated_entry is None:
            continue
        content, tags = hydrated_entry

        is_project_note = bool(project_tags & set(tags))
        cap = max_chunks_per_project_note if is_project_note else max_chunks_per_note
        if per_note_count.get(result.vault_path, 0) >= cap:
            continue

        content_tokens = len(_ENCODING.encode(content))
        # Skip (not stop) when a candidate would blow the budget, so a later,
        # smaller candidate can still fit. Always keep the very first chunk
        # regardless of size, so one oversized top result can't empty the
        # whole selection.
        if selected and total_tokens + content_tokens > budget_tokens:
            continue

        selected.append(
            RetrievedChunk(
                chunk_id=result.chunk_id,
                vault_path=result.vault_path,
                heading_path=result.heading_path,
                content=content,
                rrf_score=result.rrf_score,
            )
        )
        per_note_count[result.vault_path] = per_note_count.get(result.vault_path, 0) + 1
        total_tokens += content_tokens

    return selected
