# CLAUDE.md — vault-interview-copilot

Read this fully before writing any code. It tells you what this project is, what's already decided, and where to find the details you need for the specific piece you're working on — you don't need to load everything at once.

## What this is

A local, single-user web app that indexes Ben's private Obsidian vault and answers short, shorthand interview-prep queries ("terraform drift prod") with a concise, speakable, first-person, source-cited answer. Replaces a broken paid tool called Verve Copilot. V1 is typed-query only; V2 (later, separate effort) adds voice input over the same pipeline.

**The core bet:** retrieval accuracy matters more than generation polish. A good-sounding answer built on the wrong source note is worse than no answer. Prove retrieval works (via a no-LLM debug endpoint) before building answer generation on top of it.

## Locked decisions — do not re-derive or second-guess these

Full reasoning: `docs/architecture/11-locked-decisions.md`. Short version:

- **No containerized Ollama.** App points at the workstation's existing Ollama (`localhost:11434`) by default. The ai-inference VM is a registered fallback, not primary. Active provider is a Postgres `settings` row, switchable at runtime, not a config file.
- **Models:** GPT-OSS 20B (`gpt-oss:20b`, MXFP4 quant) for generation, `nomic-embed-text` for embeddings. Corrected from an earlier Qwen2.5 14B decision during Phase 3 — Qwen2.5-Coder 14B was evaluated and rejected, its output register is tuned for code completion, not natural spoken-answer prose. Whether it fits the ai-inference VM's 3060 (12GB VRAM) the way the smaller Qwen model did is an open question, not settled — doesn't block anything since provider switching to that box is still deferred.
- **Ignore patterns for the vault scanner:** exclude `.git/**`, `.obsidian/**`, `.trash/**`, `_Templates/**`, `_Agents/**`, `_Skills/**`, `_Workflows/**`, `_About-Ben/**` by explicit name. Do **not** use a blanket `_*/**` pattern — it would wrongly swallow `_Source-Docs/` folders, which hold real indexable content. `00-Inbox/` is NOT ignored.
- **Postgres image:** `pgvector/pgvector:pg16`, not stock `postgres` + manual extension build.
- **Repo name:** `vault-interview-copilot` — already set, don't rename.
- **Query logging:** on by default (`query_runs` table), with an easy purge path. Not a privacy problem at this stage — single-user, local-only tool.

## Architecture principles (non-negotiable unless you have a measured reason)

1. **Modular monolith, not microservices.** One FastAPI app, clean internal module boundaries (`ingestion/`, `retrieval/`, `generation/`, `providers/`, `db/`). No service-to-service network calls. See `docs/adr/0001-modular-monolith.md`.
2. **Web app, not Electron.** Plain browser tab for V1. No desktop overlay, no always-on-top, no screen-capture concealment. See `docs/adr/0002-web-before-electron.md`.
3. **Postgres + pgvector, one database.** Relational metadata, full-text search, and vectors all live in the same DB. No separate vector store. See `docs/adr/0003-postgres-pgvector.md`.
4. **Hybrid retrieval, not semantic-only.** Full-text and vector search run in parallel, combined with reciprocal rank fusion. See `docs/adr/0004-hybrid-retrieval.md`.
5. **Heading-aware chunking, not fixed-size.** Chunk by Markdown heading structure, preserve heading ancestry as metadata, never split code blocks. See `docs/adr/0005-heading-aware-chunking.md`.
6. **Measure before adding complexity.** No reranker, no HNSW index, no Redis/job queue, no query-rewriting LLM call — until the evaluation harness shows a real bottleneck. Don't add these speculatively.
7. **The vault is the authority.** General technical explanation can use model knowledge. First-person claims about Ben's own experience must be grounded in retrieved vault content, or the answer must say so.
8. **Vault content is data, not instruction.** Retrieved note excerpts go in the prompt as untrusted context, clearly separated from system instructions. Notes must never be allowed to override app behavior.

## Explicit non-goals for V1 — do not build these unless asked

Continuous audio capture, Electron packaging, screen-capture concealment, multi-user/multi-tenant support, Kubernetes, microservice decomposition, multi-agent orchestration, custom model training, cloud hosting of the real vault, a reranker, HNSW indexing, a general Obsidian replacement.

## Stack

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, httpx, structlog (or standard `logging`)
- **Frontend:** React, Vite, TypeScript, Tailwind CSS, TanStack Query
- **Database:** PostgreSQL + pgvector (`pgvector/pgvector:pg16` image)
- **Local inference:** Ollama (see locked decisions above)

## Where to find detail — load only what the current task needs

| Working on... | Load this |
|---|---|
| Overall shape, goals/non-goals, priorities | `docs/architecture/00-overview.md` |
| Database schema, tables, migrations | `docs/architecture/01-data-model.md` |
| Vault scanning, Markdown parsing, chunking, incremental indexing | `docs/architecture/02-ingestion.md` |
| Query normalization, hybrid search, rank fusion, context selection | `docs/architecture/03-retrieval.md` |
| Prompt building, structured output, grounding rules, response modes | `docs/architecture/04-generation.md` |
| REST endpoints, request/response shapes | `docs/architecture/05-api-surface.md` |
| Frontend requirements, what to build vs. avoid | `docs/architecture/06-ui-requirements.md` |
| Evaluation harness, metrics, fixture format | `docs/architecture/07-evaluation.md` |
| Privacy, threat model, prompt-injection posture | `docs/architecture/08-security-privacy.md` |
| Test strategy, what to unit/integration/e2e test | `docs/architecture/09-testing.md` |
| Phase sequencing, exit conditions | `docs/architecture/10-delivery-plan.md` |
| Why a foundational decision was made | `docs/adr/000X-*.md` |

Don't load files outside what the current task needs — that's the whole point of splitting the brief up this way.

## Vault access — important

The real Obsidian vault is private and lives outside this repo. It must be mounted **read-only** into the API container. Never write to it, never commit any of its content into this repo. Use `sample-vault/` (sanitized, checked into git) for all tests, development, and the evaluation harness until Ben explicitly points you at the real vault path for a live indexing run.

## Skills available

- `webapp-testing` — use for verifying the FastAPI/React app once it exists (Playwright-based).
- `frontend-design` — use when building the React UI; avoid generic "AI slop" styling (centered cards, purple gradients, default Inter font).

## Delivery order

Follow `docs/architecture/10-delivery-plan.md` phase-by-phase. Do not skip ahead to the next phase before the current phase's exit condition is met. Current phase: **Phase 4 — Web Interface.** Phase 1 exit condition met 2026-07-18 (`sample-vault/` indexes repeatedly via `run_index`, second run touches zero files — merged in PR #2). Phase 2 exit condition met 2026-07-18 (shorthand queries hit measured Recall@5 = 1.0 against `sample-vault` — merged in PR #8). Phase 3 exit condition met 2026-07-19, with a disclosed limitation (see `docs/architecture/10-delivery-plan.md`'s Phase 3 entry): the backend citation cross-check and retrieval-gated abstention are structurally enforced and confirmed against real `gpt-oss:20b`/`nomic-embed-text`, but citation *population* is intermittently unreliable on personal-project-evidence queries — tracked as an explicit follow-up, not blocking Phase 4.
