from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://copilot:copilot@localhost:5432/vault_copilot"
    ollama_workstation_url: str = "http://localhost:11434"
    ollama_ai_inference_url: str = "http://localhost:11434"
    generation_model: str = "qwen2.5:14b"
    embedding_model: str = "nomic-embed-text"
    chunk_max_section_tokens: int = 400
    vault_path: str = "/vault"
    query_logging: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "info"


settings = Settings()
