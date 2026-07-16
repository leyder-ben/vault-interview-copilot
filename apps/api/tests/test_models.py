from app.db.base import Base
from app.db.models import Chunk, IndexRun, Note, NoteLink, QueryRun  # noqa: F401


def test_all_five_tables_registered_on_metadata():
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"notes", "chunks", "note_links", "index_runs", "query_runs"}


def test_chunk_embedding_is_768_dimensional_vector():
    from pgvector.sqlalchemy import Vector

    embedding_col = Chunk.__table__.columns["embedding"]
    assert isinstance(embedding_col.type, Vector)
    assert embedding_col.type.dim == 768


def test_foreign_keys_point_at_notes():
    chunk_fk = next(iter(Chunk.__table__.columns["note_id"].foreign_keys))
    assert chunk_fk.column.table.name == "notes"
    link_fk = next(iter(NoteLink.__table__.columns["source_note_id"].foreign_keys))
    assert link_fk.column.table.name == "notes"
