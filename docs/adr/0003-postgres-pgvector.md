# ADR-003: PostgreSQL + pgvector Instead of a Dedicated Vector Database

**Status:** Accepted
**Date:** 2026-07-15

## Context

The system needs more than vector search. It needs relational metadata (notes, chunks, frontmatter, tags, wikilinks), full-text search (for exact technical tokens — service names, acronyms, repo names, VM names — that semantic search alone tends to miss), vector search (for concepts, synonyms, and incomplete phrasing), file lifecycle tracking (index runs, content hashes, incremental updates), and query/evaluation logging (Section 15's Recall@5, MRR, and benchmarking all depend on this data existing somewhere queryable).

A dedicated vector database (Pinecone, Weaviate, Qdrant, Chroma, etc.) is very good at one of those five things and would need to be paired with a second relational database to cover the rest — meaning two databases to keep in sync, two things that can drift, two connections to manage in a single-user local tool.

## Decision

Use PostgreSQL with the pgvector extension as the single data store — relational metadata, full-text search (Postgres's built-in `tsvector`/`tsquery`), and vector embeddings all live in the same database, often the same tables.

## Alternatives Considered

**Dedicated vector database + separate relational database:** rejected. Splitting these means every ingestion run and every query touches two systems instead of one, and keeping notes/chunks metadata in sync with a separate vector store's index is exactly the kind of drift-prone plumbing this project doesn't need for a single local vault. It's like running two separate parts trucks to stock one shop — the parts eventually match up, but only after somebody spends time reconciling two inventories that didn't need to be separate in the first place.

**Dedicated vector database alone, no relational DB:** rejected — doesn't cover full-text search, structured metadata, or query logging without significant workarounds.

## Consequences

**Good:** One database, one connection, one backup, one place to write a query that joins across notes/chunks/embeddings/query_runs. Postgres's full-text search is genuinely good, not a compromise — hybrid retrieval (ADR-004) depends on having solid full-text search sitting right next to the vector search, and pgvector makes that trivial in a single query.

**Trade-off:** pgvector's exact (brute-force) vector search doesn't scale to the same size or speed as a purpose-built vector database under heavy load. For a personal vault of a few hundred to a few thousand notes, this is not a real constraint (Section 16: don't add HNSW until exact search is a measured bottleneck).

## Conditions That Would Justify Revisiting

- The vault grows large enough (many tens of thousands of chunks) that exact vector search is a measured latency problem even after adding HNSW indexing within pgvector itself.
- The project moves to a genuinely different scale (hosted, multi-vault, multi-user) where a dedicated vector database's horizontal scaling actually matters.
