from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import Chunk, IndexRun, Note, NoteLink
from app.ingestion.chunker import chunk_note
from app.ingestion.embeddings import EmbeddingProvider
from app.ingestion.parser import parse_note
from app.ingestion.scanner import scan_vault


@dataclass
class IndexRunResult:
    status: str
    files_scanned: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    chunks_created: int = 0
    chunks_deleted: int = 0
    errors: list[dict] = field(default_factory=list)


def _title_from_path(vault_path: str) -> str:
    return vault_path.rsplit("/", 1)[-1]


def run_index(
    session: Session,
    vault_path: str,
    embedding_provider: EmbeddingProvider,
    *,
    max_section_tokens: int,
    embedding_model: str,
) -> IndexRunResult:
    started_at = datetime.now(UTC)

    try:
        scanned_files = scan_vault(vault_path)
    except OSError as exc:
        index_run = IndexRun(
            started_at=started_at,
            completed_at=datetime.now(UTC),
            status="failed",
            errors_json={"errors": [{"vault_path": None, "error": str(exc)}]},
        )
        session.add(index_run)
        session.commit()
        return IndexRunResult(status="failed", errors=[{"vault_path": None, "error": str(exc)}])

    result = IndexRunResult(status="success", files_scanned=len(scanned_files))
    existing_notes = {note.vault_path: note for note in session.query(Note).all()}

    for scanned in scanned_files:
        try:
            existing = existing_notes.get(scanned.vault_path)
            if existing is not None and existing.content_hash == scanned.content_hash:
                continue

            parsed = parse_note(
                scanned.content, fallback_title=_title_from_path(scanned.vault_path)
            )
            chunk_data = chunk_note(
                parsed,
                title=parsed.title,
                vault_path=scanned.vault_path,
                max_section_tokens=max_section_tokens,
            )
            vectors = embedding_provider.embed_batch([c.content_with_context for c in chunk_data])

            if existing is None:
                note = Note(
                    vault_path=scanned.vault_path,
                    filename=scanned.vault_path.rsplit("/", 1)[-1],
                    title=parsed.title,
                    content_hash=scanned.content_hash,
                    modified_at=scanned.modified_at,
                    frontmatter_json=parsed.frontmatter,
                    tags=parsed.tags,
                    aliases=parsed.aliases,
                    indexed_at=datetime.now(UTC),
                    embedding_version=embedding_model,
                )
                session.add(note)
                result.files_added += 1
            else:
                note = existing
                note.content_hash = scanned.content_hash
                note.modified_at = scanned.modified_at
                note.frontmatter_json = parsed.frontmatter
                note.tags = parsed.tags
                note.aliases = parsed.aliases
                note.indexed_at = datetime.now(UTC)
                note.embedding_version = embedding_model
                result.files_updated += 1

            note.chunks = [
                Chunk(
                    heading_path=c.heading_path,
                    chunk_index=c.chunk_index,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    content=c.content,
                    content_with_context=c.content_with_context,
                    token_count=c.token_count,
                    embedding=vector,
                    content_hash=c.content_hash,
                )
                for c, vector in zip(chunk_data, vectors)
            ]
            note.links = [
                NoteLink(
                    target_path=link.target, link_text=link.link_text, link_type=link.link_type
                )
                for link in parsed.links
            ]
            result.chunks_created += len(chunk_data)
        except Exception as exc:  # noqa: BLE001
            result.errors.append({"vault_path": scanned.vault_path, "error": str(exc)})

    if result.errors:
        result.status = "partial"

    index_run = IndexRun(
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status=result.status,
        files_scanned=result.files_scanned,
        files_added=result.files_added,
        files_updated=result.files_updated,
        files_deleted=result.files_deleted,
        chunks_created=result.chunks_created,
        chunks_deleted=result.chunks_deleted,
        errors_json={"errors": result.errors} if result.errors else None,
    )
    session.add(index_run)
    session.commit()
    return result
