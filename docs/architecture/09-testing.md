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

## Use the `webapp-testing` skill

Once the FastAPI + React app exists, use `webapp-testing` (Playwright) for UI verification rather than manually clicking through — this is a real token-efficiency win since you're not re-explaining browser automation setup each session.
