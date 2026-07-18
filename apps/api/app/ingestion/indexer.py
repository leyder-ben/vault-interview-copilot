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


def _diff_and_embed_chunks(
    existing_chunks: list[Chunk],
    chunk_data: list,
    embedding_provider: EmbeddingProvider,
) -> list[Chunk]:
    # Keyed by (heading_path, chunk_index), not heading_path alone — an oversized
    # section (see chunker.py's fallback splitting) can produce multiple sibling
    # chunks under the same heading_path, and heading_path-only keys would collapse
    # them to a single dict entry, causing every sibling but one to be compared
    # against the wrong old chunk's content_hash.
    existing_by_key = {(c.heading_path, c.chunk_index): c for c in existing_chunks}
    to_embed_indexes: list[int] = []
    texts_to_embed: list[str] = []
    resolved: dict[int, list[float]] = {}

    for i, c in enumerate(chunk_data):
        old = existing_by_key.get((c.heading_path, c.chunk_index))
        if old is not None and old.content_hash == c.content_hash:
            resolved[i] = old.embedding
        else:
            to_embed_indexes.append(i)
            texts_to_embed.append(c.content_with_context)

    new_vectors = embedding_provider.embed_batch(texts_to_embed)
    for idx, vector in zip(to_embed_indexes, new_vectors):
        resolved[idx] = vector

    return [
        Chunk(
            heading_path=c.heading_path,
            chunk_index=c.chunk_index,
            start_line=c.start_line,
            end_line=c.end_line,
            content=c.content,
            content_with_context=c.content_with_context,
            token_count=c.token_count,
            embedding=resolved[i],
            content_hash=c.content_hash,
        )
        for i, c in enumerate(chunk_data)
    ]


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
        scan_result = scan_vault(vault_path)
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

    scanned_files = scan_result.files
    result = IndexRunResult(status="success", files_scanned=len(scanned_files))
    result.errors.extend(scan_result.errors)
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

            if existing is None:
                # Build chunks + embeddings fully before creating/touching the Note
                # row. If embed_batch raises, we must not have added anything to the
                # session — a new note with zero chunks would otherwise get committed
                # and be silently skipped forever on future runs (its content_hash
                # would already match).
                vectors = embedding_provider.embed_batch(
                    [c.content_with_context for c in chunk_data]
                )
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
                session.add(note)
                result.files_added += 1
            else:
                # Same principle: resolve embeddings for changed/new chunks fully
                # before mutating the existing, already-persistent Note row. If
                # embed_batch raises inside _diff_and_embed_chunks, it raises before
                # returning anything here, so content_hash and chunks below are never
                # touched — the DB row stays exactly as it was before this run.
                new_chunks = _diff_and_embed_chunks(
                    list(existing.chunks), chunk_data, embedding_provider
                )
                note = existing
                note.content_hash = scanned.content_hash
                note.modified_at = scanned.modified_at
                note.frontmatter_json = parsed.frontmatter
                note.tags = parsed.tags
                note.aliases = parsed.aliases
                note.indexed_at = datetime.now(UTC)
                note.embedding_version = embedding_model
                note.chunks = new_chunks
                result.files_updated += 1

            note.links = [
                NoteLink(
                    target_path=link.target, link_text=link.link_text, link_type=link.link_type
                )
                for link in parsed.links
            ]
            result.chunks_created += len(chunk_data)
        except Exception as exc:  # noqa: BLE001
            result.errors.append({"vault_path": scanned.vault_path, "error": str(exc)})

    scanned_paths = {f.vault_path for f in scanned_files} | {
        e["vault_path"] for e in scan_result.errors if e.get("vault_path") is not None
    }
    for vault_path_key, note in existing_notes.items():
        if vault_path_key not in scanned_paths:
            result.chunks_deleted += len(note.chunks)
            session.delete(note)
            result.files_deleted += 1

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
