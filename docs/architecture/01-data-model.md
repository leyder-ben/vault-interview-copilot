# Data Model

PostgreSQL + pgvector. All tables live in one database — see `docs/adr/0003-postgres-pgvector.md` for why.

## notes

```text
id
vault_path
filename
title
content_hash
modified_at
frontmatter_json
tags
aliases
indexed_at
embedding_version
```

Content hash is authoritative for change detection — modification timestamps alone are not reliable enough for index decisions.

## chunks

```text
id
note_id
heading_path
chunk_index
start_line
end_line
content
content_with_context
token_count
embedding
search_vector
content_hash
```

`heading_path` preserves ancestry (e.g. `Infrastructure > Terraform > Drift Management`) — see `docs/adr/0005-heading-aware-chunking.md`. `content_with_context` is the version actually embedded, including document title, path, heading path, and tags prepended — not just raw chunk text.

## note_links

```text
id
source_note_id
target_path
link_text
link_type
```

Wikilinks parsed from notes. Not used for ranking in V1 (open design question — see `docs/architecture/07-evaluation.md` open questions) but tracked from the start since it's cheap to capture during ingestion.

## index_runs

```text
id
started_at
completed_at
status
files_scanned
files_added
files_updated
files_deleted
chunks_created
chunks_deleted
errors_json
```

One row per indexing run. Supports the index-status endpoint and incremental-indexing verification.

## query_runs

```text
id
created_at
raw_query
normalized_query
response_mode
retrieval_latency_ms
rerank_latency_ms
generation_latency_ms
total_latency_ms
retrieved_chunk_ids
retrieval_scores
selected_source_ids
provider_name
model_name
```

Logging is on by default per the locked decisions in `CLAUDE.md` — this table is what the evaluation harness (Recall@5, MRR, latency percentiles) measures against. Needs an easy purge path (`DELETE FROM query_runs`, or a `--no-log` flag for a one-off private run), not an off-by-default toggle.

## Migration notes

Alembic manages all schema changes. First migration should stand up all five tables plus the pgvector extension. Do not hand-write SQL migrations outside Alembic — keep one source of truth for schema history.
