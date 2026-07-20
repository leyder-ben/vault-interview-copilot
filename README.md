# vault-interview-copilot

A local, vault-grounded interview recall tool. Type a shorthand query mid-interview ("terraform drift prod," "helm scaling") and it pulls the relevant note out of an Obsidian vault and hands back a short, speakable, first-person answer with sources — not a generic explanation, and not an invented personal claim.

**Status:** Phases 0-3 complete and merged. The backend can index a vault, retrieve against it, and hand back a grounded, sourced, speakable answer over `POST /api/query`. Phase 4 (web interface) is next — this repo is the API with no face on it yet.

### Where each phase landed

- **Phase 0 — skeleton.** `docker compose up` brings up Postgres+pgvector and the API end to end; `/health` responds; schema is migrated via Alembic.
- **Phase 1 — vault indexing.** Scans an Obsidian vault, parses frontmatter/headings/wikilinks, chunks heading-aware (never mid-code-block), embeds via `nomic-embed-text`, and re-indexes incrementally — a second pass over an unchanged vault touches zero files, proven against real Postgres, not just asserted.
- **Phase 2 — retrieval.** Full-text (`websearch_to_tsquery`) and pgvector cosine search run sequentially and get merged with reciprocal rank fusion. `GET /api/debug/retrieve` exists specifically so retrieval quality can be checked without an LLM anywhere in the loop. First real eval run against `sample-vault` came back Recall@5 = 0.83 (5/6) — one query was getting zeroed out because `websearch_to_tsquery` ANDs every term, so a single missing filler word tanked an otherwise-strong match. Added an OR-of-terms fallback that only kicks in when the strict query returns nothing. Re-measured: 1.0 (6/6).
- **Phase 3 — grounded answers.** `POST /api/query` runs retrieval → context selection → structured generation (`gpt-oss:20b` via Ollama) → a backend citation cross-check that verifies two things independently: that a cited chunk was actually in the context sent to the model (blocks fabricated IDs outright), and — added after a real gap got measured — that the chunk's content actually supports the specific claim it's attached to (lexical-overlap relevance score, threshold tuned against 92 hand-labeled real query/chunk pairs to precision 0.93 / recall 0.97). Retrieval-quality-gated abstention means a query with no real vault evidence gets a stated "I don't have grounding for this" instead of a confident-sounding guess.

  **Known, disclosed, not yet fixed:** the model reliably narrates grounded content but doesn't reliably populate the structured citation list behind it — measured at roughly half of eligible queries (5 of 9) in a broader sample. The relevance check above stops a *wrong* citation from surviving; it does nothing for a *missing* one. This is exit-condition-compatible (Phase 3's bar was no fabricated citations, not perfect citation recall) and it's tracked, not swept under the rug — see `docs/architecture/10-delivery-plan.md`.

## Why this exists

Generic interview-prep tools lean on broad model knowledge or a resume. That produces generic answers, invented personal claims, and slow recall under time pressure. This tool instead treats a private Obsidian vault as the authoritative source of personal experience, and optimizes retrieval accuracy and grounded claims above everything else — including polish.

## Architecture

Full design brief, data model, and 25 sections of reasoning live in the private vault this tool indexes (not included in this repo — see Privacy below). Short version:

- **Modular monolith** — one FastAPI backend, clean internal module boundaries (ingestion, retrieval, generation, providers). No microservices; nobody else depends on this tool's uptime.
- **Frontend** — React + Vite + TypeScript, deliberately small: query box, speakable answer, sources.
- **Database** — PostgreSQL + pgvector, for relational metadata, full-text search, and vector search in one place.
- **Local inference** — Ollama, pointed at whichever GPU box is active (workstation primary, homelab VM as an auto-fallback). Swappable behind a provider interface; hosted providers (OpenAI/Anthropic) can be added later without a rebuild. Generation runs with Ollama's `think='low'` reasoning effort — the default (unset) setting was costing 10-18s per call in hidden reasoning tokens this app never reads; forcing it low cut that to 2-5s with no measured loss in answer quality.
- **Retrieval before generation, always** — a no-LLM debug endpoint proves retrieval quality before any answer generation gets built. A good-sounding answer built on the wrong source note is worse than no answer.

See `docs/adr/` for the individual architecture decisions and why each one was made.

## Stack

React, Vite, TypeScript, Tailwind CSS, TanStack Query · FastAPI, Pydantic, SQLAlchemy, Alembic · PostgreSQL + pgvector · Ollama (`gpt-oss:20b` generation, `nomic-embed-text` embeddings)

## Getting started

```bash
cp .env.example .env
docker compose up -d
curl http://localhost:8000/health

# index a vault (sample-vault by default, see .env)
python -m app.ingestion.cli

# check retrieval quality with no LLM in the loop
curl http://localhost:8000/api/debug/retrieve?q=terraform+drift

# ask a real question end to end
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "terraform state drift", "mode": "shorthand"}'

# score retrieval against the eval fixtures
python -m app.evaluation.cli
```

## Privacy

The real Obsidian vault this tool indexes is private and never included in this repo. `sample-vault/` is the sanitized stand-in used for demos, tests, and evaluation — it's what every measured number in this README was run against. The real, private evaluation dataset (built from actual mock-interview transcripts) lives outside this repo entirely, in a gitignored `evaluation/datasets/private/` path.

## License

TBD.
