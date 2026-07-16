# ADR-005: Heading-Aware Markdown Chunking

**Status:** Accepted
**Date:** 2026-07-15

## Context

The vault isn't generic prose — it's structured Markdown with a deliberate heading hierarchy, frontmatter, tags, and wikilinks (per the vault's own conventions: function-based folders, consistent frontmatter, ICM-style scoped loading). A fixed-size chunking strategy (e.g., every 500 characters) ignores that structure entirely. It will cut a troubleshooting story in half mid-sentence, split a STAR story's Situation from its Result, or merge the tail of one section with the head of an unrelated one just because they happened to land in the same character window.

For this tool specifically, a chunk that loses its heading context also loses the thing that makes it citable and speakable — "Terraform Drift Management" as a heading tells the retrieval and generation layers something a mid-paragraph character cutoff never will.

## Decision

Chunk by heading-defined semantic sections first, preserving heading ancestry with each chunk (e.g., `Infrastructure > Terraform > Drift Management`). Keep fenced code blocks intact — never split inside one. Only fall back to splitting by paragraph and token limits when a heading-defined section is oversized. Add semantic overlap only where needed, not by default. Never join unrelated neighboring sections just to hit a target chunk size.

Each embedded chunk carries contextual metadata alongside its content — document title, vault path, full heading path, and tags — not just the raw text.

## Alternatives Considered

**Fixed-size chunking (e.g., 500 characters with overlap):** rejected as the starting strategy. It's simpler to implement, but it actively works against this vault's structure — arbitrary cutoffs mid-section are exactly the failure mode that produces bad citations and incomplete personal examples, which is the one thing this tool can't afford to get wrong (Section 5.3 — the vault is the authority, and a broken citation undermines that).

**Sentence-window or fixed-token chunking without heading awareness:** rejected for the same reason — better than raw character cutoffs, but still blind to the actual semantic boundaries the vault's own author (Ben) already built in via the heading hierarchy. Ignoring structure that already exists and re-deriving worse structure algorithmically doesn't make sense here.

This is the difference between cutting pipe to a tape measure versus cutting it at the joints — the joints are already the correct places to cut; measuring blind and cutting through the middle of a fitting just creates a mess you have to clean up later.

## Consequences

**Good:** Chunks stay conceptually whole, citations point to real, complete sections instead of mid-sentence fragments, and code blocks never get mangled by a cutoff landing in the middle of a script. Heading ancestry embedded in the chunk gives the retrieval layer real signal (a query for "terraform drift" benefits from a chunk that carries `Infrastructure > Terraform > Drift Management` as metadata, not just body text).

**Trade-off:** More implementation work upfront than a naive fixed-size splitter — the chunker has to actually parse heading hierarchy, track oversized-section fallback logic, and handle edge cases (notes with no headings, notes with malformed heading nesting). Chunk sizes will be uneven by design, which means downstream context-budget management (Section 11.4) has to handle variable-size chunks rather than assuming uniform size.

## Conditions That Would Justify Revisiting

- Evaluation (Section 15) shows heading-based chunks are frequently too large or too small for good retrieval precision, and a different chunk-size range (Section 21, open design question) performs meaningfully better even after respecting heading boundaries.
- A significant portion of vault notes turn out to have poor or missing heading structure, making heading-aware chunking degrade to fixed-size chunking anyway for those files.
