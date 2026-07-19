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
    frontier_api_key: str | None = None
    # Measured 2026-07-19 against sample-vault (7 fixtures, both query forms,
    # 14 data points) using real nomic-embed-text embeddings via
    # app.evaluation.runner.run_eval. The no-evidence fixture
    # (meridian-no-evidence-database-pooling-007) scored top_rrf_score of
    # 0.01639 on both query forms (shorthand and natural — RRF score ties
    # because both queries land in the same top-rank position with no
    # lexical/full-text matches); the 6 real fixtures scored in
    # [0.03227, 0.03279] across all 12 data points. No overlap between the
    # two clusters. Threshold set at 0.02, inside the gap and biased toward
    # the abstain cluster (0.00361 above the highest abstain score vs. 0.01227
    # below the lowest non-abstain score) per the design spec's bias toward
    # over-abstaining. See docs/superpowers/plans/2026-07-19-
    # phase-3-grounded-answers.md Task 7 for the full measurement process.
    abstention_score_threshold: float = 0.02
    # Measured 2026-07-19 against 92 hand-labeled (chunk, claim) pairs across
    # 4 chunks and 4 real queries against sample-vault content (see
    # docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md's
    # "Citation cross-check verifies membership, not relevance" section for
    # the full finding and methodology): precision 0.93, recall 0.97 at this
    # threshold -- catches 64/66 in-context-but-irrelevant citations,
    # wrongly strips 5/26 (19%) genuinely relevant ones. Severity looked
    # chunk-shape-dependent in that sample (one short/generic chunk was
    # cited almost unconditionally regardless of relevance; three others
    # were cited with high precision) -- not exhaustively validated across
    # the full vault, so revisit if a broader sample shifts this.
    citation_relevance_threshold: float = 0.30
    chunk_max_section_tokens: int = 400
    vault_path: str = "/vault"
    query_logging: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "info"


settings = Settings()
