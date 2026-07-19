from app.core.config import Settings, settings


def test_defaults_match_env_example():
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.generation_model == "gpt-oss:20b"
    assert settings.query_logging is True
    assert settings.api_port == 8000


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@z:5432/db")
    monkeypatch.setenv("QUERY_LOGGING", "false")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://x:y@z:5432/db"
    assert settings.query_logging is False


def test_chunk_max_section_tokens_default():
    settings = Settings(_env_file=None)
    assert settings.chunk_max_section_tokens == 400


def test_chunk_max_section_tokens_env_override(monkeypatch):
    monkeypatch.setenv("CHUNK_MAX_SECTION_TOKENS", "250")
    settings = Settings(_env_file=None)
    assert settings.chunk_max_section_tokens == 250


def test_generation_model_defaults_to_gpt_oss_20b():
    assert settings.generation_model == "gpt-oss:20b"


def test_context_budget_tokens_has_a_positive_default():
    assert settings.context_budget_tokens > 0


def test_personal_project_tags_defaults_to_empty_list():
    assert settings.personal_project_tags == []


def test_abstention_score_threshold_is_a_float():
    assert isinstance(settings.abstention_score_threshold, float)
