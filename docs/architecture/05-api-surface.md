# API Surface — V1

## POST /api/query

Request:

```json
{
  "query": "terraform drift prod",
  "mode": "speakable",
  "max_sources": 6
}
```

Response:

```json
{
  "answer": {
    "say_this": "...",
    "supporting_points": ["..."],
    "personal_examples": ["..."]
  },
  "sources": [
    {
      "path": "Projects/Whetstone/Infrastructure.md",
      "heading": "Terraform Drift",
      "start_line": 42,
      "end_line": 58,
      "score": 0.91
    }
  ],
  "confidence": "high",
  "limitations": [],
  "timing_ms": {
    "retrieval": 170,
    "generation": 1150,
    "total": 1380
  }
}
```

## POST /api/index/run

Triggers a manual incremental indexing run.

## GET /api/index/status

Returns indexed file counts, last run status, embedding model version, errors.

## GET /api/health

Checks API, database, vector extension, and configured model provider. This is the first real endpoint to build — Phase 0 exit condition depends on it existing and returning something meaningful.

## GET /api/source

Accepts a source identifier, returns the excerpt and metadata. Must **not** expose arbitrary filesystem access from user-controlled input — resolve strictly through the `chunks`/`notes` tables, never take a raw path from the request and read the filesystem directly.

## POST /api/settings/provider

Not in the original brief's API list but required by the locked provider-hosting decision (see CLAUDE.md) — switches the active inference provider (workstation vs. ai-inference VM) at runtime. Should trigger a health check against the new target before committing the switch.
