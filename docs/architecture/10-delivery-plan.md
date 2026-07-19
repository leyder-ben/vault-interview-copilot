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

**Status: implementation complete, exit condition pending Ben's review — 2026-07-19.** Per the Decision authority section in `CLAUDE.md`, this is a finding to decide on, not a conclusion this doc draws for itself.

The safety-critical half of the exit condition ("without fabricated file citations") is met in the narrow sense that's been verified: `generation/service.py`'s backend citation cross-check makes an **out-of-context** citation (an ID not present in the chunks actually sent to the model) impossible to survive into a response, and the retrieval-quality-gated abstention pre-check (measured, not guessed — see `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md` Task 7) correctly abstains rather than fabricating when the vault lacks evidence. Both were confirmed against the real running pipeline (real Postgres, real `nomic-embed-text`, real `gpt-oss:20b`) in that plan's Task 13. **This claim needs a narrower scope than earlier drafts of this entry stated:** the cross-check verifies chunk-ID *membership* in context, not whether the chunk's content actually *supports* the specific claim it's cited against — see the second follow-up below, found later the same day, for a real gap in that narrower distinction.

The "sourced answers" half has a measured gap, found by that same real-model verification (not by CI, which uses deterministic fakes) and then quantified across a broader sample: `gpt-oss:20b` reliably narrates grounded content in `say_this`/`supporting_points`, but does not reliably populate the `used_source_chunk_ids`/`personal_examples` structured-output fields for every query that should have them. Task 13's initial pass found this on 1 of 2 real queries; a follow-up 10-query broader sample (`docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md`, "Citation-population reliability, broader sample" section, appended after Task 13) measured **5 of 9 queries that narrated grounded Meridian-specific content actually got populated citations** (the 10th query didn't retrieve Meridian-specific content at all, so it wasn't a fair test and was excluded from the denominator). This fails in the safe direction (under-cites, never fabricates) — one response's own text noted a citation attempt had been stripped by the backend verification, suggesting the model does sometimes attempt a citation that then fails cross-check rather than never attempting one — but at roughly half the eligible queries, this is a real reliability gap, not an edge case. Whether that measured rate is acceptable to ship Phase 3 on is Ben's call; tracked as an explicit follow-up below either way.

- [ ] **Follow-up: citation-population reliability.** `gpt-oss:20b` leaves `used_source_chunk_ids`/`personal_examples` empty on roughly half of eligible queries despite grounded narrative content — measured at 5/9 across a 10-query broader sample (see `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md`, Task 13's write-up plus the "Citation-population reliability, broader sample" section after it, for the full per-query record). Candidate fixes, not yet attempted: (a) a stricter Ollama structured-output JSON schema that makes `used_source_chunk_ids` effectively mandatory whenever non-empty context was supplied, rather than an optional array the model can leave empty; (b) a second-pass extraction call that re-derives citations from the already-generated `say_this`/`supporting_points` text against the retrieved context, decoupling citation extraction from first-pass narrative generation. One data point worth investigating first: one response's own text indicated a citation was attempted and then stripped by backend verification, not simply omitted — worth checking whether that's the dominant failure mode before picking a fix.

- [ ] **Follow-up: citation cross-check verifies membership, not relevance — a second, separate exit-condition concern.** Not a duplicate of the bullet above (that one is about the model under-citing; this one is about what happens when it *does* cite). Measured on 2026-07-19 across three independent conditions (default reasoning, `think='low'` with and without a targeted prompt guardrail — see `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md`'s "Citation cross-check verifies membership, not relevance" section for the full table and methodology): roughly 95-100% of citations attached to the single highest-ranked context chunk for one test query did not trace to that chunk's actual content, across all three conditions, including after a one-line prompt guardrail specifically targeting this behavior (a clean negative result — the guardrail changed nothing). Every one of these citations passed the existing cross-check cleanly, since the cited chunk genuinely was in context — the cross-check was never designed to catch this, and doesn't. Confirmed narrowly: one chunk (short, topically on-the-nose, content-thin), one query. Not confirmed: whether this generalizes to other chunk shapes or other queries. A candidate fix (a deterministic content-relevance check, prototyped against already-hand-labeled data before any live-model validation) is being evaluated separately — not yet adopted, per the Decision authority section in `CLAUDE.md`.

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
