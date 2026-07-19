# Locked Decisions (2026-07-14 stress-test pass)

These supersede anything elsewhere in `docs/architecture/` where they conflict. Also summarized at the top of `CLAUDE.md` — this file has the full reasoning.

## Provider hosting — no containerized Ollama

Two real boxes are in play:

- **Workstation** (RTX 5060 Ti, 16GB VRAM) — Ollama already installed and running. Default/primary target. Zero new setup, and it's the box actually in front of Ben during a live interview.
- **ai-inference VM** (RTX 3060, 12GB VRAM) — not running by default (reserved static IP, powered off). Registered as fallback, not primary.

Both endpoints registered in `.env` as named URLs. **Which one is active is a Postgres `settings` table row (`active_provider`), not a config-file setting** — switchable at runtime via `POST /api/settings/provider`. Switching triggers a health check against the new target before committing. If the active provider fails mid-query, the app auto-falls-back to the other registered provider and surfaces that it did.

Reasoning: prove the workstation is sufficient before standing up a second always-on inference box for a tool that doesn't need one yet (measure-before-complexity principle).

## Model selection

- **Generation:** GPT-OSS 20B (`gpt-oss:20b`, MXFP4 quant, 131K context) via Ollama, confirmed running on the workstation. Qwen2.5-Coder 14B was evaluated and rejected — its output register is tuned for code completion, not natural spoken-answer prose, which this product needs. Whether GPT-OSS 20B (20.9B params) fits the ai-inference VM's 3060 (12GB VRAM) the way Qwen2.5 14B Q4 did is now an **open question, not a settled fact** — provider switching to that box is deferred (see `docs/superpowers/specs/2026-07-19-phase-3-grounded-answers-design.md`), so this doesn't block anything yet, but don't assume it fits until it's actually checked.
- **Embedding:** `nomic-embed-text` via Ollama. Small footprint, no real VRAM contention on either box. **This choice is effectively permanent once indexing starts** — changing it means a full reindex, not a config swap.

## Generation reasoning effort — `think='low'`, not unset

GPT-OSS 20B is a "thinking"-capable model. With no `think` value set on the Ollama `/api/chat` request — the default this codebase shipped with through most of Phase 3 — Ollama runs it at unconstrained/high reasoning effort. Measured 2026-07-19 (see `docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md` for the full investigation): unset reasoning effort cost **~10.4s median / 17-22s tail per call**, generating thousands of characters of hidden chain-of-thought (`message.thinking`) that this app never reads — `providers/llm.py` only ever consumed `message.content`. That's pure latency cost for zero measured benefit.

`think='low'` cut real per-call latency to **2-5s across 30+ real reps**, with no loss of structured-output validity — every one of those reps produced a valid, schema-parseable `AnswerDraft`. `think=false` (fully disabled) was tested and rejected: it returns empty `content` with `done_reason: stop`, breaking structured output entirely for this model — not a viable option at any speed. `think='medium'` was also tested (~8s) and rejected as a worse latency/benefit tradeoff than `'low'` once `'low'` was shown to work.

**This is now the shipped default** — `providers/llm.py`'s `_chat_once` sets `"think": "low"` unconditionally, no settings toggle, matching this project's "no config file for something a single user doesn't need to choose" posture elsewhere.

**One explicit caveat, stated plainly rather than dressed up with false precision:** unlike the latency numbers above (real, repeated, measured), spoken-answer *quality* at `think='low'` was only spot-checked across 4 real queries and read by eye as accurate and appropriately detailed — this was a judgment call, not a scored metric. It is not held to the same evidentiary bar as `abstention_score_threshold` or `citation_relevance_threshold`, both of which were locked in against real labeled data. If answer quality is ever suspected to have regressed, that suspicion deserves its own real measurement before being dismissed or confirmed.

## Vault ingestion ignore patterns

```yaml
ignore_patterns:
  - ".git/**"
  - ".obsidian/**"
  - ".trash/**"           # Obsidian's deleted-file holding pen — indexing this
                            # would resurface content already deliberately removed,
                            # including superseded duplicate drafts.
  - "_Templates/**"        # Fill-in-the-blank scaffolding, not real content.
  - "_Agents/**"           # Planned agent-instruction layer. These are directives
  - "_Skills/**"           # written FOR an AI to follow — the literal edge case
  - "_Workflows/**"        # the "vault is data, not instruction" stance exists for.
  - "_About-Ben/**"

  # Do NOT use a blanket "_*/**" catch-all — it would also swallow
  # _Source-Docs/ folders (Whetstone, Interview-Copilot, Surplus-Intelligence-
  # Platform, Bootcamp-Deliverables), which hold real indexable content
  # (mock interview transcripts, brainstorm docs, README sources), not
  # scaffolding. List scaffolding folders explicitly instead.
```

`00-Inbox/` is deliberately **not** ignored — zero-friction capture; freshly landed, not-yet-filed notes should still be searchable.

## Deployment

`pgvector/pgvector:pg16` (or matching version) as the base Postgres image — not stock `postgres` + a manual extension build, which is a known time-sink in Phase 0.

## Repo name

`vault-interview-copilot` — locked, matches what the brief called it from the start. No reason to rename a portfolio repo whose real selling points are the ADRs and evaluation methodology.

## Query logging default

**On by default**, with an easy purge path (`DELETE FROM query_runs`, or a `--no-log` flag for a one-off private run) rather than an off-by-default toggle with UI. The evaluation strategy (Recall@5, MRR, benchmarking) depends on real query history existing to measure against — logging is a feature here, not just a liability, as long as this stays single-user and local. Revisit hard if this tool ever becomes hosted/multi-user.
