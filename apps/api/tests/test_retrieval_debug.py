from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.db.models import Chunk, Note
from app.main import app
from tests.ingestion.fakes import FakeEmbeddingProvider


def test_debug_retrieve_returns_full_pipeline_breakdown(db_session, monkeypatch):
    note = Note(
        vault_path="Terraform.md",
        filename="Terraform.md",
        title="Terraform.md",
        content_hash="hash-terraform",
        modified_at=datetime.now(UTC),
    )
    db_session.add(note)
    db_session.flush()
    content = "Document: Terraform\nState drift happens when infrastructure diverges."
    db_session.add(
        Chunk(
            note_id=note.id,
            heading_path="Drift",
            chunk_index=0,
            start_line=1,
            end_line=5,
            content=content,
            content_with_context=content,
            content_hash="chash-terraform",
            embedding=FakeEmbeddingProvider().embed_batch([content])[0],
        )
    )
    db_session.commit()

    import app.api.retrieval_debug as retrieval_debug_module

    monkeypatch.setattr(
        retrieval_debug_module,
        "OllamaEmbeddingProvider",
        lambda base_url, model=None: FakeEmbeddingProvider(),
    )
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.get("/api/debug/retrieve", params={"q": "terraform drift"})
        assert response.status_code == 200
        body = response.json()
        assert body["raw_query"] == "terraform drift"
        assert body["normalized_query"] == "terraform drift"
        assert "fulltext_results" in body
        assert "vector_results" in body
        assert "fused_results" in body
        assert body["fused_results"][0]["vault_path"] == "Terraform.md"
        assert set(body["timing_ms"].keys()) == {"fulltext", "vector", "fusion", "total"}
    finally:
        app.dependency_overrides.clear()


def test_debug_retrieve_requires_q_param(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.get("/api/debug/retrieve")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
