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

**Met, with a disclosed limitation — 2026-07-19.** The safety-critical half of this condition is fully met and structurally enforced, not just tested: `generation/service.py`'s backend citation cross-check makes a fabricated citation impossible to survive into a response (every `used_source_chunk_ids`/`personal_examples[].source_chunk_ids` entry is filtered against the actual retrieved context before being trusted), and the retrieval-quality-gated abstention pre-check (measured, not guessed — see `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md` Task 7) correctly abstains rather than fabricating when the vault lacks evidence. Both were confirmed against the real running pipeline (real Postgres, real `nomic-embed-text`, real `gpt-oss:20b`) in that plan's Task 13.

The "sourced" half has a real, disclosed gap, found by that same real-model verification pass (not by CI, which uses deterministic fakes): `gpt-oss:20b` reliably narrates grounded content in `say_this`/`supporting_points`, but does not reliably populate the `used_source_chunk_ids`/`personal_examples` structured-output fields for every query shape that should have them — one real personal-project-evidence query returned an empty `sources` array despite `confidence: "high"` and narrative content that was genuinely grounded in retrieved evidence, even after the one prompt-wording iteration the plan allows. This fails in the safe direction (under-cites, never fabricates) and is not systemic — a different real query populated both `sources` and `personal_examples` correctly — but it means citations don't reliably appear when they should, which undercuts part of the tool's value even though it never produces a false one. Tracked as an explicit follow-up below rather than absorbed silently into "done."

- [ ] **Follow-up: citation-population reliability.** `gpt-oss:20b` intermittently leaves `used_source_chunk_ids`/`personal_examples` empty on personal-project-evidence queries despite grounded narrative content (see Task 13's write-up in `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md` for the full record). Candidate fixes, not yet attempted: (a) a stricter Ollama structured-output JSON schema that makes `used_source_chunk_ids` effectively mandatory whenever non-empty context was supplied, rather than an optional array the model can leave empty; (b) a second-pass extraction call that re-derives citations from the already-generated `say_this`/`supporting_points` text against the retrieved context, decoupling citation extraction from first-pass narrative generation. Needs its own measurement pass (broader real-query sample, not just the 2 personal-evidence-shaped queries Task 13 had time for) before picking an approach — same "measure before adding complexity" discipline as everything else in this project.

## Phase 4: Web Interface

- Query input and keyboard workflow (`06-ui-requirements.md`).
- Speakable answer display.
- Supporting points and examples.
- Source excerpts.
- Confidence and limitation state.
- Copy action, local history.

**Confidence/limitation state must distinguish two visually different empty-`sources` cases, not collapse them** (see Phase 3's "citation-population reliability" follow-up above): `confidence: "low"` with a stated evidence-lacking limitation is a genuine abstention — the UI should show that plainly. `confidence: "high"`/`"medium"` with an empty `sources` array is a different, narrower case — the answer is grounded but the citation trail didn't populate — and needs its own visual treatment, not a reused "no evidence" state, or the UI would misrepresent a real (if under-cited) answer as a non-answer.

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
