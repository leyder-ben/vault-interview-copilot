# Phase 1 Design — Vault Indexing

**Date:** 2026-07-16
**Source:** `Phase-1-Scope.md` (private vault, `03-Projects/Interview-Copilot/`), `docs/architecture/02-ingestion.md`, `docs/architecture/01-data-model.md`, `docs/adr/0005-heading-aware-chunking.md`, `docs/architecture/09-testing.md`.

## Goal

Index a sample Obsidian vault into Postgres (notes + heading-aware chunks + embeddings), incrementally, and prove it via a repeatable no-op second run. This is Phase 1 of `docs/architecture/10-delivery-plan.md`. No retrieval or generation work here — that's Phase 2/3.

**Exit condition (unchanged from delivery plan):** run the indexer twice against an unchanged `sample-vault/`; the second run touches zero files.

## Scope decisions made during brainstorming

These resolve gaps between the vault's `Phase-1-Scope.md` note and the current repo state (Phase 0 deliberately deferred some things this note assumed were already in place):

1. **No `settings` table this phase.** The embedding provider reads `settings.ollama_workstation_url` directly from `app.core.config` (env-based `pydantic-settings`), hardcoded to the workstation Ollama instance. The Postgres `settings` table + `POST /api/settings/provider` + auto-fallback switching (per `docs/architecture/11-locked-decisions.md`) is deferred to Phase 3, when the generation adapter exists and provider choice actually has two live consumers instead of one. Embeddings don't need runtime switching in V1 (`nomic-embed-text` is described as "effectively permanent once indexing starts" anyway).
2. **No `POST /api/index/run` this phase.** Indexing is triggered via a CLI entry point (`python -m app.ingestion.cli`). The manual-run HTTP endpoint from `docs/architecture/05-api-surface.md` is deferred until something (a UI, a scheduler) actually needs to trigger it over HTTP. Only `GET /api/index/status` (read-only) is built now, per `Phase-1-Scope.md`'s explicit build order.
3. **Sample vault uses fictional content in the vault's real flavor.** A new, invented project codename ("Meridian") with realistic DevOps/infra topics (Terraform, Kubernetes, CI/CD, troubleshooting stories) — structurally and tonally like the real vault, but not copied from it and not reusing real codenames (Whetstone, Field Ops, TC1–3, P2).
4. **Token counting uses `tiktoken` (cl100k_base) as an approximation.** Not exact for Qwen2.5/nomic-embed-text's actual tokenizers, but adequate for chunk-size budgeting decisions — the only thing `chunks.token_count` is used for in V1. One small, well-known dependency vs. a cruder `len(text) // 4` heuristic.
5. **Oversized-section threshold is a config value, not a hardcoded constant.** Added to `app.core.config.Settings` as `chunk_max_section_tokens: int = 400`, env-overridable (`CHUNK_MAX_SECTION_TOKENS`). Keeps it tunable from evaluation results without a code change, consistent with the rest of `Settings`' naming style (`embedding_model`, `generation_model`).

## Module layout

New code under `apps/api/app/ingestion/`, following the existing `ingestion/retrieval/generation/providers/db` module boundary from `docs/adr/0001-modular-monolith.md`:

```
app/ingestion/
  scanner.py     # walks vault dir, applies ignore list, computes content hash
  parser.py      # frontmatter + heading hierarchy + code fences + links
  chunker.py     # heading-aware splitting, oversized-section fallback, content_with_context
  embeddings.py  # EmbeddingProvider protocol + OllamaEmbeddingProvider
  indexer.py     # orchestrates scan -> diff -> parse -> chunk -> embed -> upsert -> index_runs row
  cli.py         # `python -m app.ingestion.cli` manual entry point
app/api/index_status.py   # GET /api/index/status
```

### Parser: hand-rolled, not a Markdown library

`parser.py` is a line-based scanner, not `markdown-it-py`/`mistune`. Reasoning: headings (`^#{1,6}\s`) and fenced code blocks (```` ``` ````/`~~~` toggling) are simple regex/state-machine detectable, and a hand-rolled pass gives exact 1:1 source line numbers for free — no need to map back from a generic AST's token positions. Wikilinks (`[[Note]]`, `[[Note|alias]]`) aren't standard Markdown, so a library wouldn't help there regardless; they're regex-extracted from raw text alongside standard `[text](url)` links.

Parser output (`ParsedNote`):
- `frontmatter: dict` (YAML, via `yaml.safe_load`)
- `title: str` (frontmatter `title` field if present, else first `#` heading, else filename)
- `tags: list[str]`, `aliases: list[str]` (from frontmatter)
- `sections: list[Section]` — each with `heading_path: str` (e.g. `Infrastructure > Terraform > Drift Management`), `level: int`, `start_line: int`, `end_line: int`, `content: str`, `code_block_ranges: list[tuple[int, int]]`
- `links: list[Link]` — `target`, `link_text`, `link_type` (`"wikilink"` or `"markdown"`)

A note with no headings at all produces a single implicit section spanning the whole body (heading_path `None`), covering the ADR's "notes with no headings" edge case.

## Chunker

Implements `docs/adr/0005-heading-aware-chunking.md` order of operations:

1. One chunk candidate per heading-defined section (from the parser's `sections`).
2. If a section's token count (via `tiktoken`) exceeds **~400 tokens**, fall back to paragraph splitting within that section only. Code fence line ranges are protected — the fallback splitter never cuts inside one.
3. `content_with_context` is built per the ADR's format:
   ```
   Document: <title>
   Path: <vault-relative path>
   Section: <heading_path>
   Tags: <comma-joined tags>

   <section or sub-chunk content>
   ```
4. No semantic overlap is added by default (per the ADR — only add it if evaluation later shows it's needed).

**Why ~400 tokens:** a heuristic default, not a measured number.
- Smaller, focused chunks retrieve more precisely — embedding a large chunk averages its semantics across everything in it, diluting the vector. Common RAG guidance sits in the 200–500 token range for this reason.
- Keeps downstream context budget manageable: even if hybrid retrieval (Phase 2) pulls back several chunks for one answer, the total stays reasonable for the 14B generation model's prompt without needing a smarter budgeting scheme yet.
- Expected to rarely trigger: most heading-defined sections in this kind of vault (STAR stories, troubleshooting entries, focused technical write-ups) are naturally under 400 tokens. The fallback exists for outliers (an unusually long code walkthrough, an unstructured wall of text under one heading), not the common case.
- Not tuned now, by design (`CLAUDE.md` principle: measure before adding complexity). If Phase 2's evaluation harness shows retrieval precision suffers at this size, it's a `settings.chunk_max_section_tokens` env-var change, not a code change.

### Chunk-level content hashing and embedding reuse

`chunks.content_hash` is `sha256` of the chunk's raw `content` (not `content_with_context` — the prepended metadata shouldn't force a re-embed just because, say, a tag changed elsewhere). It exists so a changed note doesn't force re-embedding chunks that didn't actually change:

When a note's file-level hash changes, the indexer re-parses and re-chunks it, then diffs the new chunk list against the note's existing `Chunk` rows keyed by `heading_path`:
- Same `heading_path`, same `content_hash` → reuse the existing row's `embedding` unchanged; only update line ranges/`chunk_index` if they shifted. **No embedding call.**
- Same `heading_path`, different `content_hash` → that section actually changed; re-embed just this chunk.
- New `heading_path` → new chunk; embed it.
- An old `heading_path` no longer present → delete that chunk row.

This matters beyond correctness: most real edits touch one section of a note, not the whole thing, so this avoids re-embedding an entire large note over a one-paragraph edit — directly relevant once this points at a much larger vault.

## Embedding provider

`embeddings.py` defines a small `Protocol` — **batch-shaped from the start**, not per-chunk:

```python
class EmbeddingProvider(Protocol):
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

`OllamaEmbeddingProvider` is the real implementation — `httpx` POST to `{base_url}/api/embed` (Ollama's newer batch endpoint, not the older single-prompt `/api/embeddings`) with `{"model": "nomic-embed-text", "input": texts}`, returns the list of `embeddings` in the same order as the input list.

**The provider takes `base_url: str` as a constructor argument — it does not read `settings` internally.** The CLI (`cli.py`, the composition root that constructs it) resolves `base_url=settings.ollama_workstation_url` for now. This matters for Phase 3: the locked provider-hosting decision (`docs/architecture/11-locked-decisions.md`) says the active provider becomes a Postgres `settings` table row (`active_provider`, valued `"workstation"` or `"ai_inference"` — already the same vocabulary as the `ollama_workstation_url`/`ollama_ai_inference_url` config key suffixes, so no renaming needed there). When that lands, only the one-line resolution at the construction site changes (query the DB row, map its value to the matching config key) — `OllamaEmbeddingProvider` itself doesn't need to change at all, since it never knew where `base_url` came from.

**Why batch, not one call per chunk:** a single-chunk-per-request design works fine against `sample-vault/`'s handful of notes, but would not hold up once this points at a full personal knowledge vault — thousands of notes means thousands of round trips, and network/request overhead (not model compute) becomes the bottleneck. Batching per note (typically a handful of chunks) cuts that dramatically without needing async workers or a job queue, which would be premature complexity for this phase. Combined with the chunk-level reuse logic above (only unchanged-content chunks get skipped; new/changed chunks within a note are batched into one call), this keeps indexing-at-scale reasonable while staying a plain synchronous function — no concurrency model to test or reason about yet. If evaluation against a real full-size vault later shows even batched-per-note calls are too slow, the next lever is batching across notes within a run, not a queue/worker system — call that out as the actual next step if it comes up, rather than building it speculatively now.

Tests use a fake deterministic provider (hash-seeded fixed-768-dim vectors, matching `EMBEDDING_DIM` in `app/db/models.py`) — no live Ollama dependency in CI, per `docs/architecture/09-testing.md`'s "no model dependency in standard CI" rule. The fake lives in the test suite, not shipped application code.

## Indexer: incremental upsert flow

`indexer.run_index(session, vault_path, embedding_provider) -> IndexRunResult`:

1. Scan `vault_path` recursively via `scanner.py`, skipping ignored dirs by exact name (`.git`, `.obsidian`, `.trash`, `_Templates`, `_Agents`, `_Skills`, `_Workflows`, `_About-Ben` — never a blanket `_*` pattern, per `CLAUDE.md`). Collect `.md` files with vault-relative path, sha256 content hash, and mtime.
2. Load existing `notes` rows keyed by `vault_path`.
3. For each scanned file:
   - **New path** → parse, chunk, batch-embed all of the note's chunks in one `embed_batch` call, insert `Note` + `Chunk` rows + `NoteLink` rows. `Note.embedding_version` is set to `settings.embedding_model` (`"nomic-embed-text"`). Count as added.
   - **Existing path, hash unchanged** → skip entirely — no parse, no chunk, no embed, no DB write. This is what makes the exit condition provable.
   - **Existing path, hash changed** → parse, chunk, diff against existing `Chunk` rows by `heading_path`/`content_hash` (see "Chunk-level content hashing" above); batch-embed only the new/changed chunks in one `embed_batch` call; reuse embeddings for unchanged chunks; update the `Note` row (`content_hash`, `modified_at`, `frontmatter_json`, `tags`, `aliases`, `indexed_at`, `embedding_version`); replace its `NoteLink` rows. Count as updated.
4. Any `notes` row whose `vault_path` wasn't among this run's scanned files → delete (cascades to `chunks` and `note_links` via `ondelete="CASCADE"`). Count as deleted.
5. Write one `index_runs` row: `started_at`/`completed_at`, `status`, `files_scanned`/`files_added`/`files_updated`/`files_deleted`, `chunks_created`/`chunks_deleted`, `errors_json`.

**Renames are delete-plus-add** — no rename detection, per `Phase-1-Scope.md` and `02-ingestion.md`.

### Error handling

Each file is processed inside its own try/except during step 3 — one bad file (e.g. malformed frontmatter) is recorded into `errors_json` as `{vault_path, error}` and does not abort the run. `index_runs.status` is `"success"` when `errors_json` is empty, `"partial"` when some files failed but the run completed, `"failed"` only if something prevents scanning from starting at all (e.g. `vault_path` unreadable).

## API surface added this phase

`GET /api/index/status` — read-only, returns the most recent `index_runs` row plus a current `notes` count and the embedding model version (read from `settings.embedding_model`, since `notes.embedding_version` should be uniform across all rows in V1 — there's only ever one embedding model active at a time). Matches `docs/architecture/05-api-surface.md`.

## CLI entry point

`python -m app.ingestion.cli` — wires a DB session, `OllamaEmbeddingProvider(base_url=settings.ollama_workstation_url)`, and `settings.vault_path`, calls `indexer.run_index()`, and prints a summary. This is the manual way to run indexing and to hand-verify the exit condition before the integration test does it automatically. This is also the single line Phase 3 will change to read the active provider from the DB instead.

## Sample vault content

`sample-vault/` is currently empty (`.gitkeep` only) — this is a blocker per `Phase-1-Scope.md` item 0. New fictional content, codenamed **"Meridian"**, structurally matching the real vault's conventions (function-based folders, frontmatter, tags) without reusing real project names or content:

- `00-Inbox/Quick-Note-Kubernetes-Question.md` — no headings at all (exercises the headingless-note edge case); proves `00-Inbox/` is **not** ignored.
- `02-Technical-Reference/Terraform/Terraform-Fundamentals.md` — nested headings (`##`/`###`), a fenced `hcl` code block, wikilinks to talking-points notes, frontmatter tags/aliases.
- `02-Technical-Reference/Kubernetes/Kubernetes-Fundamentals.md` — headings on HPA vs. Cluster Autoscaler, a fenced `yaml` code block.
- `01-Interview-Prep/Project-Talking-Points/Meridian-Tool-Stack-Articulation.md` — wikilinks back to the technical-reference notes above.
- `01-Interview-Prep/Technical-Concepts/CICD-Pipeline-Walkthrough.md` — a fenced GitHub Actions YAML snippet, multiple headings.
- `02-Technical-Reference/Troubleshooting-Log/Interview-Ready-Troubleshooting-Stories.md` — STAR-style headings (Situation/Task/Action/Result).
- `03-Projects/Meridian/_Source-Docs/Mock-Interview-Notes.md` — under a `_Source-Docs/`-style folder; proves the ignore list's explicit-named-folders approach does **not** wrongly swallow it via a blanket `_*` pattern.
- `_Templates/STAR-Story-Template.md` — inside an actually-ignored folder; proves the ignore list **does** exclude what it's supposed to.

7 indexable notes + 1 deliberately-ignored one, within the "5–10 sanitized notes" guidance in `Phase-1-Scope.md`.

## Testing

**Unit tests** (`apps/api/tests/ingestion/`):
- Scanner: ignore-list correctness, including the `_Source-Docs` (indexed) vs. `_Templates` (ignored) distinction; content-hash stability across identical content.
- Parser: frontmatter extraction, heading hierarchy + line ranges, code-fence detection, wikilink/markdown-link extraction, headingless-note handling.
- Chunker: section-boundary splitting, oversized-section fallback triggering at the ~400-token threshold, code blocks never split, `content_with_context` format.
- Embedding client: `OllamaEmbeddingProvider.embed_batch` request/response handling (batch in, ordered batch out) against a mocked `httpx` transport.
- Indexer: chunk-reuse diffing — unchanged chunks keep their embedding and produce no `embed_batch` call content; changed/new chunks are the only ones batched for embedding.

**Integration tests** (real Postgres, matching Phase 0's CI setup, fake embedding provider substituted in — no live Ollama needed), all operating on a **temporary copy** of `sample-vault/` rather than the committed fixture directory, so mutating/deleting tests don't touch checked-in files:

1. Index the temp copy twice with nothing changed in between → the second run's `index_runs` row shows `files_added = files_updated = files_deleted = 0` (the core exit-condition proof).
2. Modify one section of one file's content in the temp copy, then reindex → only that file's `Note` row and the changed section's `Chunk` row are touched; its other chunks keep their original `embedding` values (proving the chunk-level reuse logic, not just note-level skip); everything else in the vault is untouched.
3. Delete a file from the temp copy, then reindex → its `Note` row (and cascaded `Chunk`/`NoteLink` rows) are gone.

**CLI:** `python -m app.ingestion.cli` run manually against `sample-vault/` twice is the hand-verification of the exit condition, mirroring integration test #1.

## Non-goals for this phase (explicitly deferred)

- Retrieval (full-text, vector, rank fusion) — Phase 2.
- The `settings` table, `POST /api/settings/provider`, provider health-check/fallback — Phase 3.
- `POST /api/index/run` HTTP trigger — deferred until something needs it over HTTP.
- Rename detection — not planned for V1 per `Phase-1-Scope.md`.
- Semantic chunk overlap — only added later if evaluation shows a need.
