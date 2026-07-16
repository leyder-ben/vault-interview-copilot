# ADR-004: Hybrid Retrieval Instead of Semantic-Only Retrieval

**Status:** Accepted
**Date:** 2026-07-15

## Context

Queries into this system are deliberately terse — shorthand typed under time pressure mid-interview ("terraform drift prod," "helm scaling," "jenkins oidc secrets"). Semantic (vector) search is good at matching concepts, synonyms, and incomplete phrasing, but it can miss or under-rank exact technical tokens: specific service names, acronyms, repo names, VM names, command names. A query for "pve-dain" or "OIDC" needs an exact-token hit, not just a conceptual neighbor. Keyword (full-text) search is good at exactly that, but weak on paraphrase and incomplete phrasing — the flip side of the same coin.

Neither approach alone covers both failure modes this tool will actually hit in practice.

## Decision

Run full-text search and vector search in parallel for every query, merge and de-duplicate the results, and combine the ranked lists with reciprocal rank fusion (RRF) rather than relying on either signal alone. Candidate set gets narrowed from ~20 results per method down to 10-15 combined, then to a final context of 4-6 chunks.

## Alternatives Considered

**Semantic-only retrieval:** rejected. This is the default approach in most RAG tutorials, but it's a bad fit for this specific query pattern — shorthand technical fragments with exact tokens (VM names, acronyms, repo names) that vector embeddings don't reliably preserve at the token level.

**Keyword-only retrieval:** rejected. Handles exact tokens well but fails on paraphrase, synonyms, and the "I know what I mean but can't remember the exact term" case that's common when recalling something under interview pressure.

**A learned re-ranking/weighted score combination instead of RRF:** deferred, not rejected outright. RRF was chosen as the first combination method because it doesn't require both search methods to produce directly comparable scores — full-text relevance scores and cosine similarity scores aren't on the same scale, and RRF sidesteps that by working off rank position instead of raw score. A weighted combined score is one of the open design questions (Section 21) to test against the evaluation harness once one exists, not decide by instinct upfront.

This mirrors running two different diagnostic tools on the same problem instead of trusting one gauge — a multimeter tells you voltage, a clamp meter tells you current, and you don't skip one just because the other is usually right.

## Consequences

**Good:** Covers both the "exact term I can't quite phrase" case and the "exact term I remember perfectly" case without picking one at the expense of the other. RRF is simple, cheap, and doesn't require score calibration between two different search systems.

**Trade-off:** More moving parts than a single retrieval method — two searches to run and merge instead of one, and a fusion step to get right. Reranking (a cross-encoder pass on top of the fused candidates) is explicitly deferred until the evaluation harness shows it's needed (Section 11.3) — this ADR covers the two-method fusion, not reranking.

## Conditions That Would Justify Revisiting

- The evaluation harness (Section 15) shows one method alone would have performed just as well on real query patterns — unlikely given the shorthand-heavy query style this tool targets, but it should be measured, not assumed.
- RRF is measurably outperformed by a weighted score combination on the evaluation set (Section 21, open design question).
