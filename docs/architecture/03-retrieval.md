# Retrieval Pipeline

See `docs/adr/0004-hybrid-retrieval.md` for why hybrid (not semantic-only) was chosen.

## Query normalization

Queries are terse shorthand typed under time pressure. Start with deterministic normalization — no extra LLM call for this in V1.

Example glossary:

```text
tf         -> terraform
k8s        -> kubernetes
sm         -> secrets manager
cw         -> cloudwatch
bluegreen  -> blue green deployment
gha        -> github actions
```

Normalization should also:

- Lowercase only for search while preserving the original query for display.
- Normalize punctuation/whitespace.
- Expand known project aliases.
- Preserve exact technical tokens and hostnames — do not over-normalize these away.
- Detect likely response mode (definition, comparison, troubleshooting, personal example).

Only add LLM-based query rewriting if the evaluation harness demonstrates a meaningful improvement over deterministic normalization. Don't add it speculatively.

## Hybrid retrieval

```text
Normalized query
       |
       +--> Full-text search: top 20
       |
       +--> Vector search: top 20
                         |
                         v
              Merge and de-duplicate
                         |
                         v
                Rank fusion (reciprocal rank fusion)
                         |
                         v
                 Candidate set: 10-15
                         |
                         v
                Optional reranking (NOT in V1 — see below)
                         |
                         v
                 Final context: 4-6 chunks
```

Semantic search handles concepts, incomplete phrasing, synonyms. Full-text search handles exact service names, acronyms, commands, repo names, VM names. Neither alone covers both failure modes this tool will actually hit.

Reciprocal rank fusion (RRF) is the first combination method because full-text relevance scores and cosine similarity scores aren't on the same scale — RRF works off rank position instead of requiring calibrated scores.

## Reranking — do not build in the first functional slice

Add a cross-encoder reranker only when:

- The correct note often appears in the candidate set but ranks too low.
- Evaluation shows a measurable gain in Recall@5, MRR, or source quality.
- Added latency stays acceptable.

This is a "measure before adding complexity" case — see CLAUDE.md principle 6.

## Context selection

The final context builder should:

- Prefer diverse evidence over several adjacent chunks saying the same thing.
- Include heading and path metadata with each chunk.
- Stay within the model's context budget.
- Prioritize personal project evidence when the query asks about experience.
- Retain exact source identifiers outside the model-generated text (never let the model invent or restate a source path — the backend resolves chunk IDs to paths/headings/lines, always).

## Phase 2 exit condition

Shorthand queries consistently retrieve the expected sample notes — measured against the evaluation fixtures in `docs/architecture/07-evaluation.md`, not by eyeballing a few examples.
