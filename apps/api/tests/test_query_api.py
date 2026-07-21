from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.db.models import Chunk, Note, QueryRun
from app.generation.schema import ResponseMode
from app.main import app
from tests.ingestion.fakes import FakeEmbeddingProvider
from tests.providers.fakes import FakeLLMProvider


def _index_terraform_note(db_session):
    note = Note(
        vault_path="Terraform.md",
        filename="Terraform.md",
        title="Terraform.md",
        content_hash="hash-terraform",
        modified_at=datetime.now(UTC),
    )
    db_session.add(note)
    db_session.flush()
    content = "Document: Terraform\nState drift happens when infrastructure diverges from state."
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


def _patch_providers(monkeypatch, fake_llm=None):
    import app.api.query as query_module

    monkeypatch.setattr(
        query_module,
        "OllamaEmbeddingProvider",
        lambda base_url, model=None: FakeEmbeddingProvider(),
    )
    monkeypatch.setattr(
        query_module,
        "OllamaLLMProvider",
        lambda base_url, model=None: (fake_llm or FakeLLMProvider()),
    )
    return query_module


def test_query_happy_path_returns_answer_with_sources(db_session, monkeypatch):
    _index_terraform_note(db_session)
    query_module = _patch_providers(monkeypatch)
    monkeypatch.setattr(query_module.settings, "abstention_score_threshold", -999.0)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.post("/api/query", json={"query": "terraform state drift"})
        assert response.status_code == 200
        body = response.json()
        assert "say_this" in body["answer"]
        assert body["confidence"] in ("high", "medium", "low")
        assert "timing_ms" in body
        assert set(body["timing_ms"].keys()) == {"retrieval", "generation", "total"}
    finally:
        app.dependency_overrides.clear()


def test_query_abstains_when_forced_threshold_is_unreachable(db_session, monkeypatch):
    _index_terraform_note(db_session)
    fake_llm = FakeLLMProvider()
    query_module = _patch_providers(monkeypatch, fake_llm=fake_llm)
    monkeypatch.setattr(query_module.settings, "abstention_score_threshold", 999.0)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.post("/api/query", json={"query": "terraform state drift"})
        assert response.status_code == 200
        body = response.json()
        assert body["confidence"] == "low"
        assert fake_llm.calls == []
    finally:
        app.dependency_overrides.clear()


def test_query_non_speakable_mode_returns_stub_without_retrieval_gating(db_session, monkeypatch):
    _index_terraform_note(db_session)
    fake_llm = FakeLLMProvider()
    _patch_providers(monkeypatch, fake_llm=fake_llm)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.post(
            "/api/query", json={"query": "terraform state drift", "mode": "explain"}
        )
        assert response.status_code == 200
        body = response.json()
        assert "not implemented" in " ".join(body["limitations"])
        assert fake_llm.calls == []
    finally:
        app.dependency_overrides.clear()


def test_query_writes_a_query_run_row_when_logging_enabled(db_session, monkeypatch):
    _index_terraform_note(db_session)
    query_module = _patch_providers(monkeypatch)
    monkeypatch.setattr(query_module.settings, "abstention_score_threshold", -999.0)
    monkeypatch.setattr(query_module.settings, "query_logging", True)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.post("/api/query", json={"query": "terraform state drift"})
        body = response.json()
        rows = db_session.query(QueryRun).all()
        assert len(rows) == 1
        assert rows[0].raw_query == "terraform state drift"
        assert rows[0].response_mode == ResponseMode.SPEAKABLE.value
        assert rows[0].provider_name == "ollama"
        assert rows[0].confidence == body["confidence"]
        assert rows[0].limitations == body["limitations"]
    finally:
        app.dependency_overrides.clear()


def test_query_skips_query_run_row_when_logging_disabled(db_session, monkeypatch):
    _index_terraform_note(db_session)
    query_module = _patch_providers(monkeypatch)
    monkeypatch.setattr(query_module.settings, "abstention_score_threshold", -999.0)
    monkeypatch.setattr(query_module.settings, "query_logging", False)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        client.post("/api/query", json={"query": "terraform state drift"})
        rows = db_session.query(QueryRun).all()
        assert len(rows) == 0
    finally:
        app.dependency_overrides.clear()


def test_query_requires_query_field(db_session):
    # A real db_session override is used here, not a stub, matching the
    # precedent in tests/test_retrieval_debug.py's analogous
    # test_debug_retrieve_requires_q_param: FastAPI resolves the get_db
    # dependency as part of the request cycle regardless of body validity.
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.post("/api/query", json={})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
