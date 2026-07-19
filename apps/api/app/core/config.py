from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://copilot:copilot@localhost:5432/vault_copilot"
    ollama_workstation_url: str = "http://localhost:11434"
    ollama_ai_inference_url: str = "http://localhost:11434"
    generation_model: str = "gpt-oss:20b"
    embedding_model: str = "nomic-embed-text"
    context_budget_tokens: int = 3000
    personal_project_tags: list[str] = []
    # PLACEHOLDER — a reasoned starting estimate, not a measurement. Task 7 of
    # docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md replaces
    # this with a real value measured against sample-vault using real
    # nomic-embed-text embeddings (FakeEmbeddingProvider's hash-noise vectors
    # can't calibrate a semantic-relevance threshold meaningfully). This is
    # the plan's one explicitly-allowed "no placeholders" exception — see
    # Task 7's note before assuming this comment or value is stale.
    abstention_score_threshold: float = 0.0165
    chunk_max_section_tokens: int = 400
    vault_path: str = "/vault"
    query_logging: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "info"


settings = Settings()
