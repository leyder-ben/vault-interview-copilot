# Evaluation Strategy

Build this harness early — before extensive prompt tuning. Retrieval quality should be measured, not eyeballed.

## Evaluation dataset

Private dataset for the real vault; sanitized dataset for the public repo / `sample-vault/`.

```yaml
- id: terraform-drift-001
  query: "terraform drift prod"
  expected_notes:
    - "Interview Prep/Terraform.md"
    - "Projects/Whetstone/Infrastructure.md"
  expected_concepts:
    - remote state
    - terraform plan
    - manual changes
    - reconciliation
  expected_personal_project:
    - Whetstone

- id: environments-001
  query: "why use staging"
  expected_notes:
    - "Interview Prep/Environments.md"
```

A real fixture set exists, built from real mock-interview questions — originally drafted in the vault note `Evaluation-Fixtures-Draft.md`, now converted into `evaluation/datasets/private/mock-interview-fixtures.yaml` (20 fixtures, gitignored — real project names, not for the public repo). A small sanitized subset covering the same fixture categories against `sample-vault/`'s fictional Meridian content lives at `evaluation/datasets/sample-vault/meridian-fixtures.yaml` (committed, 6 fixtures — sample-vault only has 7 indexable notes, so this isn't padded to match the private set 1:1). Don't invent fixture examples when real ones already exist.

## Retrieval metrics

- Recall@5, Recall@10
- Mean reciprocal rank (MRR)
- Exact source-note match
- Correct project-example match
- Duplicate-context rate
- Retrieval latency p50 and p95

## Generation metrics

- Citation validity
- Unsupported first-person claim rate
- Speakability rating
- Concept coverage
- Answer length
- Generation latency p50 and p95
- Abstention quality when evidence is missing

## Portfolio benchmarking

README should eventually include measured (not invented) improvements, e.g.: "Hybrid retrieval improved Recall@5 from X% to Y% on N shorthand DevOps interview queries while keeping p95 retrieval latency below Z ms." Record methodology, hardware, model versions, dataset size, limitations. Never publish a number that wasn't actually measured.

## Open design questions to test, not decide by instinct

- Which embedding model performs best on Ben's technical shorthand and personal project notes?
- How much heading/metadata context should be embedded alongside chunk text?
- What chunk-size range balances conceptual completeness vs. retrieval precision?
- Does RRF outperform a weighted combined score on the eval set?
- When does a cross-encoder reranker earn its latency cost?
- Should wikilink neighbors influence ranking?
- How should recent session logs be weighted vs. canonical architecture docs?
- How should contradictory/outdated notes be identified?
- Which local generation model produces the best speakable answers on available hardware?
- At what point should the system stream partial answer text?

These don't block Phase 0-1 work. They get tested once the harness exists.
