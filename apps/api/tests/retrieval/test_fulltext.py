from datetime import UTC, datetime

from app.db.models import Chunk, Note
from app.retrieval.fulltext import search_fulltext


def _make_note_with_chunk(session, *, vault_path, heading_path, content_with_context):
    note = Note(
        vault_path=vault_path,
        filename=vault_path.rsplit("/", 1)[-1],
        title=vault_path,
        content_hash=f"hash-{vault_path}",
        modified_at=datetime.now(UTC),
    )
    session.add(note)
    session.flush()
    chunk = Chunk(
        note_id=note.id,
        heading_path=heading_path,
        chunk_index=0,
        start_line=1,
        end_line=5,
        content=content_with_context,
        content_with_context=content_with_context,
        content_hash=f"chash-{vault_path}",
    )
    session.add(chunk)
    session.flush()
    return note, chunk


def test_search_fulltext_ranks_exact_term_match_first(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="Terraform.md",
        heading_path="Drift Management",
        content_with_context=(
            "Document: Terraform\nState drift happens when infrastructure diverges."
        ),
    )
    _make_note_with_chunk(
        db_session,
        vault_path="Kubernetes.md",
        heading_path="Scaling",
        content_with_context=(
            "Document: Kubernetes\nPod scaling is unrelated to infrastructure state."
        ),
    )
    db_session.commit()

    results = search_fulltext(db_session, "terraform drift", limit=20)

    assert len(results) >= 1
    assert results[0].vault_path == "Terraform.md"
    assert results[0].rank == 1


def test_search_fulltext_returns_empty_list_for_no_matches(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="Terraform.md",
        heading_path="Drift Management",
        content_with_context=(
            "Document: Terraform\nState drift happens when infrastructure diverges."
        ),
    )
    db_session.commit()

    results = search_fulltext(db_session, "kubernetes helm charts", limit=20)

    assert results == []


def test_search_fulltext_respects_limit(db_session):
    for i in range(5):
        _make_note_with_chunk(
            db_session,
            vault_path=f"Note-{i}.md",
            heading_path=None,
            content_with_context=f"Document: Note {i}\nTerraform drift note number {i}.",
        )
    db_session.commit()

    results = search_fulltext(db_session, "terraform drift", limit=3)

    assert len(results) == 3
