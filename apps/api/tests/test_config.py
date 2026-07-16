from app.core.config import Settings


def test_defaults_match_env_example():
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.generation_model == "qwen2.5:14b"
    assert settings.query_logging is True
    assert settings.api_port == 8000


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@z:5432/db")
    monkeypatch.setenv("QUERY_LOGGING", "false")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://x:y@z:5432/db"
    assert settings.query_logging is False
