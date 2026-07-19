from datetime import UTC, datetime

from app.db.models import Chunk, Note
from app.retrieval.sources import resolve_sources


def _make_note_and_chunk(db_session, vault_path, heading, start_line, end_line, content):
    note = Note(
        vault_path=vault_path,
        filename=vault_path,
        title=vault_path,
        content_hash=f"hash-{vault_path}",
        modified_at=datetime.now(UTC),
    )
    db_session.add(note)
    db_session.flush()
    chunk = Chunk(
        note_id=note.id,
        heading_path=heading,
        chunk_index=0,
        start_line=start_line,
        end_line=end_line,
        content=content,
        content_with_context=content,
        content_hash=f"chash-{vault_path}-{heading}",
    )
    db_session.add(chunk)
    db_session.flush()
    return chunk.id


def test_resolve_sources_returns_path_heading_and_lines(db_session):
    chunk_id = _make_note_and_chunk(
        db_session, "Terraform.md", "Drift", 10, 20, "State drift happens when infra diverges."
    )
    db_session.commit()

    citations = resolve_sources(db_session, [chunk_id])

    assert len(citations) == 1
    assert citations[0].chunk_id == chunk_id
    assert citations[0].path == "Terraform.md"
    assert citations[0].heading == "Drift"
    assert citations[0].start_line == 10
    assert citations[0].end_line == 20


def test_resolve_sources_preserves_requested_order(db_session):
    first_id = _make_note_and_chunk(db_session, "A.md", "H1", 1, 2, "content a")
    second_id = _make_note_and_chunk(db_session, "B.md", "H2", 1, 2, "content b")
    db_session.commit()

    citations = resolve_sources(db_session, [second_id, first_id])

    assert [c.chunk_id for c in citations] == [second_id, first_id]


def test_resolve_sources_empty_list_returns_empty():
    from app.db.base import SessionLocal

    session = SessionLocal()
    try:
        assert resolve_sources(session, []) == []
    finally:
        session.close()


def test_resolve_sources_skips_unknown_chunk_ids(db_session):
    chunk_id = _make_note_and_chunk(
        db_session, "Kubernetes.md", "Scaling", 1, 5, "HPA scales pods."
    )
    db_session.commit()

    citations = resolve_sources(db_session, [chunk_id, 999999])

    assert len(citations) == 1
    assert citations[0].chunk_id == chunk_id
