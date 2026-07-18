# Phase 2: Retrieval — Design

**Status:** approved, ready for implementation planning
**Date:** 2026-07-18
**Exit condition (from `docs/architecture/10-delivery-plan.md`):** shorthand queries consistently retrieve the expected sample notes — measured against the evaluation fixtures in `docs/architecture/07-evaluation.md`, not by eyeballing a few examples.

## Overview

Phase 1 built the ingestion pipeline: notes and chunks exist in Postgres, each chunk has a `content_with_context` field (already embedded via `nomic-embed-text`) and an unused `search_vector` column. Phase 2 builds the actual retrieval pipeline described in `docs/architecture/03-retrieval.md`: query normalization, full-text search, vector search, reciprocal rank fusion (RRF), a no-LLM debug endpoint to inspect the pipeline directly, and an evaluation harness that scores retrieval against the real (private) and sanitized (`sample-vault`) fixture sets built in `evaluation/datasets/`.

This is deliberately retrieval-only. No generation, no `/api/query`, no context-diversity selection for prompts, no reranking — see "Out of scope" below.

## Architecture

```
app/retrieval/
  normalize.py   — normalize_query(raw: str) -> str
  fulltext.py    — search_fulltext(session, query: str, limit: int = 20) -> list[ScoredChunk]
  vector.py      — search_vector(session, query_embedding: list[float], limit: int = 20) -> list[ScoredChunk]
  fusion.py      — reciprocal_rank_fusion(fulltext: list[ScoredChunk], vector: list[ScoredChunk], k: int = 60) -> list[FusedResult]
  search.py      — search(session, embedding_provider, raw_query: str) -> RetrievalResult
                   (orchestrates: normalize -> embed -> fulltext search -> vector search -> fuse)

app/api/retrieval_debug.py
  GET /api/debug/retrieve?q=...   — thin wrapper around search(), full per-stage response

app/evaluation/
  metrics.py     — recall_at_k(), mrr(), exact_match()
  runner.py      — load_fixtures(path) -> run each (both query forms) through search() -> score
  cli.py         — python -m app.evaluation.cli --dataset {sample-vault|private}

apps/api/tests/retrieval/     — unit tests per module (normalize, fulltext, vector, fusion, search)
apps/api/tests/evaluation/    — test_retrieval_eval.py: Recall@5 threshold assertion against sample-vault (exit-condition proof)
apps/api/tests/test_retrieval_debug.py — endpoint test
```

`app/retrieval/`, `app/evaluation/` already exist as empty scaffolded directories from Phase 0 — this phase fills them in.

## Query flow

```
raw_query
    |
    v
normalize_query()          -- lowercase, alias expansion (hardcoded dict), punctuation cleanup;
    |                          preserves raw_query separately for display
    v
embed(normalized_query)    -- one call to OllamaEmbeddingProvider (Phase 1), reused as-is
    |
    +--> search_fulltext(): to_tsquery against chunks.search_vector, top 20, ts_rank score
    |
    +--> search_vector(): pgvector cosine distance (<=>) against chunks.embedding, top 20
                           (sequential — see "Sequential execution" below)
    |
    v
merge + de-duplicate by chunk_id
    |
    v
reciprocal_rank_fusion(k=60): score = sum(1 / (k + rank)) across the lists a chunk appears in
    |
    v
RetrievalResult: normalized_query, fulltext_results, vector_results, fused_results, timing_ms
```

No reranking, no context-diversity narrowing to 4-6 chunks — both explicitly deferred (see "Out of scope").

## Sequential execution (not concurrent)

Full-text search and vector search run **sequentially** — call one, then the other, plainly, no async/threading. Both are local Postgres queries with no external network hop; latency is expected to be low enough that concurrency isn't worth the complexity yet. This is a deliberate decision per CLAUDE.md's "measure before adding complexity" principle, not an oversight — revisit only if the evaluation harness's p95 retrieval-latency numbers show sequential execution is actually a bottleneck. State this plainly in code comments; don't imply future concurrent work that isn't planned.

## Data model change: populating `search_vector`

`chunks.search_vector` (`TSVECTOR`, with an existing GIN index `ix_chunks_search_vector`) has existed since the Phase 0 migration but has never been populated — Phase 1's indexer never touched it. Phase 2 converts it to a Postgres-computed generated column, so Postgres keeps it in sync automatically and Phase 1's already-shipped, already-reviewed `indexer.py` needs zero changes.

**Verified mechanics** (tested against real Postgres 16.14, in `copilot-postgres`, with real data — 24 chunks from an actual `sample-vault` indexing run via `python -m app.ingestion.cli`, not synthetic rows):

- `ALTER COLUMN ... ADD GENERATED ALWAYS AS (...) STORED` **does not exist** as Postgres syntax — confirmed via a real syntax error. That form is exclusive to `GENERATED ... AS IDENTITY` (auto-increment columns). Postgres has no in-place conversion of a plain column into a stored generated column.
- The only working approach is drop-and-recreate as a new column:
  ```sql
  BEGIN;
  DROP INDEX ix_chunks_search_vector;
  ALTER TABLE chunks DROP COLUMN search_vector;
  ALTER TABLE chunks ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content_with_context)) STORED;
  CREATE INDEX ix_chunks_search_vector ON chunks USING gin (search_vector);
  COMMIT;
  ```
- Dropping the column **does** drop its GIN index — confirmed. The index must be explicitly recreated in the same migration; it does not survive.
- Existing rows **are** backfilled automatically the moment the column is re-added as generated — confirmed against real data (all 24 pre-existing chunks got correct, non-null `tsvector` values immediately, computed from their actual `content_with_context`). No separate backfill script or data migration needed.
- **Atomicity confirmed by forcing a real failure**: ran the same sequence with a deliberately broken generated expression (referenced a nonexistent column). Postgres errored on the `ADD COLUMN` step and aborted the transaction; the already-executed `DROP INDEX` and `DROP COLUMN` did not stick. Final state was byte-for-byte the original schema — plain column, original index, data untouched. Alembic's `env.py` already wraps every migration's `upgrade()` in `context.begin_transaction()` (`run_migrations_online()`), and Postgres supports transactional DDL, so a real Alembic migration using this same sequence gets this atomicity for free: if any step fails, the table is left exactly as it was before the migration ran — never in a half-dropped, no-`search_vector`-at-all state.

**Alembic migration** (`0002_...`), using SQLAlchemy's `Computed()` construct:

```python
def upgrade() -> None:
    op.drop_index("ix_chunks_search_vector", table_name="chunks")
    op.drop_column("chunks", "search_vector")
    op.add_column(
        "chunks",
        sa.Column(
            "search_vector",
            TSVECTOR(),
            sa.Computed("to_tsvector('english', content_with_context)", persisted=True),
        ),
    )
    op.create_index("ix_chunks_search_vector", "chunks", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_search_vector", table_name="chunks")
    op.drop_column("chunks", "search_vector")
    op.add_column("chunks", sa.Column("search_vector", TSVECTOR(), nullable=True))
    op.create_index("ix_chunks_search_vector", "chunks", ["search_vector"], postgresql_using="gin")
```

`app/db/models.py`'s `Chunk.search_vector` field annotation gets a matching `Computed(...)` argument so the ORM model reflects reality (SQLAlchemy won't try to write to a generated column).

## Query normalization

Hardcoded dict in `app/retrieval/normalize.py`, seeded from `03-retrieval.md`'s example glossary plus obvious DevOps shorthand:

```python
ALIASES = {
    "tf": "terraform",
    "k8s": "kubernetes",
    "sm": "secrets manager",
    "cw": "cloudwatch",
    "bluegreen": "blue green deployment",
    "gha": "github actions",
    # extend as evaluation results show gaps
}
```

`normalize_query()` lowercases for search while preserving the raw query for display, expands known aliases, normalizes punctuation/whitespace, and does **not** over-normalize exact technical tokens (hostnames, exact service names) away — per `03-retrieval.md`. No LLM-based query rewriting — only add it if the evaluation harness demonstrates deterministic normalization isn't enough.

## Full-text search (`app/retrieval/fulltext.py`)

`websearch_to_tsquery('english', normalized_query)` against `chunks.search_vector`, ranked by `ts_rank`, top 20. Chosen over `to_tsquery`/`plainto_tsquery` specifically because the harness now scores full interviewer-phrasing sentences, not just shorthand fragments (see "Both query forms" below) — `websearch_to_tsquery` tolerates natural multi-word phrasing (handles stray punctuation, quoted phrases, implicit AND between terms) without requiring the caller to construct tsquery syntax by hand, where `to_tsquery` would reject anything that isn't already valid tsquery operator syntax.

## Vector search (`app/retrieval/vector.py`)

pgvector cosine distance (`<=>`) against `chunks.embedding`, top 20. Plain sequential scan — **no HNSW/ivfflat index**, per the locked "no ANN index until evaluation shows a real bottleneck" decision in CLAUDE.md. `sample-vault` is tiny (24 chunks); this is a non-issue at this scale.

## Reciprocal rank fusion (`app/retrieval/fusion.py`)

Standard RRF: `score = Σ 1/(k + rank)` across whichever of the two ranked lists a chunk appears in, `k = 60` (the conventional default). Merge by `chunk_id`, sort descending by fused score. Output includes each chunk's rank/score in each source list it appeared in (needed for the debug endpoint's per-stage transparency) plus its fused rank/score.

## Debug endpoint (`GET /api/debug/retrieve`)

Thin wrapper around `search()` — no new logic, just HTTP plumbing and response serialization:

```json
{
  "raw_query": "terraform drift prod",
  "normalized_query": "terraform drift prod",
  "fulltext_results": [
    {"chunk_id": 12, "path": "...", "heading": "...", "rank": 1, "score": 0.61}
  ],
  "vector_results": [
    {"chunk_id": 12, "path": "...", "heading": "...", "rank": 3, "score": 0.84}
  ],
  "fused_results": [
    {"chunk_id": 12, "path": "...", "heading": "...",
     "fused_rank": 1, "rrf_score": 0.031,
     "fulltext_rank": 1, "vector_rank": 3}
  ],
  "timing_ms": {"fulltext": 8, "vector": 22, "fusion": 1, "total": 31}
}
```

Not authenticated (single-user, local-only tool, matching the project's existing posture). Does **not** write to `query_runs` — that table's write path is a Phase 3 concern (real queries through `/api/query`), not debug-endpoint traffic.

## Evaluation harness

### Metrics computed this phase (retrieval-only, no LLM)

- **Recall@5, Recall@10** — is any `expected_notes` path among the top-K fused results' parent notes.
- **MRR** — reciprocal rank of the first `expected_notes` match in the fused list.
- **Exact source-note match** — top-1 fused result is an `expected_notes` path.
- **Retrieval latency p50, p95** — from `timing_ms.total` across the eval run.

### Explicitly deferred to Phase 3

`07-evaluation.md`'s full metrics list includes **"correct project-example match"** and concept/duplicate-context judgments. These aren't retrieval metrics — they require either an LLM-generated answer to check against, or project-per-note metadata that doesn't exist on any `Note` yet. Computing them now would mean inventing a proxy metric not grounded in what Phase 2 actually produces. Deferred to whenever Phase 3's generation harness exists, documented here as a deliberate scope cut, not a silent gap.

### Both query forms, scored separately

The private fixture set (`evaluation/datasets/private/mock-interview-fixtures.yaml`) carries both a shorthand `query` and a real `interviewer_phrasing` field per fixture — this distinction is the entire point of `03-retrieval.md`'s normalization work ("queries are terse shorthand typed under time pressure"). `runner.py` runs **both** forms through `search()` as separate scored cases per fixture (when both are present) and computes Recall@5/Recall@10/MRR **separately** for the shorthand group vs. the natural-phrasing group — not blended into one number. A single blended score would prove retrieval works without ever proving normalization specifically helps.

**Consequence for `sample-vault`:** `evaluation/datasets/sample-vault/meridian-fixtures.yaml` (committed 2026-07-18, PR #4) currently has **only** the shorthand `query` field — no `interviewer_phrasing`. Since automated/CI runs are sample-vault-only (the private set requires the real vault, run manually), the exit-condition proof as it stands would never actually exercise natural-phrasing normalization. **This is a task in the Phase 2 plan, not optional polish**: retrofit an `interviewer_phrasing` field onto each of the 6 `meridian-fixtures.yaml` entries, in the same style as the private set (a plausible spoken interviewer question for the same underlying query), before the harness/exit-condition task is considered done.

The pytest exit-condition assertion (`test_retrieval_eval.py`) checks the **shorthand** Recall@5 specifically, matching `03-retrieval.md`'s own framing ("V1 only needs to handle your shorthand"). The natural-phrasing numbers are computed and reported by the CLI but don't gate the exit condition — they're the harness's V2-prep value (per the private fixture note's own stated rationale), not this phase's pass/fail bar.

### CLI (`python -m app.evaluation.cli --dataset {sample-vault|private}`)

Mirrors the Phase 1 CLI pattern. Prints both query-form breakdowns:

```
$ python -m app.evaluation.cli --dataset sample-vault
Shorthand:       Recall@5: 100% (6/6)   Recall@10: 100%   MRR: 0.92
Natural phrasing: Recall@5: 83% (5/6)   Recall@10: 100%   MRR: 0.81
Retrieval latency: p50 12ms, p95 34ms
```

## Testing

- Unit tests per `app/retrieval/` module against a seeded `db_session` (real Postgres, matching Phase 1's established pattern).
- Migration test: apply `0002_...` against a DB with pre-existing chunk rows (not just an empty schema), assert `search_vector` is populated and matches `to_tsvector('english', content_with_context)` — this is the regression guard for the mechanics verified above.
- Debug endpoint test.
- `test_retrieval_eval.py`: the actual Phase 2 exit-condition proof, asserting shorthand Recall@5 against `sample-vault` meets a threshold. The threshold is not picked in advance — that would be an unmeasured, invented number, which CLAUDE.md's evaluation principle explicitly rules out ("never publish a number that wasn't actually measured"). Instead, the implementation task runs the harness first, uncapped, against the finished pipeline (with the retrofitted `interviewer_phrasing` fixtures in place); whatever shorthand Recall@5 that real run produces becomes the committed threshold — set at that measured value (not padded), so the test is a regression floor from a real baseline, not a target picked by guesswork. If the first real run is below 100%, the plan task investigates the specific miss (retrieval bug vs. genuinely hard fixture) before locking in the threshold, rather than silently accepting a low bar.

## Out of scope (Phase 3+)

- Context selection / diversity filtering (the "final context: 4-6 chunks" step in `03-retrieval.md`'s diagram) — that's prompt-building, not retrieval ranking.
- Reranking — explicitly deferred per `03-retrieval.md` and CLAUDE.md principle 6.
- `POST /api/query`, `POST /api/settings/provider`.
- Writing to `query_runs` (real query logging).
- "Correct project-example match" and concept-coverage metrics (see above).
- LLM-based query rewriting.
