# Delivery Plan — Phases and Exit Conditions

Work phase by phase. Don't start a later phase's work before the current phase's exit condition is actually met — this is the single biggest lever against wasted tokens on this project, since jumping ahead means redoing work once an earlier assumption turns out wrong.

## Phase 0: Decisions and Skeleton — CURRENT PHASE

- Select working project name — **done**, `vault-interview-copilot`.
- Create repository, basic docs — **done**, pushed to `github.com/leyder-ben/vault-interview-copilot` (private).
- ADR-001 through 005 — **done**, see `docs/adr/`.
- Add Docker Compose with API and PostgreSQL.
- Enable pgvector.
- Add `/health` endpoint.

**Exit condition:** the local stack starts reliably (`docker compose up` works end to end) and CI runs formatting and tests. **Not yet met** — no Dockerfile, no FastAPI app, no migration exist yet as of this writing.

## Phase 1: Vault Indexing

- Read-only vault mount.
- File scanner and ignore patterns (`02-ingestion.md`).
- Markdown/frontmatter parser.
- Heading-aware chunker.
- Database schema and migrations (`01-data-model.md`).
- Local embedding provider (`nomic-embed-text`).
- Incremental upsert/deletion logic.
- Index-status endpoint.

**Exit condition:** a sample vault can be indexed repeatedly without rebuilding unchanged files.

## Phase 2: Retrieval

- Postgres full-text search.
- pgvector semantic search.
- Hybrid rank fusion (`03-retrieval.md`).
- Retrieval-debug endpoint or dev panel.
- Initial evaluation dataset and metrics (`07-evaluation.md`).

**Exit condition:** shorthand queries consistently retrieve the expected sample notes.

## Phase 3: Grounded Answers

- Ollama generation adapter.
- Prompt and context builder.
- Structured answer schema (`04-generation.md`).
- Backend-controlled source resolution.
- Grounding and abstention behavior.
- Query telemetry (`query_runs`).

**Exit condition:** the API returns concise, sourced answers without fabricated file citations.

## Phase 4: Web Interface

- Query input and keyboard workflow (`06-ui-requirements.md`).
- Speakable answer display.
- Supporting points and examples.
- Source excerpts.
- Confidence and limitation state.
- Copy action, local history.

**Exit condition:** the typed V1 is useful in realistic interview-prep sessions.

## Phase 5: Evaluation and Hardening

- Expand private and sanitized test sets.
- Benchmark retrieval variants.
- Add reranking only if justified by measurement.
- Threat model and privacy review (`08-security-privacy.md`).
- Documentation and demo recording.
- GitHub Actions and release workflow.

**Exit condition:** the repository tells a complete, measured engineering story.

## Phase 6: V2 Voice Input (separate effort, not scoped now)

- Streaming transcript endpoint.
- Local or hosted STT adapter.
- Transcript buffer, question-boundary detection.
- Manual and automatic trigger modes.
- Reuse V1 query pipeline as-is.

**Exit condition:** recorded interview audio can be replayed through the system and produce timely, grounded answers.
