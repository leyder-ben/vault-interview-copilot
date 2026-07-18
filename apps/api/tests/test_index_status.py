from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.ingestion.indexer import run_index
from app.main import app
from tests.ingestion.fakes import FakeEmbeddingProvider


def test_status_with_no_runs_yet(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.get("/api/index/status")
        assert response.status_code == 200
        body = response.json()
        assert body["note_count"] == 0
        assert body["last_run"] is None
        assert body["embedding_model"] == "nomic-embed-text"
    finally:
        app.dependency_overrides.clear()


def test_status_reflects_latest_index_run(tmp_path, db_session):
    (tmp_path / "Note-A.md").write_text("# Note A\n\nBody.\n", encoding="utf-8")
    run_index(
        db_session,
        str(tmp_path),
        FakeEmbeddingProvider(),
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.get("/api/index/status")
        body = response.json()
        assert body["note_count"] == 1
        assert body["last_run"]["status"] == "success"
        assert body["last_run"]["files_added"] == 1
    finally:
        app.dependency_overrides.clear()
