# vault-interview-copilot

A local, vault-grounded interview recall tool. Type a shorthand query mid-interview ("terraform drift prod," "helm scaling") and it pulls the relevant note out of an Obsidian vault and hands back a short, speakable, first-person answer with sources — not a generic explanation, and not an invented personal claim.

**Status:** Phase 0 complete — `docker compose up` starts Postgres+pgvector and the API end to end; `/health` responds; schema is migrated. Phase 1 (vault indexing) not yet started.

## Why this exists

Generic interview-prep tools lean on broad model knowledge or a resume. That produces generic answers, invented personal claims, and slow recall under time pressure. This tool instead treats a private Obsidian vault as the authoritative source of personal experience, and optimizes retrieval accuracy and grounded claims above everything else — including polish.

## Architecture

Full design brief, data model, and 25 sections of reasoning live in the private vault this tool indexes (not included in this repo — see Privacy below). Short version:

- **Modular monolith** — one FastAPI backend, clean internal module boundaries (ingestion, retrieval, generation, providers). No microservices; nobody else depends on this tool's uptime.
- **Frontend** — React + Vite + TypeScript, deliberately small: query box, speakable answer, sources.
- **Database** — PostgreSQL + pgvector, for relational metadata, full-text search, and vector search in one place.
- **Local inference** — Ollama, pointed at whichever GPU box is active (workstation primary, homelab VM as an auto-fallback). Swappable behind a provider interface; hosted providers (OpenAI/Anthropic) can be added later without a rebuild.
- **Retrieval before generation, always** — a no-LLM debug endpoint proves retrieval quality before any answer generation gets built. A good-sounding answer built on the wrong source note is worse than no answer.

See `docs/adr/` for the individual architecture decisions and why each one was made.

## Stack

React, Vite, TypeScript · FastAPI, Pydantic, SQLAlchemy, Alembic · PostgreSQL + pgvector · Ollama (Qwen2.5 14B generation, nomic-embed-text embeddings)

## Getting started

```bash
cp .env.example .env
docker compose up -d
curl http://localhost:8000/health
```

## Privacy

The real Obsidian vault this tool indexes is private and never included in this repo. A sanitized sample vault will live in `sample-vault/` for demos, tests, and evaluation once Phase 1 (ingestion) is built.

## License

TBD.
