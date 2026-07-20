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

**Status: Met — 2026-07-19.** Per the Decision authority section in `CLAUDE.md`, this verdict is Ben's, not one this doc concluded on its own.

The safety-critical half of the exit condition ("without fabricated file citations") is met, and more thoroughly than earlier drafts of this entry claimed: `generation/service.py`'s backend citation cross-check now verifies both that a cited chunk ID was actually present in the context sent to the model (an **out-of-context** ID is impossible to survive into a response) and, as of the relevance guard below, that the chunk's content actually **supports the specific claim** it's cited against — the narrower "membership only" gap flagged earlier the same day has a real, measured, shipped mitigation now, not just a documented gap. The retrieval-quality-gated abstention pre-check (measured, not guessed — see `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md` Task 7) correctly abstains rather than fabricating when the vault lacks evidence. All of this was confirmed against the real running pipeline (real Postgres, real `nomic-embed-text`, real `gpt-oss:20b`) — most recently re-verified end-to-end after the `think='low'` change below, in that plan's final verification section.

**Where the relevance-guard finding actually came from:** it wasn't noticed in isolation — it came out of a deliberate local-vs-frontier comparison run to address the citation-*recall* gap (see the open follow-up below). Local second-pass extraction (`gpt-oss:20b` re-deriving citations from the generated answer text) was measured first: roughly 1-in-3 recall on genuinely eligible cases, 0/36 fabrication (conservative failure mode — it missed real citations but never attached a wrong one), real latency cost on the ~28% of queries that trigger it (p50 17.9s / p95 36.5s combined with pass one). That result didn't move with one tuning attempt. A frontier model (`gpt-4o-mini`) was tested in the same pass-two slot as the next step in that comparison — and instead of clearly outperforming local, it surfaced a worse failure mode: it confidently attached a citation (chunk 24) that was topically adjacent to the query but whose content didn't actually support the claim — the first case that got past the existing cross-check while still being wrong. That single finding is what escalated into the broader investigation: the cross-check only ever verified a cited chunk was *present in context*, never that its *content* supported the claim. **That's the actual origin of the relevance guard below** — not an incidental one-query notice, but the direct output of testing whether a frontier model could fix local's recall gap and finding it introduced a worse problem instead.

**What happened since:** (1) the citation cross-check's membership-only gap was broadened from one query/one chunk to 4 chunks and 4 real queries (92 hand-labeled pairs total), and a deterministic lexical-overlap relevance check (`app/generation/relevance.py`, `Settings.citation_relevance_threshold = 0.30`) was shipped into `generation/service.py`'s cross-check on the strength of that broader validation — measured precision 0.93, recall 0.97 on the combined labeled set, with the finding that severity was chunk-shape-dependent (one short/generic chunk drove nearly all of the original problem; three others of different shapes and lengths were cited with high precision). (2) Separately, `gpt-oss:20b`'s reasoning effort was found to be the dominant driver of end-to-end latency — unset (effectively high) reasoning effort cost ~10.4s median / 17-22s tail per call for hidden reasoning tokens this app never reads; `think='low'` cut that to 2-5s across 30+ real reps with no loss of structured-output validity, and is now the shipped default (`providers/llm.py`), re-verified against the live API. This was a performance fix, layered on top of the citation-quality work, not a resolution of either citation finding — see `docs/architecture/11-locked-decisions.md`'s new "Generation reasoning effort" section.

**What stays open, disclosed and tracked, not resolved:** the citation-*recall* gap — `gpt-oss:20b` reliably narrates grounded content but doesn't reliably populate `used_source_chunk_ids`/`personal_examples` for every query that should have them (roughly half of eligible queries in the broader sample, 5/9) — is unchanged by either of the fixes above. The relevance guard makes a *wrong* citation less likely to survive; it does nothing for a *missing* one. This gap is real, measured, and explicitly not being called resolved by this "Met" verdict — it's the reason the follow-up bullet below stays open rather than being checked off.

- [ ] **Follow-up: citation-population reliability — one real attempt made, inconclusive, not resolved.** `gpt-oss:20b` leaves `used_source_chunk_ids`/`personal_examples` empty on roughly half of eligible queries despite grounded narrative content — measured at 5/9 across a 10-query broader sample (see `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md`, Task 13's write-up plus the "Citation-population reliability, broader sample" section after it, for the full per-query record). This is the one exit-condition gap that stays open after Phase 3's "Met" verdict above — the citation-relevance guard (see the now-closed follow-up below) addresses over-citation, not under-citation, and doesn't touch this.

  **Candidate fix (a) — stricter Ollama structured-output schema** making `used_source_chunk_ids` effectively mandatory whenever non-empty context was supplied — not yet tried.

  **Candidate fix (b) — second-pass extraction call re-deriving citations from the generated `say_this`/`supporting_points` text.** One real attempt made on each variant, both real numbers, neither adopted:
  - *Local second pass* (`gpt-oss:20b`): ~1-in-3 recall on genuinely eligible cases, 0/36 fabrication, didn't improve after one tuning attempt. Real latency cost on the ~28% of queries that trigger it — p50 17.9s / p95 36.5s combined with pass one. Conservative failure mode: missed citations, never attached a wrong one.
  - *Frontier second pass* (`gpt-4o-mini`): tested specifically to see if a frontier model would clear local's recall ceiling. It didn't get a clean recall measurement — the run surfaced the topical-adjacency over-citing problem (chunk 24) before the comparison finished, which redirected the investigation into the relevance-guard work above instead. **The actual question this follow-up is named for — does a frontier second pass recover meaningfully more real citations than local's 1-in-3 — was never answered.**

  Now that a real relevance guard sits downstream of any second pass (local or frontier), the frontier second-pass's over-citing failure mode may no longer be disqualifying the way it looked mid-investigation — worth a fresh, focused recall measurement (frontier pass two + existing relevance guard, same query set) before deciding between shipping local pass-two's modest-but-real 1-in-3 recovery, retrying frontier now that the guard exists, or shipping with disclosed omission and revisiting later. This decision is Ben's per the Decision authority section in `CLAUDE.md` — not defaulted to here.

- [x] **Follow-up: citation cross-check verifies membership, not relevance — resolved 2026-07-19.** Was: roughly 95-100% of citations attached to the single highest-ranked context chunk for one test query did not trace to that chunk's actual content. Broadened to 4 chunks/4 queries (92 labeled pairs) before any fix was built, then closed with a shipped, tested relevance guard (`app/generation/relevance.py`, threshold 0.30, precision 0.93/recall 0.97 on the labeled set) — see `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md`'s "Citation relevance check — broader validation and implementation" section for the full record. Caveat carried forward, not resolved by this checkmark: 4 chunks/4 queries is real evidence, not an exhaustive characterization — a chunk shape not yet tested (much longer content, code-heavy content) could still behave differently.

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
