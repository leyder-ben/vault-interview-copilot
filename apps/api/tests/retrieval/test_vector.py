from datetime import UTC, datetime

from app.db.models import Chunk, Note
from app.retrieval.vector import search_vector_similarity

DIM = 768


def _unit_vector(hot_index: int) -> list[float]:
    vector = [0.0] * DIM
    vector[hot_index] = 1.0
    return vector


def _make_note_with_chunk(session, *, vault_path, heading_path, embedding):
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
        content="content",
        content_with_context="Document: x\ncontent",
        content_hash=f"chash-{vault_path}",
        embedding=embedding,
    )
    session.add(chunk)
    session.flush()
    return note, chunk


def test_search_vector_similarity_ranks_closest_embedding_first(db_session):
    _make_note_with_chunk(
        db_session, vault_path="Close.md", heading_path=None, embedding=_unit_vector(0)
    )
    _make_note_with_chunk(
        db_session, vault_path="Far.md", heading_path=None, embedding=_unit_vector(500)
    )
    db_session.commit()

    query_embedding = _unit_vector(0)
    results = search_vector_similarity(db_session, query_embedding, limit=20)

    assert results[0].vault_path == "Close.md"
    assert results[0].rank == 1
    assert results[-1].vault_path == "Far.md"


def test_search_vector_similarity_respects_limit(db_session):
    for i in range(5):
        _make_note_with_chunk(
            db_session,
            vault_path=f"Note-{i}.md",
            heading_path=None,
            embedding=_unit_vector(i),
        )
    db_session.commit()

    results = search_vector_similarity(db_session, _unit_vector(0), limit=3)

    assert len(results) == 3


def test_search_vector_similarity_excludes_chunks_with_no_embedding(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="HasEmbedding.md",
        heading_path=None,
        embedding=_unit_vector(0),
    )
    note = Note(
        vault_path="NoEmbedding.md",
        filename="NoEmbedding.md",
        title="NoEmbedding.md",
        content_hash="hash-no-embedding",
        modified_at=datetime.now(UTC),
    )
    db_session.add(note)
    db_session.flush()
    db_session.add(
        Chunk(
            note_id=note.id,
            chunk_index=0,
            start_line=1,
            end_line=5,
            content="content",
            content_with_context="Document: x\ncontent",
            content_hash="chash-no-embedding",
            embedding=None,
        )
    )
    db_session.commit()

    results = search_vector_similarity(db_session, _unit_vector(0), limit=20)

    assert {r.vault_path for r in results} == {"HasEmbedding.md"}
