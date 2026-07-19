from datetime import UTC, datetime

from app.db.models import Chunk, Note
from app.retrieval.search import search
from tests.ingestion.fakes import FakeEmbeddingProvider


def _make_note_with_chunk(session, *, vault_path, content_with_context):
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
        chunk_index=0,
        start_line=1,
        end_line=5,
        content=content_with_context,
        content_with_context=content_with_context,
        content_hash=f"chash-{vault_path}",
        embedding=FakeEmbeddingProvider().embed_batch([content_with_context])[0],
    )
    session.add(chunk)
    session.flush()
    return note, chunk


def test_search_returns_normalized_query_and_fused_results(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="Terraform.md",
        content_with_context=(
            "Document: Terraform\nState drift happens when infrastructure diverges."
        ),
    )
    db_session.commit()

    provider = FakeEmbeddingProvider()
    result = search(db_session, provider, "TF Drift")

    assert result.raw_query == "TF Drift"
    assert result.normalized_query == "terraform drift"
    assert len(result.fused_results) >= 1
    assert result.fused_results[0].vault_path == "Terraform.md"


def test_search_embeds_normalized_query_not_raw_query(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="Terraform.md",
        content_with_context=(
            "Document: Terraform\nState drift happens when infrastructure diverges."
        ),
    )
    db_session.commit()

    provider = FakeEmbeddingProvider()
    search(db_session, provider, "TF Drift")

    assert provider.calls == [["terraform drift"]]


def test_search_populates_timing_ms_keys(db_session):
    provider = FakeEmbeddingProvider()
    result = search(db_session, provider, "anything")

    assert set(result.timing_ms.keys()) == {"fulltext", "vector", "fusion", "total"}
    assert all(isinstance(v, float) for v in result.timing_ms.values())
