# Vault Ingestion

The ingestion layer is the project's primary differentiator — it understands Obsidian/Markdown structure rather than treating the vault as generic text files.

## Ignore patterns — see CLAUDE.md locked decisions for the authoritative list

Do not rederive this list. It's drafted against the real vault structure, not a hypothetical one. The critical detail: use explicit named folders, never a blanket `_*/**` pattern, because that would wrongly swallow `_Source-Docs/` folders which hold real indexable content (mock interview transcripts, brainstorm docs, README sources).

## File scanning

For each Markdown file:

- Record vault-relative path.
- Calculate a content hash — **authoritative** for change detection, not modification time.
- Compare hash to last indexed version; skip unchanged files.
- Detect deleted and renamed files.
- Apply the ignore patterns from CLAUDE.md.

## Markdown parsing

Parse and preserve:

- YAML frontmatter
- Title
- Heading hierarchy
- Tags, aliases
- Wikilinks, Markdown links
- Fenced code blocks (never split these during chunking)
- Lists and tables where practical
- Source line ranges

## Chunking strategy — see `docs/adr/0005-heading-aware-chunking.md` for full reasoning

Do **not** start with fixed-size (e.g. 500-character) chunks.

Order of operations:

1. Split by heading-defined semantic sections.
2. Preserve heading ancestry with each chunk.
3. Keep fenced code blocks intact — never split inside one.
4. Split oversized sections by paragraph/token limits only when a section itself is too large.
5. Add semantic overlap only where needed, not by default.
6. Never join unrelated neighboring sections just to hit a target chunk size.

Each embedded chunk includes contextual metadata prepended to the content:

```text
Document: Whetstone Platform
Path: Projects/Whetstone/Infrastructure.md
Section: Infrastructure > Terraform > Drift Management
Tags: aws, terraform, devops, whetstone

[Section content]
```

## Incremental indexing

An indexing run should:

- Insert new notes and chunks.
- Replace chunks for changed notes.
- Remove chunks for deleted notes.
- Treat renames as delete-plus-add initially (don't build rename detection heuristics for V1 unless it becomes a real problem).
- Record counts, duration, errors, and embedding model version in `index_runs`.
- Avoid rebuilding the entire vault for one changed file — this is the whole point of content-hash-based change detection.

**Embedding model is effectively permanent once indexing starts.** Changing it means a full reindex, not a config swap. Don't change `nomic-embed-text` casually.

## Phase 1 exit condition

A sample vault can be indexed repeatedly without rebuilding unchanged files. Verify this explicitly — run the indexer twice on an unchanged `sample-vault/` and confirm the second run touches zero files.
