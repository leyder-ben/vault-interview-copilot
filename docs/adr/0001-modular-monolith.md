# ADR-001: Modular Monolith Instead of Microservices

**Status:** Accepted
**Date:** 2026-07-15

## Context

This is a single-user, local-first tool. One person (Ben) runs it on his own hardware to pull grounded answers out of his own Obsidian vault during his own interviews. There is no second team, no separate deploy cadence for different pieces, no uptime SLA, and no scaling problem to solve — the entire "load" is one person typing shorthand queries during a live conversation.

The natural pieces of the system are still real: ingestion (scanning and parsing the vault), retrieval (keyword + vector search), generation (prompt building and calling the model), and providers (swappable LLM/embedding backends). The question isn't whether those boundaries exist — it's whether they need to be separate deployable services or can live as modules inside one application.

## Decision

Build one FastAPI application with clear internal module boundaries: `ingestion/`, `retrieval/`, `generation/`, `providers/`, `db/`. No service-to-service network calls, no separate deploy for each piece, one `docker compose up` starts the whole thing.

## Alternatives Considered

**Microservices** (separate ingestion service, retrieval service, generation service, each with its own API): rejected. This buys you independent scaling and independent deploys — neither of which matters here. What it costs is real: network calls where a function call would do, service discovery, more Docker Compose complexity, more failure modes to debug, and more surface area before there's a single working query. On a two-truck operation, you don't run two separate dispatch offices that have to radio each other — one dispatcher with clear areas of responsibility gets the job done faster and with less that can go wrong between them.

## Consequences

**Good:** Faster to build, easier to debug (one process, one log stream, one stack trace instead of tracing a request across service boundaries), no premature infrastructure. Module boundaries are still real in the code, so if a piece genuinely needs to become its own service later, the seams are already there.

**Trade-off:** If this tool ever needs to serve multiple users concurrently or scale a specific piece independently (e.g., embedding generation becomes a bottleneck under real concurrent load), the monolith would need to be split. That's an explicit non-goal for V1 and V2 per the brief, so it's an acceptable trade.

## Conditions That Would Justify Revisiting

- The tool moves from single-user/local to hosted/multi-user (a genuinely different project).
- One module (most likely embedding generation or LLM calls) becomes a measured bottleneck that specifically needs independent scaling — not a guess, a measurement.
