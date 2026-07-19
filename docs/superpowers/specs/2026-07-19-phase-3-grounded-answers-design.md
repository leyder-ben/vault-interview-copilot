# Phase 3: Grounded Answers — Design

**Status:** approved, ready for implementation planning
**Date:** 2026-07-19
**Exit condition (from `docs/architecture/10-delivery-plan.md` / `04-generation.md`):** the API returns concise, sourced answers without fabricated file citations. Verify this explicitly against cases where the vault genuinely lacks evidence — confirm the model abstains correctly rather than filling the gap with a plausible-sounding but ungrounded claim.

## Overview

Phase 2 built retrieval (full-text + vector + RRF fusion) and proved it works (Recall@5 = 1.0, measured). It stopped short of anything past ranked chunk IDs — no context selection, no generation, no `/api/query`. Phase 3 builds the rest of the pipeline described in `04-generation.md`: a real context builder, an Ollama generation adapter, structured-output validation, backend-enforced citation grounding, retrieval-quality-gated abstention, and `POST /api/query` itself.

The core bet of this project (per `CLAUDE.md`) is that retrieval accuracy matters more than generation polish, and that a wrong-but-confident answer is worse than no answer. This phase is where that bet gets implemented as code, not just stated as a principle: the backend — not the model, not a prompt instruction — is what makes a fabricated citation structurally impossible to survive into the response, and what makes a zero-evidence query short-circuit to abstention before the LLM is ever called.

## Corrections carried into this phase (not new work, but must land alongside it)

The generation model changed since `04-generation.md` and `11-locked-decisions.md` were written. The workstation now runs **GPT-OSS 20B** (`gpt-oss:20b`, MXFP4 quant, confirmed via `ollama ps`/`ollama show` — 20.9B params, 131K context), not Qwen2.5 14B. Qwen2.5-**Coder** 14B was evaluated and rejected: its output register is tuned for code completion, not natural spoken-answer prose, which is what this product actually needs.

- `docs/architecture/04-generation.md`: update model reference.
- `docs/architecture/11-locked-decisions.md`: update the "Model selection" section. Also remove the "fits both boxes" claim as settled fact — it was true for Qwen2.5 14B Q4 on the 3060's 12GB VRAM, but is an open question for a 20.9B MXFP4 model on the same box. Doesn't block this phase (provider switching to the ai-inference VM is explicitly deferred, see below), but the doc shouldn't assert something that hasn't been checked.
- `apps/api/app/core/config.py`: `generation_model` default `"qwen2.5:14b"` → `"gpt-oss:20b"`.

Verified live against the running model during design: `/api/chat` with `format=<json_schema>` against `gpt-oss:20b` returns clean, schema-valid JSON on the first attempt (tested with a 4-field schema subset and a real context chunk). `/api/chat` is used over `/api/generate` — its `system`/`user` message roles map directly onto the three-way prompt separation required by `08-security-privacy.md`.

## Explicitly deferred (do not build in this phase)

- **Provider-switching endpoint, `settings` DB table, auto-fallback logic.** `POST /api/settings/provider` and the locked "active provider is a DB row" decision stay deferred until there's a second live, running provider actually worth switching to — the ai-inference VM is powered off by default. `OllamaLLMProvider` takes `base_url` as a constructor argument (never reads `settings` internally), resolved once at the `api/query.py` composition root from `settings.ollama_workstation_url` — the same shape Phase 1 already used for `OllamaEmbeddingProvider`, and the same "one line changes later" seam. No config renaming needed when the settings table lands: `ollama_workstation_url`/`ollama_ai_inference_url` already use the `"workstation"`/`"ai_inference"` vocabulary that `active_provider` will store.
- **Full logic for non-speakable response modes** (`explain`, `compare`, `troubleshoot`, `example`). The `ResponseMode` enum and API shape are real and complete now; only `speakable` has a working prompt + generation path behind it. The other four return a fixed stub `AnswerDraft` (see below) — implementing them is a fast-follow that adds logic behind an already-shaped API, not a schema migration.
- **Standalone `GET /api/source` endpoint.** The resolution logic it would wrap is built as its own reusable function now (`retrieval/sources.py`) specifically so that adding the route later is a one-line addition — see "Source resolution" below.
- **Automated scoring for subjective generation metrics** (speakability rating, concept-coverage nuance). Stays manual spot-check. Citation validity, abstention correctness, answer length, and latency are automated.

## Module layout

```
app/providers/                      (currently empty scaffold — filled in this phase)
  embeddings.py  — MOVED from app/ingestion/embeddings.py (EmbeddingProvider, OllamaEmbeddingProvider)
  llm.py         — NEW: LLMProvider protocol, OllamaLLMProvider, FakeLLMProvider

app/retrieval/
  context.py     — NEW: select(fused_results, session, budget) -> list[RetrievedChunk]
                   (hydrates content, dedups by note, prefers diverse evidence, trims to budget)
  sources.py     — NEW: resolve_sources(session, chunk_ids: list[int]) -> list[SourceCitation]
                   (pure DB lookup: chunk id -> path/heading/start_line/end_line; no score, no
                   generation awareness — reusable standalone by a future GET /api/source handler)

app/generation/                     (currently empty scaffold — filled in this phase)
  schema.py      — NEW: ResponseMode, Confidence, PersonalExample, AnswerDraft, request/response models
  prompt.py      — NEW: build_prompt(query, context: list[RetrievedChunk], mode) -> ChatMessages
  service.py     — NEW: answer(session, llm_provider, query, mode, context) -> AnswerResult
                   (pre-check -> prompt -> provider call -> parse/retry -> citation cross-check ->
                   confidence downgrade -> resolve_sources)

app/api/query.py                    — NEW: POST /api/query
  wires: retrieval.search() -> retrieval.context.select() -> generation.service.answer() ->
  response assembly -> QueryRun telemetry write

apps/api/tests/providers/           — unit tests for OllamaLLMProvider (mocked httpx), FakeLLMProvider
apps/api/tests/retrieval/           — test_context.py, test_sources.py
apps/api/tests/generation/          — test_schema.py, test_prompt.py, test_service.py
                                       (citation cross-check, confidence-floor, pre-check short-circuit,
                                       parse-retry-then-typed-error — all against FakeLLMProvider)
apps/api/tests/test_query_api.py    — POST /api/query integration test, FakeLLMProvider, asserts
                                       QueryRun row written
```

Existing import sites updated for the `embeddings.py` move: `retrieval/search.py`, `ingestion/indexer.py`, `evaluation/runner.py`, `ingestion/cli.py`, `evaluation/cli.py`, `api/retrieval_debug.py`.

`app/providers/` and `app/generation/` already exist as empty scaffolded directories from Phase 0 (matching `app/retrieval/`'s and `app/evaluation/`'s state before Phase 2) — this phase fills them in, and additionally moves `EmbeddingProvider` into `providers/` so both provider protocols (embedding, generation) live under the one module boundary ADR-0001 actually scoped for them, instead of split across `ingestion/` and `providers/`.

## Query flow

```
raw_query, mode (default "speakable"), max_sources
    |
    v
retrieval.search()                    -- unchanged from Phase 2 (normalize, fulltext, vector, RRF fuse)
    |
    v
retrieval.context.select()            -- NEW: hydrate chunk content, dedup by note, prefer diverse
    |                                     evidence over adjacent near-duplicates, prioritize personal
    |                                     project evidence, trim to token/count budget
    |                                     -> list[RetrievedChunk] (id, path, heading, content, score)
    v
retrieval-quality pre-check           -- empty context OR top fused score below a measured threshold
    |                                     (measured against eval fixtures, not guessed)
    |
    +-- FAILS --> deterministic abstention AnswerDraft, skip LLM entirely, confidence=LOW
    |
    +-- PASSES
         |
         v
    mode == "speakable"?
         |
         +-- NO  --> fixed stub AnswerDraft ("mode not implemented"), skip LLM entirely
         |
         +-- YES
              |
              v
         generation.prompt.build_prompt()   -- 3-way separated: system instructions (grounding rules,
              |                                "data not instruction"), user query, context chunks
              |                                (each labeled by chunk ID + heading path)
              v
         OllamaLLMProvider.generate_answer()  -- POST /api/chat, format=<AnswerDraft JSON schema>
              |
              v
         parse response as AnswerDraft
              |
              +-- parse fails --> retry once --> still fails --> typed error AnswerDraft
              |                                                    (never a fabricated answer)
              v
         citation cross-check:
           context_chunk_ids = {c.id for c in context}
           used_source_chunk_ids  filtered to context_chunk_ids
           personal_examples[].source_chunk_ids  filtered per-example;
             an example that loses ALL its source ids is dropped entirely (not just filtered to empty)
           if anything was dropped: confidence downgraded one level, LOW is a floor (stays LOW,
             never goes lower -- zero-evidence is already handled by the pre-check above)
              |
              v
         retrieval.sources.resolve_sources(surviving chunk ids)  -- DB-only, path/heading/lines
              |
              v
         response assembled: answer, sources (resolved paths + retrieval scores merged in by the
           caller here, not by resolve_sources itself), confidence, limitations, timing_ms
              |
              v
         QueryRun row written (raw/normalized query, mode, per-stage latencies, retrieved chunk ids +
           scores, selected source ids, provider/model name) -- skipped if query_logging=False
```

## Structured output schema (`generation/schema.py`)

```python
class ResponseMode(str, Enum):
    SPEAKABLE = "speakable"
    EXPLAIN = "explain"
    COMPARE = "compare"
    TROUBLESHOOT = "troubleshoot"
    EXAMPLE = "example"

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class PersonalExample(BaseModel):
    project: str
    example: str
    source_chunk_ids: list[int]

class AnswerDraft(BaseModel):        # exact shape the LLM is constrained to emit as JSON
    say_this: str
    supporting_points: list[str]
    personal_examples: list[PersonalExample]
    used_source_chunk_ids: list[int]
    confidence: Confidence
    limitations: list[str]
```

`response_mode` is a request parameter (selects prompt template + service path), not a field on `AnswerDraft`. Confidence downgrade order: `HIGH -> MEDIUM -> LOW`; `LOW` is a hard floor.

## Ollama LLM provider (`providers/llm.py`)

```python
class LLMProvider(Protocol):
    def generate_answer(
        self, query: str, context: list[RetrievedChunk], mode: ResponseMode
    ) -> AnswerDraft: ...
```

`OllamaLLMProvider` — `httpx` POST to `{base_url}/api/chat`, `format=<AnswerDraft.model_json_schema()>`, `stream=False`, `model=settings.generation_model`. Constructor takes `base_url: str` (never reads `settings` internally — same pattern as `OllamaEmbeddingProvider`).

`FakeLLMProvider` — deterministic, keyed on query substrings or a fixture map, returns a canned `AnswerDraft`. Lives in the test suite (`tests/providers/fakes.py`), not shipped application code, matching Phase 1's `FakeEmbeddingProvider` precedent. Used by `POST /api/query` integration tests and by CI generally — no live Ollama dependency in standard CI, per `09-testing.md`.

## Evaluation harness extension

New fixture field: `expected_abstain: bool` — cases where the sample/private vault genuinely lacks evidence for the query, used to assert the pre-check short-circuits correctly. New sanitized fixtures needed in `evaluation/datasets/sample-vault/` and corresponding private fixtures (both gated by "don't invent examples when patterns already exist" — reuse `meridian-fixtures.yaml`'s categories where a no-evidence variant makes sense).

Automated generation metrics (extending `app/evaluation/metrics.py`):
- Citation validity — every `used_source_chunk_ids` in the response resolves to a path in the fixture's `expected_notes`.
- Abstention correctness — `expected_abstain` fixtures produce `confidence=LOW` with a limitation stated, and did not call the LLM (checked via `FakeLLMProvider` call count in the test, not just output shape).
- Answer length — `say_this` sentence count within the 2-5 sentence guidance from `04-generation.md`.
- Generation latency p50/p95.

Manual spot-check (not automated): speakability rating, concept-coverage nuance — same treatment retrieval eval gave "eyeballing" before Phase 2's harness existed.

## Testing

Per `09-testing.md`:
- **Unit:** citation cross-check filtering (full drop vs. partial-example drop), confidence downgrade-with-floor, prompt 3-way section separation, `AnswerDraft` schema validation, `resolve_sources` (never takes a raw filesystem path, DB-only).
- **Integration:** `POST /api/query` against `FakeLLMProvider` (deterministic, CI-safe) — happy path, pre-check short-circuit path, non-speakable-mode stub path, parse-failure-retry path, `QueryRun` row assertion.
- **Manual/optional (not standard CI):** one real end-to-end pass against the running `gpt-oss:20b`, mirroring Phase 2's real-`nomic-embed-text` verification — confirms the exit condition against real generation, not just the fake provider.

## Out of scope (restated for clarity)

Provider-switching endpoint and `settings` table, non-speakable mode generation logic, standalone `GET /api/source` route, automated speakability/concept-coverage scoring, reranking, HNSW indexing — none of these block this phase's exit condition and none are being silently assumed for later; they're listed here so a future phase doesn't have to rediscover the boundary.
