# Testing Strategy

## Unit tests

- Frontmatter parsing
- Heading hierarchy extraction
- Chunk-size boundaries
- Code-block preservation (never split inside a fenced block)
- Wikilink parsing
- Content-hash behavior
- Query normalization
- Rank-fusion behavior
- Source-resolution behavior (chunk ID → path/heading/lines, never the reverse)
- Structured-output validation (the JSON schema in `04-generation.md`)

## Integration tests

- Sample vault → database indexing, end to end
- Changed-file incremental reindexing (run twice, confirm second run touches only what changed)
- Deleted-file cleanup
- Full-text and vector retrieval against real data
- Query API with a deterministic fake model provider (no real LLM call in CI)
- Database migrations (Alembic upgrade/downgrade)
- Docker Compose health checks

## End-to-end tests

- User submits shorthand query → correct source appears
- Answer renders in expected sections
- Citation opens the expected excerpt
- Missing evidence produces a stated limitation, not a fabricated claim

## Model-dependent tests — keep separate from deterministic CI

Anything that calls a real LLM provider runs manually or in an optional workflow with explicit cost/resource controls. Standard CI should never depend on Ollama being up and responsive — use the deterministic fake provider for anything that has to run on every commit.

## Tests run against an isolated database, not your dev data

`pytest` never touches the database your local `uvicorn`/CLI/manual-verification runs use. `tests/conftest.py` derives a separate database (`<settings.database_url>_test`, e.g. `vault_copilot_test`) from `settings.database_url`, auto-creates it if missing, and points both the test fixtures and Alembic (via a `TEST_DATABASE_URL` environment variable `alembic/env.py` checks before falling back to `settings.database_url`) at it. This exists because a real incident during Phase 3 lost a batch of live diagnostic data: a routine `pytest` run truncated `notes`/`chunks`/`query_runs` on the *same* database a manual real-model verification pass had just populated, mid-investigation. If you're about to run a real/manual verification pass whose data you want to keep, it's already safe from `pytest` — but it is **not** safe from you manually re-running `python -m app.ingestion.cli` or otherwise touching `vault_copilot` directly, since that's still the one real database.

## Use the `webapp-testing` skill

Once the FastAPI + React app exists, use `webapp-testing` (Playwright) for UI verification rather than manually clicking through — this is a real token-efficiency win since you're not re-explaining browser automation setup each session.
