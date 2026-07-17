from app.db.models import IndexRun, Note
from app.ingestion.indexer import run_index
from tests.ingestion.fakes import FakeEmbeddingProvider

NOTE_A = "# Note A\n\n## Section One\n\nContent for section one.\n"


def _write(base, relative_path, content):
    file_path = base / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def test_new_files_are_added_with_chunks_and_embeddings(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()

    result = run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    assert result.files_added == 1
    assert result.status == "success"
    note = db_session.query(Note).filter_by(vault_path="Note-A.md").one()
    assert note.title == "Note A"
    assert len(note.chunks) >= 1
    assert all(c.embedding is not None for c in note.chunks)


def test_second_run_with_no_changes_touches_zero_files(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()

    run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )
    provider.calls.clear()
    second_result = run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    assert second_result.files_added == 0
    assert second_result.files_updated == 0
    assert second_result.files_deleted == 0
    assert provider.calls == []


def test_index_run_row_is_recorded(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()

    run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    run = db_session.query(IndexRun).order_by(IndexRun.id.desc()).first()
    assert run.status == "success"
    assert run.files_added == 1
