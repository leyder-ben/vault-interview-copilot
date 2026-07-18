# Phase 2: Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the retrieval pipeline (normalization, full-text search, vector search, RRF fusion, a no-LLM debug endpoint) and an evaluation harness that proves shorthand queries consistently retrieve the expected `sample-vault` notes.

**Architecture:** New `app/retrieval/` module (normalize → fulltext + vector search → fusion) orchestrated by `search()`, exposed read-only via `GET /api/debug/retrieve`. A new `app/evaluation/` module scores `search()` against fixture YAML files (Recall@5/@10, MRR, exact-match, latency), with a CLI entry point mirroring Phase 1's `app.ingestion.cli` pattern. Full design: `docs/superpowers/specs/2026-07-18-phase-2-retrieval-design.md`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pgvector, PyYAML (existing stack from Phase 0/1 — no new dependencies).

## Global Constraints

- RRF constant `k = 60` (standard default), applied as `score = Σ 1/(k + rank)` across whichever ranked lists a chunk appears in.
- Full-text and vector search run **sequentially** (call one, then the other) — no async/threading. State this plainly in code comments; don't imply future concurrent work that isn't planned.
- Full-text search uses `websearch_to_tsquery('english', ...)`, not `to_tsquery`/`plainto_tsquery` — chosen because the harness scores full natural-language interviewer phrasing, not just shorthand fragments.
- Vector search is a plain sequential scan (`ORDER BY embedding <=> :query_vector`) — no HNSW/ivfflat index, per the locked "no ANN index until evaluation shows a bottleneck" decision.
- `embedding_provider.embed_batch([normalized_query])[0]` is the verified way to embed a single query — confirmed compatible with `apps/api/app/ingestion/embeddings.py`'s actual `embed_batch(texts: list[str]) -> list[list[float]]` signature.
- Phase 2's evaluation harness computes exactly: Recall@5, Recall@10, MRR, exact source-note match, retrieval latency p50/p95. It does **not** compute "correct project-example match" or concept-coverage metrics — those require an LLM-generated answer or project-per-note metadata that doesn't exist yet, deferred to Phase 3.
- The exit-condition Recall@5 threshold is not decided in advance — it is measured from a real harness run and locked in at that value (see Task 12). If the first real run is below 100%: investigating and fixing *retrieval code* once, then re-running once, is allowed. Editing fixture content (`expected_notes`, wording, or dropping a fixture) to raise the score is **not** allowed under any circumstance.
- `GET /api/debug/retrieve` is unauthenticated (single-user, local-only tool) — this is conditional on staying localhost-only; revisit before any non-localhost exposure (Phase 4+). It does not write to `query_runs`.
- Ruff config (`line-length = 100`, `target-version = "py312"`, lint rules `["E", "F", "I", "UP"]`) applies to all new code.
- `apps/api/tests/conftest.py`'s `db_session` fixture (real Postgres, migrated to head, truncated between tests) is the existing pattern for all DB-touching tests — reuse it, don't build a new one.
- `apps/api/tests/ingestion/fakes.py`'s `FakeEmbeddingProvider`/`FailingEmbeddingProvider` are reusable as-is for retrieval/evaluation tests — don't duplicate them.

---

### Task 1: `chunks.search_vector` generated-column migration

**Files:**
- Create: `apps/api/alembic/versions/0002_chunks_search_vector_generated.py`
- Modify: `apps/api/app/db/models.py`
- Test: `apps/api/tests/test_migrations.py` (append)

**Interfaces:**
- Consumes: nothing from earlier tasks (this is the first Phase 2 task).
- Produces: `chunks.search_vector` becomes a Postgres `GENERATED ALWAYS AS (to_tsvector('english', content_with_context)) STORED` column, automatically populated on every insert/update. Consumed by Task 3 (full-text search) and Task 4/Task 12 (evaluation harness, indirectly).

- [x] **Step 1: Write the failing test — migration backfills pre-existing rows**

This test proves the exact mechanic verified manually during design: downgrade to `0001`, insert a chunk row via raw SQL (bypassing the ORM, since the ORM model will already declare the future generated column), upgrade to `0002`, assert `search_vector` was backfilled correctly for that pre-existing row — not just for rows inserted after the migration.

Append to `apps/api/tests/test_migrations.py`:

```python
def test_0002_backfills_search_vector_for_preexisting_chunks(db_engine):
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, "0001")

    # This test uses db_engine, not db_session — db_session's teardown
    # truncates tables automatically, db_engine's does not. Since this test
    # inserts rows via raw SQL (bypassing the ORM, deliberately — see Step 1's
    # explanation), it must clean up after itself in a finally block, or a
    # stray "Note-A.md" row leaks into whichever test runs next.
    try:
        with db_engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO notes (vault_path, filename, title, content_hash, modified_at)
                    VALUES ('Note-A.md', 'Note-A.md', 'Note A', 'hash-a', now())
                    """
                )
            )
            note_id = conn.execute(sa.text("SELECT id FROM notes WHERE vault_path = 'Note-A.md'")).scalar_one()
            conn.execute(
                sa.text(
                    """
                    INSERT INTO chunks
                        (note_id, chunk_index, start_line, end_line, content,
                         content_with_context, content_hash)
                    VALUES
                        (:note_id, 0, 1, 3, 'Terraform drift happens when state diverges.',
                         'Document: Note A\nTerraform drift happens when state diverges.', 'chash-a')
                    """
                ),
                {"note_id": note_id},
            )

        command.upgrade(alembic_cfg, "0002")

        with db_engine.begin() as conn:
            row = conn.execute(
                sa.text("SELECT search_vector FROM chunks WHERE content_hash = 'chash-a'")
            ).one()
            search_vector = row[0]

        assert search_vector is not None
        assert "terraform" in search_vector
        assert "drift" in search_vector
    finally:
        # command.upgrade must run here too, not just the truncate: if the
        # raw-SQL insert above throws, execution never reaches the upgrade
        # call in the try block, and the schema is left stranded at
        # revision 0001 — every later test using db_session assumes head
        # schema (including the generated search_vector column) and would
        # fail with a confusing, unrelated-looking error. upgrade is a
        # no-op if already at head, so this is always safe to call.
        command.upgrade(alembic_cfg, "0002")
        with db_engine.begin() as conn:
            conn.execute(
                sa.text("TRUNCATE notes, chunks, note_links, index_runs, query_runs RESTART IDENTITY CASCADE")
            )
```

`apps/api/tests/test_migrations.py` already imports `sqlalchemy as sa` and uses a `db_engine` fixture per the existing file (Phase 0) — check the existing file's imports and top-of-file fixtures before appending, don't duplicate an `import sqlalchemy as sa` line if one already exists.

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/test_migrations.py::test_0002_backfills_search_vector_for_preexisting_chunks -v`
Expected: FAIL — `alembic.util.exc.CommandError` or similar, because revision `0002` doesn't exist yet.

- [x] **Step 3: Write the migration**

Create `apps/api/alembic/versions/0002_chunks_search_vector_generated.py`:

```python
"""chunks.search_vector as a generated column

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres has no ALTER COLUMN ... ADD GENERATED for stored generated
    # columns (that form is exclusive to GENERATED ... AS IDENTITY) — the
    # only way to convert an existing plain column is drop-and-recreate.
    # This whole function runs as one Alembic transaction (see env.py's
    # context.begin_transaction()); if any step fails, Postgres rolls back
    # the entire migration, so chunks.search_vector is never left dropped
    # with no replacement.
    op.drop_index("ix_chunks_search_vector", table_name="chunks")
    op.drop_column("chunks", "search_vector")
    op.add_column(
        "chunks",
        sa.Column(
            "search_vector",
            TSVECTOR(),
            sa.Computed("to_tsvector('english', content_with_context)", persisted=True),
        ),
    )
    op.create_index("ix_chunks_search_vector", "chunks", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_search_vector", table_name="chunks")
    op.drop_column("chunks", "search_vector")
    op.add_column("chunks", sa.Column("search_vector", TSVECTOR(), nullable=True))
    op.create_index("ix_chunks_search_vector", "chunks", ["search_vector"], postgresql_using="gin")
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/test_migrations.py -v`
Expected: PASS (all tests in the file, old and new).

- [x] **Step 5: Update the SQLAlchemy model to match**

Modify `apps/api/app/db/models.py`. Add the import and change the `search_vector` column definition:

```python
from sqlalchemy import Computed  # add to the existing sqlalchemy import line
```

Change:

```python
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
```

to:

```python
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', content_with_context)", persisted=True)
    )
```

- [x] **Step 6: Run the full test suite to check for regressions**

Run: `cd apps/api && pytest -v`
Expected: PASS (all tests, old and new). This confirms Phase 1's indexer — which never sets `search_vector` explicitly — still works unchanged, since Postgres now computes it automatically.

- [x] **Step 7: Commit**

```bash
git add apps/api/alembic/versions/0002_chunks_search_vector_generated.py apps/api/app/db/models.py apps/api/tests/test_migrations.py
git commit -m "feat(retrieval): make chunks.search_vector a Postgres-generated column"
```

---

### Task 2: Query normalization

**Files:**
- Create: `apps/api/app/retrieval/__init__.py`
- Create: `apps/api/app/retrieval/normalize.py`
- Create: `apps/api/tests/retrieval/__init__.py`
- Test: `apps/api/tests/retrieval/test_normalize.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ALIASES: dict[str, str]`, `normalize_query(raw: str) -> str`. Consumed by `search()` (Task 6).

- [x] **Step 1: Write the failing test**

Create `apps/api/app/retrieval/__init__.py` (empty) and `apps/api/tests/retrieval/__init__.py` (empty).

Create `apps/api/tests/retrieval/test_normalize.py`:

```python
from app.retrieval.normalize import normalize_query


def test_lowercases_query():
    assert normalize_query("Terraform Drift") == "terraform drift"


def test_expands_known_alias():
    assert normalize_query("tf drift") == "terraform drift"


def test_expands_alias_regardless_of_case():
    assert normalize_query("K8S scaling") == "kubernetes scaling"


def test_does_not_expand_alias_substring_inside_another_word():
    # "tf" must not match inside "artful" — whole-token matching only
    assert normalize_query("artful dodger") == "artful dodger"


def test_normalizes_punctuation_and_whitespace():
    assert normalize_query("terraform,   drift!!") == "terraform drift"


def test_preserves_exact_technical_tokens_not_in_glossary():
    assert normalize_query("pve-dain OIDC") == "pve-dain oidc"
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/retrieval/test_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retrieval.normalize'`

- [x] **Step 3: Write the implementation**

Create `apps/api/app/retrieval/normalize.py`:

```python
from __future__ import annotations

import re

ALIASES: dict[str, str] = {
    "tf": "terraform",
    "k8s": "kubernetes",
    "sm": "secrets manager",
    "cw": "cloudwatch",
    "bluegreen": "blue green deployment",
    "gha": "github actions",
}

_PUNCTUATION_RE = re.compile(r"[^\w\s-]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_query(raw: str) -> str:
    lowered = raw.lower()
    no_punctuation = _PUNCTUATION_RE.sub("", lowered)
    collapsed = _WHITESPACE_RE.sub(" ", no_punctuation).strip()

    tokens = collapsed.split(" ")
    expanded = [ALIASES.get(token, token) for token in tokens]
    return " ".join(expanded)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/retrieval/test_normalize.py -v`
Expected: PASS (6 tests)

- [x] **Step 5: Commit**

```bash
git add apps/api/app/retrieval/__init__.py apps/api/app/retrieval/normalize.py apps/api/tests/retrieval/__init__.py apps/api/tests/retrieval/test_normalize.py
git commit -m "feat(retrieval): add query normalization with alias glossary"
```

---

### Task 3: Full-text search

**Files:**
- Create: `apps/api/app/retrieval/fulltext.py`
- Test: `apps/api/tests/retrieval/test_fulltext.py`

**Interfaces:**
- Consumes: `Chunk`, `Note` models (`app.db.models`, already exist; `Chunk.search_vector` is now a generated column per Task 1).
- Produces: `ScoredChunk(chunk_id: int, vault_path: str, heading_path: str | None, rank: int, score: float)`, `search_fulltext(session: Session, query: str, limit: int = 20) -> list[ScoredChunk]`. `ScoredChunk` is consumed by Task 4 (vector search, same shape), Task 5 (fusion), Task 6 (search orchestration), and Task 7 (debug endpoint).

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/retrieval/test_fulltext.py`:

```python
from datetime import datetime, timezone

from app.db.models import Chunk, Note
from app.retrieval.fulltext import search_fulltext


def _make_note_with_chunk(session, *, vault_path, heading_path, content_with_context):
    note = Note(
        vault_path=vault_path,
        filename=vault_path.rsplit("/", 1)[-1],
        title=vault_path,
        content_hash=f"hash-{vault_path}",
        modified_at=datetime.now(timezone.utc),
    )
    session.add(note)
    session.flush()
    chunk = Chunk(
        note_id=note.id,
        heading_path=heading_path,
        chunk_index=0,
        start_line=1,
        end_line=5,
        content=content_with_context,
        content_with_context=content_with_context,
        content_hash=f"chash-{vault_path}",
    )
    session.add(chunk)
    session.flush()
    return note, chunk


def test_search_fulltext_ranks_exact_term_match_first(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="Terraform.md",
        heading_path="Drift Management",
        content_with_context="Document: Terraform\nState drift happens when infrastructure diverges.",
    )
    _make_note_with_chunk(
        db_session,
        vault_path="Kubernetes.md",
        heading_path="Scaling",
        content_with_context="Document: Kubernetes\nPod scaling is unrelated to infrastructure state.",
    )
    db_session.commit()

    results = search_fulltext(db_session, "terraform drift", limit=20)

    assert len(results) >= 1
    assert results[0].vault_path == "Terraform.md"
    assert results[0].rank == 1


def test_search_fulltext_returns_empty_list_for_no_matches(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="Terraform.md",
        heading_path="Drift Management",
        content_with_context="Document: Terraform\nState drift happens when infrastructure diverges.",
    )
    db_session.commit()

    results = search_fulltext(db_session, "kubernetes helm charts", limit=20)

    assert results == []


def test_search_fulltext_respects_limit(db_session):
    for i in range(5):
        _make_note_with_chunk(
            db_session,
            vault_path=f"Note-{i}.md",
            heading_path=None,
            content_with_context=f"Document: Note {i}\nTerraform drift note number {i}.",
        )
    db_session.commit()

    results = search_fulltext(db_session, "terraform drift", limit=3)

    assert len(results) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/retrieval/test_fulltext.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retrieval.fulltext'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/retrieval/fulltext.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import Chunk, Note


@dataclass
class ScoredChunk:
    chunk_id: int
    vault_path: str
    heading_path: str | None
    rank: int
    score: float


def search_fulltext(session: Session, query: str, limit: int = 20) -> list[ScoredChunk]:
    tsquery = sa.func.websearch_to_tsquery("english", query)
    rank_expr = sa.func.ts_rank(Chunk.search_vector, tsquery).label("score")

    rows = (
        session.query(Chunk.id, Note.vault_path, Chunk.heading_path, rank_expr)
        .join(Note, Chunk.note_id == Note.id)
        .filter(Chunk.search_vector.op("@@")(tsquery))
        .order_by(rank_expr.desc())
        .limit(limit)
        .all()
    )

    return [
        ScoredChunk(chunk_id=chunk_id, vault_path=vault_path, heading_path=heading_path, rank=i + 1, score=float(score))
        for i, (chunk_id, vault_path, heading_path, score) in enumerate(rows)
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/retrieval/test_fulltext.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/retrieval/fulltext.py apps/api/tests/retrieval/test_fulltext.py
git commit -m "feat(retrieval): add full-text search via websearch_to_tsquery"
```

---

### Task 4: Vector search

**Files:**
- Create: `apps/api/app/retrieval/vector.py`
- Test: `apps/api/tests/retrieval/test_vector.py`

**Interfaces:**
- Consumes: `ScoredChunk` (Task 3, same dataclass reused — do not redefine it). `Chunk.embedding` (`pgvector.sqlalchemy.Vector(768)`, already exists from Phase 0/1).
- Produces: `search_vector_similarity(session: Session, query_embedding: list[float], limit: int = 20) -> list[ScoredChunk]`. Named `search_vector_similarity`, not `search_vector`, to avoid colliding with the `Chunk.search_vector` column/attribute name used throughout the codebase. Consumed by Task 5 (fusion) and Task 6 (search orchestration).

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/retrieval/test_vector.py`:

```python
from datetime import datetime, timezone

from app.db.models import Chunk, Note
from app.retrieval.vector import search_vector_similarity

DIM = 768


def _unit_vector(hot_index: int) -> list[float]:
    vector = [0.0] * DIM
    vector[hot_index] = 1.0
    return vector


def _make_note_with_chunk(session, *, vault_path, heading_path, embedding):
    note = Note(
        vault_path=vault_path,
        filename=vault_path.rsplit("/", 1)[-1],
        title=vault_path,
        content_hash=f"hash-{vault_path}",
        modified_at=datetime.now(timezone.utc),
    )
    session.add(note)
    session.flush()
    chunk = Chunk(
        note_id=note.id,
        heading_path=heading_path,
        chunk_index=0,
        start_line=1,
        end_line=5,
        content="content",
        content_with_context="Document: x\ncontent",
        content_hash=f"chash-{vault_path}",
        embedding=embedding,
    )
    session.add(chunk)
    session.flush()
    return note, chunk


def test_search_vector_similarity_ranks_closest_embedding_first(db_session):
    _make_note_with_chunk(db_session, vault_path="Close.md", heading_path=None, embedding=_unit_vector(0))
    _make_note_with_chunk(db_session, vault_path="Far.md", heading_path=None, embedding=_unit_vector(500))
    db_session.commit()

    query_embedding = _unit_vector(0)
    results = search_vector_similarity(db_session, query_embedding, limit=20)

    assert results[0].vault_path == "Close.md"
    assert results[0].rank == 1
    assert results[-1].vault_path == "Far.md"


def test_search_vector_similarity_respects_limit(db_session):
    for i in range(5):
        _make_note_with_chunk(
            db_session, vault_path=f"Note-{i}.md", heading_path=None, embedding=_unit_vector(i)
        )
    db_session.commit()

    results = search_vector_similarity(db_session, _unit_vector(0), limit=3)

    assert len(results) == 3


def test_search_vector_similarity_excludes_chunks_with_no_embedding(db_session):
    _make_note_with_chunk(db_session, vault_path="HasEmbedding.md", heading_path=None, embedding=_unit_vector(0))
    note = Note(
        vault_path="NoEmbedding.md",
        filename="NoEmbedding.md",
        title="NoEmbedding.md",
        content_hash="hash-no-embedding",
        modified_at=datetime.now(timezone.utc),
    )
    db_session.add(note)
    db_session.flush()
    db_session.add(
        Chunk(
            note_id=note.id,
            chunk_index=0,
            start_line=1,
            end_line=5,
            content="content",
            content_with_context="Document: x\ncontent",
            content_hash="chash-no-embedding",
            embedding=None,
        )
    )
    db_session.commit()

    results = search_vector_similarity(db_session, _unit_vector(0), limit=20)

    assert {r.vault_path for r in results} == {"HasEmbedding.md"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/retrieval/test_vector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retrieval.vector'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/retrieval/vector.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Chunk, Note
from app.retrieval.fulltext import ScoredChunk


def search_vector_similarity(
    session: Session, query_embedding: list[float], limit: int = 20
) -> list[ScoredChunk]:
    distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")

    rows = (
        session.query(Chunk.id, Note.vault_path, Chunk.heading_path, distance_expr)
        .join(Note, Chunk.note_id == Note.id)
        .filter(Chunk.embedding.is_not(None))
        .order_by(distance_expr.asc())
        .limit(limit)
        .all()
    )

    return [
        ScoredChunk(
            chunk_id=chunk_id,
            vault_path=vault_path,
            heading_path=heading_path,
            rank=i + 1,
            score=1.0 - float(distance),
        )
        for i, (chunk_id, vault_path, heading_path, distance) in enumerate(rows)
    ]
```

`score` is `1 - cosine_distance` (i.e. cosine similarity, higher is better) so `ScoredChunk.score` means "higher is better" consistently across both `fulltext.py` and `vector.py` — important for Task 5's fusion and Task 7's debug output to stay consistent.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/retrieval/test_vector.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/retrieval/vector.py apps/api/tests/retrieval/test_vector.py
git commit -m "feat(retrieval): add pgvector cosine-similarity search"
```

---

### Task 5: Reciprocal rank fusion

**Files:**
- Create: `apps/api/app/retrieval/fusion.py`
- Test: `apps/api/tests/retrieval/test_fusion.py`

**Interfaces:**
- Consumes: `ScoredChunk` (Task 3).
- Produces: `FusedResult(chunk_id: int, vault_path: str, heading_path: str | None, fused_rank: int, rrf_score: float, fulltext_rank: int | None, vector_rank: int | None)`, `reciprocal_rank_fusion(fulltext_results: list[ScoredChunk], vector_results: list[ScoredChunk], k: int = 60) -> list[FusedResult]`. Consumed by Task 6 (search orchestration) and Task 7 (debug endpoint).

This is a pure function — no database, no fixtures beyond hand-built `ScoredChunk` lists.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/retrieval/test_fusion.py`:

```python
from app.retrieval.fulltext import ScoredChunk
from app.retrieval.fusion import reciprocal_rank_fusion


def test_chunk_in_both_lists_ranks_above_chunk_in_one_list():
    fulltext = [
        ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=1, score=0.9),
        ScoredChunk(chunk_id=2, vault_path="B.md", heading_path=None, rank=2, score=0.5),
    ]
    vector = [
        ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=1, score=0.95),
    ]

    fused = reciprocal_rank_fusion(fulltext, vector, k=60)

    assert fused[0].chunk_id == 1
    assert fused[0].fulltext_rank == 1
    assert fused[0].vector_rank == 1
    assert fused[1].chunk_id == 2
    assert fused[1].fulltext_rank == 2
    assert fused[1].vector_rank is None


def test_rrf_score_matches_formula():
    fulltext = [ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=1, score=0.9)]
    vector = [ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=3, score=0.7)]

    fused = reciprocal_rank_fusion(fulltext, vector, k=60)

    expected_score = 1 / (60 + 1) + 1 / (60 + 3)
    assert fused[0].rrf_score == expected_score


def test_fused_rank_is_sequential_starting_at_one():
    fulltext = [
        ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=1, score=0.9),
        ScoredChunk(chunk_id=2, vault_path="B.md", heading_path=None, rank=2, score=0.5),
    ]
    fused = reciprocal_rank_fusion(fulltext, [], k=60)

    assert [r.fused_rank for r in fused] == [1, 2]


def test_empty_inputs_produce_empty_output():
    assert reciprocal_rank_fusion([], [], k=60) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/retrieval/test_fusion.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retrieval.fusion'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/retrieval/fusion.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.fulltext import ScoredChunk


@dataclass
class FusedResult:
    chunk_id: int
    vault_path: str
    heading_path: str | None
    fused_rank: int
    rrf_score: float
    fulltext_rank: int | None
    vector_rank: int | None


def reciprocal_rank_fusion(
    fulltext_results: list[ScoredChunk], vector_results: list[ScoredChunk], k: int = 60
) -> list[FusedResult]:
    by_chunk: dict[int, dict] = {}

    for chunk in fulltext_results:
        by_chunk[chunk.chunk_id] = {
            "vault_path": chunk.vault_path,
            "heading_path": chunk.heading_path,
            "fulltext_rank": chunk.rank,
            "vector_rank": None,
        }

    for chunk in vector_results:
        entry = by_chunk.setdefault(
            chunk.chunk_id,
            {"vault_path": chunk.vault_path, "heading_path": chunk.heading_path, "fulltext_rank": None, "vector_rank": None},
        )
        entry["vector_rank"] = chunk.rank

    scored = []
    for chunk_id, entry in by_chunk.items():
        score = 0.0
        if entry["fulltext_rank"] is not None:
            score += 1 / (k + entry["fulltext_rank"])
        if entry["vector_rank"] is not None:
            score += 1 / (k + entry["vector_rank"])
        scored.append((chunk_id, entry, score))

    scored.sort(key=lambda item: item[2], reverse=True)

    return [
        FusedResult(
            chunk_id=chunk_id,
            vault_path=entry["vault_path"],
            heading_path=entry["heading_path"],
            fused_rank=i + 1,
            rrf_score=score,
            fulltext_rank=entry["fulltext_rank"],
            vector_rank=entry["vector_rank"],
        )
        for i, (chunk_id, entry, score) in enumerate(scored)
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/retrieval/test_fusion.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/retrieval/fusion.py apps/api/tests/retrieval/test_fusion.py
git commit -m "feat(retrieval): add reciprocal rank fusion"
```

---

### Task 6: Search orchestration

**Files:**
- Create: `apps/api/app/retrieval/search.py`
- Test: `apps/api/tests/retrieval/test_search.py`

**Interfaces:**
- Consumes: `normalize_query` (Task 2), `search_fulltext` (Task 3), `search_vector_similarity` (Task 4), `reciprocal_rank_fusion` (Task 5), `EmbeddingProvider` protocol (`app.ingestion.embeddings`, already exists — `embed_batch(texts: list[str]) -> list[list[float]]`).
- Produces: `RetrievalResult(raw_query: str, normalized_query: str, fulltext_results: list[ScoredChunk], vector_results: list[ScoredChunk], fused_results: list[FusedResult], timing_ms: dict[str, float])`, `search(session: Session, embedding_provider: EmbeddingProvider, raw_query: str) -> RetrievalResult`. Consumed by Task 7 (debug endpoint) and Task 9 (evaluation runner).

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/retrieval/test_search.py`:

```python
from datetime import datetime, timezone

from app.db.models import Chunk, Note
from app.retrieval.search import search
from tests.ingestion.fakes import FakeEmbeddingProvider


def _make_note_with_chunk(session, *, vault_path, content_with_context):
    note = Note(
        vault_path=vault_path,
        filename=vault_path.rsplit("/", 1)[-1],
        title=vault_path,
        content_hash=f"hash-{vault_path}",
        modified_at=datetime.now(timezone.utc),
    )
    session.add(note)
    session.flush()
    chunk = Chunk(
        note_id=note.id,
        chunk_index=0,
        start_line=1,
        end_line=5,
        content=content_with_context,
        content_with_context=content_with_context,
        content_hash=f"chash-{vault_path}",
        embedding=FakeEmbeddingProvider().embed_batch([content_with_context])[0],
    )
    session.add(chunk)
    session.flush()
    return note, chunk


def test_search_returns_normalized_query_and_fused_results(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="Terraform.md",
        content_with_context="Document: Terraform\nState drift happens when infrastructure diverges.",
    )
    db_session.commit()

    provider = FakeEmbeddingProvider()
    result = search(db_session, provider, "TF Drift")

    assert result.raw_query == "TF Drift"
    assert result.normalized_query == "terraform drift"
    assert len(result.fused_results) >= 1
    assert result.fused_results[0].vault_path == "Terraform.md"


def test_search_embeds_normalized_query_not_raw_query(db_session):
    _make_note_with_chunk(
        db_session,
        vault_path="Terraform.md",
        content_with_context="Document: Terraform\nState drift happens when infrastructure diverges.",
    )
    db_session.commit()

    provider = FakeEmbeddingProvider()
    search(db_session, provider, "TF Drift")

    assert provider.calls == [["terraform drift"]]


def test_search_populates_timing_ms_keys(db_session):
    provider = FakeEmbeddingProvider()
    result = search(db_session, provider, "anything")

    assert set(result.timing_ms.keys()) == {"fulltext", "vector", "fusion", "total"}
    assert all(isinstance(v, float) for v in result.timing_ms.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/retrieval/test_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.retrieval.search'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/retrieval/search.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ingestion.embeddings import EmbeddingProvider
from app.retrieval.fulltext import ScoredChunk, search_fulltext
from app.retrieval.fusion import FusedResult, reciprocal_rank_fusion
from app.retrieval.normalize import normalize_query
from app.retrieval.vector import search_vector_similarity


@dataclass
class RetrievalResult:
    raw_query: str
    normalized_query: str
    fulltext_results: list[ScoredChunk]
    vector_results: list[ScoredChunk]
    fused_results: list[FusedResult]
    timing_ms: dict[str, float]


def search(session: Session, embedding_provider: EmbeddingProvider, raw_query: str) -> RetrievalResult:
    total_start = time.perf_counter()

    normalized = normalize_query(raw_query)
    query_embedding = embedding_provider.embed_batch([normalized])[0]

    fulltext_start = time.perf_counter()
    fulltext_results = search_fulltext(session, normalized, limit=20)
    fulltext_ms = (time.perf_counter() - fulltext_start) * 1000

    vector_start = time.perf_counter()
    vector_results = search_vector_similarity(session, query_embedding, limit=20)
    vector_ms = (time.perf_counter() - vector_start) * 1000

    fusion_start = time.perf_counter()
    fused_results = reciprocal_rank_fusion(fulltext_results, vector_results, k=60)
    fusion_ms = (time.perf_counter() - fusion_start) * 1000

    total_ms = (time.perf_counter() - total_start) * 1000

    return RetrievalResult(
        raw_query=raw_query,
        normalized_query=normalized,
        fulltext_results=fulltext_results,
        vector_results=vector_results,
        fused_results=fused_results,
        timing_ms={
            "fulltext": fulltext_ms,
            "vector": vector_ms,
            "fusion": fusion_ms,
            "total": total_ms,
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/retrieval/test_search.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/retrieval/search.py apps/api/tests/retrieval/test_search.py
git commit -m "feat(retrieval): add search() orchestrating normalize -> embed -> fulltext + vector -> fusion"
```

---

### Task 7: Debug endpoint

**Files:**
- Create: `apps/api/app/api/retrieval_debug.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_retrieval_debug.py`

**Interfaces:**
- Consumes: `search` (Task 6), `get_db` (`app.api.deps`, already exists), `settings.ollama_workstation_url`/`settings.embedding_model` (`app.core.config`, already exist), `OllamaEmbeddingProvider` (`app.ingestion.embeddings`, already exists).
- Produces: `GET /api/debug/retrieve?q=...` route.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_retrieval_debug.py`:

```python
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.db.models import Chunk, Note
from app.main import app
from tests.ingestion.fakes import FakeEmbeddingProvider


def test_debug_retrieve_returns_full_pipeline_breakdown(db_session, monkeypatch):
    note = Note(
        vault_path="Terraform.md",
        filename="Terraform.md",
        title="Terraform.md",
        content_hash="hash-terraform",
        modified_at=datetime.now(timezone.utc),
    )
    db_session.add(note)
    db_session.flush()
    content = "Document: Terraform\nState drift happens when infrastructure diverges."
    db_session.add(
        Chunk(
            note_id=note.id,
            heading_path="Drift",
            chunk_index=0,
            start_line=1,
            end_line=5,
            content=content,
            content_with_context=content,
            content_hash="chash-terraform",
            embedding=FakeEmbeddingProvider().embed_batch([content])[0],
        )
    )
    db_session.commit()

    import app.api.retrieval_debug as retrieval_debug_module

    monkeypatch.setattr(
        retrieval_debug_module, "OllamaEmbeddingProvider", lambda base_url: FakeEmbeddingProvider()
    )
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.get("/api/debug/retrieve", params={"q": "terraform drift"})
        assert response.status_code == 200
        body = response.json()
        assert body["raw_query"] == "terraform drift"
        assert body["normalized_query"] == "terraform drift"
        assert "fulltext_results" in body
        assert "vector_results" in body
        assert "fused_results" in body
        assert body["fused_results"][0]["vault_path"] == "Terraform.md"
        assert set(body["timing_ms"].keys()) == {"fulltext", "vector", "fusion", "total"}
    finally:
        app.dependency_overrides.clear()


def test_debug_retrieve_requires_q_param(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.get("/api/debug/retrieve")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/test_retrieval_debug.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.retrieval_debug'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/api/retrieval_debug.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.ingestion.embeddings import OllamaEmbeddingProvider
from app.retrieval.search import search

router = APIRouter()


@router.get("/api/debug/retrieve")
def debug_retrieve(q: str, db: Session = Depends(get_db)) -> dict:
    provider = OllamaEmbeddingProvider(base_url=settings.ollama_workstation_url)
    result = search(db, provider, q)

    return {
        "raw_query": result.raw_query,
        "normalized_query": result.normalized_query,
        "fulltext_results": [
            {
                "chunk_id": c.chunk_id,
                "path": c.vault_path,
                "heading": c.heading_path,
                "rank": c.rank,
                "score": c.score,
            }
            for c in result.fulltext_results
        ],
        "vector_results": [
            {
                "chunk_id": c.chunk_id,
                "path": c.vault_path,
                "heading": c.heading_path,
                "rank": c.rank,
                "score": c.score,
            }
            for c in result.vector_results
        ],
        "fused_results": [
            {
                "chunk_id": f.chunk_id,
                "path": f.vault_path,
                "heading": f.heading_path,
                "fused_rank": f.fused_rank,
                "rrf_score": f.rrf_score,
                "fulltext_rank": f.fulltext_rank,
                "vector_rank": f.vector_rank,
            }
            for f in result.fused_results
        ],
        "timing_ms": result.timing_ms,
    }
```

Modify `apps/api/app/main.py` to the full contents:

```python
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.index_status import router as index_status_router
from app.api.retrieval_debug import router as retrieval_debug_router

app = FastAPI(title="vault-interview-copilot")
app.include_router(health_router)
app.include_router(index_status_router)
app.include_router(retrieval_debug_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/test_retrieval_debug.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd apps/api && pytest -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/retrieval_debug.py apps/api/app/main.py apps/api/tests/test_retrieval_debug.py
git commit -m "feat(api): add GET /api/debug/retrieve, a no-LLM retrieval debug endpoint"
```

---

### Task 8: Evaluation metrics

**Files:**
- Create: `apps/api/app/evaluation/__init__.py`
- Create: `apps/api/app/evaluation/metrics.py`
- Create: `apps/api/tests/evaluation/__init__.py`
- Test: `apps/api/tests/evaluation/test_metrics.py`

**Interfaces:**
- Consumes: `FusedResult` (Task 5).
- Produces: `hit_at_k(fused_results: list[FusedResult], expected_paths: list[str], k: int) -> bool`, `reciprocal_rank(fused_results: list[FusedResult], expected_paths: list[str]) -> float`, `exact_match(fused_results: list[FusedResult], expected_paths: list[str]) -> bool`, `percentile(values: list[float], p: float) -> float`. Consumed by Task 9 (evaluation runner).

These are pure functions — no database.

- [ ] **Step 1: Write the failing test**

Create `apps/api/app/evaluation/__init__.py` (empty) and `apps/api/tests/evaluation/__init__.py` (empty).

Create `apps/api/tests/evaluation/test_metrics.py`:

```python
from app.evaluation.metrics import exact_match, hit_at_k, percentile, reciprocal_rank
from app.retrieval.fusion import FusedResult


def _fused(vault_path: str, fused_rank: int) -> FusedResult:
    return FusedResult(
        chunk_id=fused_rank,
        vault_path=vault_path,
        heading_path=None,
        fused_rank=fused_rank,
        rrf_score=1.0 / fused_rank,
        fulltext_rank=fused_rank,
        vector_rank=fused_rank,
    )


def test_hit_at_k_true_when_expected_path_within_k():
    results = [_fused("A.md", 1), _fused("B.md", 2), _fused("Expected.md", 3)]
    assert hit_at_k(results, ["Expected.md"], k=5) is True


def test_hit_at_k_false_when_expected_path_beyond_k():
    results = [_fused("A.md", 1), _fused("Expected.md", 6)]
    assert hit_at_k(results, ["Expected.md"], k=5) is False


def test_hit_at_k_true_if_any_expected_path_matches():
    results = [_fused("A.md", 1), _fused("Expected-2.md", 2)]
    assert hit_at_k(results, ["Expected-1.md", "Expected-2.md"], k=5) is True


def test_reciprocal_rank_of_first_match():
    results = [_fused("A.md", 1), _fused("Expected.md", 3)]
    assert reciprocal_rank(results, ["Expected.md"]) == 1 / 3


def test_reciprocal_rank_zero_when_no_match():
    results = [_fused("A.md", 1)]
    assert reciprocal_rank(results, ["Expected.md"]) == 0.0


def test_exact_match_true_when_top_result_is_expected():
    results = [_fused("Expected.md", 1), _fused("A.md", 2)]
    assert exact_match(results, ["Expected.md"]) is True


def test_exact_match_false_when_top_result_is_not_expected():
    results = [_fused("A.md", 1), _fused("Expected.md", 2)]
    assert exact_match(results, ["Expected.md"]) is False


def test_exact_match_false_on_empty_results():
    assert exact_match([], ["Expected.md"]) is False


def test_percentile_p50_of_sorted_values():
    assert percentile([10.0, 20.0, 30.0, 40.0], 50) == 25.0


def test_percentile_p95_of_sorted_values():
    # Linear interpolation (matches numpy.percentile's default method):
    # index = 0.95 * 99 = 94.05, interpolates between sorted_values[94]=95
    # and sorted_values[95]=96 -> 95 + (96-95)*0.05 = 95.05, not a round 95.0.
    assert percentile(list(range(1, 101)), 95) == 95.05
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/evaluation/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.evaluation.metrics'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/evaluation/metrics.py`:

```python
from __future__ import annotations

import math

from app.retrieval.fusion import FusedResult


def hit_at_k(fused_results: list[FusedResult], expected_paths: list[str], k: int) -> bool:
    top_k_paths = {r.vault_path for r in fused_results if r.fused_rank <= k}
    return bool(top_k_paths & set(expected_paths))


def reciprocal_rank(fused_results: list[FusedResult], expected_paths: list[str]) -> float:
    for result in fused_results:
        if result.vault_path in expected_paths:
            return 1.0 / result.fused_rank
    return 0.0


def exact_match(fused_results: list[FusedResult], expected_paths: list[str]) -> bool:
    if not fused_results:
        return False
    return fused_results[0].vault_path in expected_paths


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (p / 100) * (len(sorted_values) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[int(index)]
    fraction = index - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/evaluation/test_metrics.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/evaluation/__init__.py apps/api/app/evaluation/metrics.py apps/api/tests/evaluation/__init__.py apps/api/tests/evaluation/test_metrics.py
git commit -m "feat(evaluation): add recall/MRR/exact-match/percentile metrics"
```

---

### Task 9: Evaluation runner

**Files:**
- Create: `apps/api/app/evaluation/runner.py`
- Test: `apps/api/tests/evaluation/test_runner.py`

**Interfaces:**
- Consumes: `search` (Task 6), `hit_at_k`/`reciprocal_rank`/`exact_match`/`percentile` (Task 8), `EmbeddingProvider` (`app.ingestion.embeddings`).
- Produces: `Fixture(id: str, query: str, interviewer_phrasing: str | None, expected_notes: list[str])`, `load_fixtures(path: str) -> list[Fixture]`, `FixtureResult(fixture_id: str, query_form: str, query_text: str, hit_at_5: bool, hit_at_10: bool, reciprocal_rank: float, exact_match: bool, latency_ms: float)`, `EvalGroupMetrics(recall_at_5: float, recall_at_10: float, mrr: float, exact_match_rate: float, latency_p50_ms: float, latency_p95_ms: float)`, `EvalReport(shorthand: EvalGroupMetrics, natural: EvalGroupMetrics, results: list[FixtureResult])`, `run_eval(session: Session, embedding_provider: EmbeddingProvider, fixtures: list[Fixture]) -> EvalReport`. Consumed by Task 10 (CLI) and Task 12 (exit-condition test).

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/evaluation/test_runner.py`:

```python
import textwrap
from datetime import datetime, timezone

import pytest

from app.db.models import Chunk, Note
from app.evaluation.runner import load_fixtures, run_eval
from tests.ingestion.fakes import FakeEmbeddingProvider


def _write_fixture_file(tmp_path, contents):
    path = tmp_path / "fixtures.yaml"
    path.write_text(textwrap.dedent(contents), encoding="utf-8")
    return str(path)


def test_load_fixtures_parses_both_query_forms(tmp_path):
    path = _write_fixture_file(
        tmp_path,
        """
        - id: fixture-1
          query: "tf drift"
          interviewer_phrasing: "How do you know if your infrastructure has drifted?"
          expected_notes:
            - "Terraform.md"
          expected_concepts:
            - state drift
          expected_personal_project:
            - Meridian
        """,
    )

    fixtures = load_fixtures(path)

    assert len(fixtures) == 1
    assert fixtures[0].id == "fixture-1"
    assert fixtures[0].query == "tf drift"
    assert fixtures[0].interviewer_phrasing == "How do you know if your infrastructure has drifted?"
    assert fixtures[0].expected_notes == ["Terraform.md"]


def test_load_fixtures_handles_missing_interviewer_phrasing(tmp_path):
    path = _write_fixture_file(
        tmp_path,
        """
        - id: fixture-1
          query: "tf drift"
          expected_notes:
            - "Terraform.md"
        """,
    )

    fixtures = load_fixtures(path)

    assert fixtures[0].interviewer_phrasing is None


def test_run_eval_scores_shorthand_and_natural_forms_separately(db_session, tmp_path):
    note = Note(
        vault_path="Terraform.md",
        filename="Terraform.md",
        title="Terraform.md",
        content_hash="hash-terraform",
        modified_at=datetime.now(timezone.utc),
    )
    db_session.add(note)
    db_session.flush()
    content = "Document: Terraform\nState drift happens when infrastructure diverges."
    db_session.add(
        Chunk(
            note_id=note.id,
            chunk_index=0,
            start_line=1,
            end_line=5,
            content=content,
            content_with_context=content,
            content_hash="chash-terraform",
            embedding=FakeEmbeddingProvider().embed_batch([content])[0],
        )
    )
    db_session.commit()

    path = _write_fixture_file(
        tmp_path,
        """
        - id: fixture-1
          query: "tf drift"
          interviewer_phrasing: "How do you know if your infrastructure has drifted?"
          expected_notes:
            - "Terraform.md"
        """,
    )
    fixtures = load_fixtures(path)

    report = run_eval(db_session, FakeEmbeddingProvider(), fixtures)

    shorthand_results = [r for r in report.results if r.query_form == "shorthand"]
    natural_results = [r for r in report.results if r.query_form == "natural"]
    assert len(shorthand_results) == 1
    assert len(natural_results) == 1
    assert shorthand_results[0].query_text == "tf drift"
    assert natural_results[0].query_text == "How do you know if your infrastructure has drifted?"
    assert 0.0 <= report.shorthand.recall_at_5 <= 1.0
    assert 0.0 <= report.natural.recall_at_5 <= 1.0


def test_run_eval_skips_natural_form_when_absent(db_session, tmp_path):
    path = _write_fixture_file(
        tmp_path,
        """
        - id: fixture-1
          query: "tf drift"
          expected_notes:
            - "Terraform.md"
        """,
    )
    fixtures = load_fixtures(path)

    report = run_eval(db_session, FakeEmbeddingProvider(), fixtures)

    assert len(report.results) == 1
    assert report.results[0].query_form == "shorthand"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/evaluation/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.evaluation.runner'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/evaluation/runner.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import yaml
from sqlalchemy.orm import Session

from app.evaluation.metrics import exact_match, hit_at_k, percentile, reciprocal_rank
from app.ingestion.embeddings import EmbeddingProvider
from app.retrieval.search import search


@dataclass
class Fixture:
    id: str
    query: str
    interviewer_phrasing: str | None
    expected_notes: list[str]


@dataclass
class FixtureResult:
    fixture_id: str
    query_form: str
    query_text: str
    hit_at_5: bool
    hit_at_10: bool
    reciprocal_rank: float
    exact_match: bool
    latency_ms: float


@dataclass
class EvalGroupMetrics:
    recall_at_5: float
    recall_at_10: float
    mrr: float
    exact_match_rate: float
    latency_p50_ms: float
    latency_p95_ms: float


@dataclass
class EvalReport:
    shorthand: EvalGroupMetrics
    natural: EvalGroupMetrics
    results: list[FixtureResult]


def load_fixtures(path: str) -> list[Fixture]:
    with open(path, encoding="utf-8") as f:
        raw_fixtures = yaml.safe_load(f)

    return [
        Fixture(
            id=item["id"],
            query=item["query"],
            interviewer_phrasing=item.get("interviewer_phrasing"),
            expected_notes=item["expected_notes"],
        )
        for item in raw_fixtures
    ]


def _score_one(session: Session, embedding_provider: EmbeddingProvider, fixture: Fixture, query_form: str, query_text: str) -> FixtureResult:
    result = search(session, embedding_provider, query_text)
    return FixtureResult(
        fixture_id=fixture.id,
        query_form=query_form,
        query_text=query_text,
        hit_at_5=hit_at_k(result.fused_results, fixture.expected_notes, k=5),
        hit_at_10=hit_at_k(result.fused_results, fixture.expected_notes, k=10),
        reciprocal_rank=reciprocal_rank(result.fused_results, fixture.expected_notes),
        exact_match=exact_match(result.fused_results, fixture.expected_notes),
        latency_ms=result.timing_ms["total"],
    )


def _aggregate(results: list[FixtureResult]) -> EvalGroupMetrics:
    if not results:
        return EvalGroupMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    latencies = [r.latency_ms for r in results]
    return EvalGroupMetrics(
        recall_at_5=sum(r.hit_at_5 for r in results) / len(results),
        recall_at_10=sum(r.hit_at_10 for r in results) / len(results),
        mrr=sum(r.reciprocal_rank for r in results) / len(results),
        exact_match_rate=sum(r.exact_match for r in results) / len(results),
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
    )


def run_eval(session: Session, embedding_provider: EmbeddingProvider, fixtures: list[Fixture]) -> EvalReport:
    results: list[FixtureResult] = []

    for fixture in fixtures:
        results.append(_score_one(session, embedding_provider, fixture, "shorthand", fixture.query))
        if fixture.interviewer_phrasing is not None:
            results.append(_score_one(session, embedding_provider, fixture, "natural", fixture.interviewer_phrasing))

    shorthand_results = [r for r in results if r.query_form == "shorthand"]
    natural_results = [r for r in results if r.query_form == "natural"]

    return EvalReport(
        shorthand=_aggregate(shorthand_results),
        natural=_aggregate(natural_results),
        results=results,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/evaluation/test_runner.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/evaluation/runner.py apps/api/tests/evaluation/test_runner.py
git commit -m "feat(evaluation): add fixture loader and eval runner, scoring both query forms separately"
```

---

### Task 10: Evaluation CLI

**Files:**
- Create: `apps/api/app/evaluation/cli.py`
- Test: `apps/api/tests/evaluation/test_cli.py`

**Interfaces:**
- Consumes: `load_fixtures`, `run_eval` (Task 9), `settings` (`app.core.config`), `SessionLocal` (`app.db.base`), `OllamaEmbeddingProvider` (`app.ingestion.embeddings`).
- Produces: `main(argv: list[str] | None = None) -> None`, runnable as `python -m app.evaluation.cli --dataset {sample-vault|private}`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/evaluation/test_cli.py`:

```python
import textwrap
from datetime import datetime, timezone

import app.evaluation.cli as cli_module
from app.db.models import Chunk, Note
from tests.ingestion.fakes import FakeEmbeddingProvider


def test_parse_args_dataset_flag_sample_vault():
    args = cli_module._parse_args(["--dataset", "sample-vault"])
    assert args.dataset == "sample-vault"


def test_parse_args_dataset_flag_private():
    args = cli_module._parse_args(["--dataset", "private"])
    assert args.dataset == "private"


def test_parse_args_rejects_unknown_dataset():
    import pytest

    with pytest.raises(SystemExit):
        cli_module._parse_args(["--dataset", "nonsense"])


def test_main_runs_eval_and_prints_both_forms(tmp_path, db_session, monkeypatch, capsys):
    note = Note(
        vault_path="Terraform.md",
        filename="Terraform.md",
        title="Terraform.md",
        content_hash="hash-terraform",
        modified_at=datetime.now(timezone.utc),
    )
    db_session.add(note)
    db_session.flush()
    content = "Document: Terraform\nState drift happens when infrastructure diverges."
    db_session.add(
        Chunk(
            note_id=note.id,
            chunk_index=0,
            start_line=1,
            end_line=5,
            content=content,
            content_with_context=content,
            content_hash="chash-terraform",
            embedding=FakeEmbeddingProvider().embed_batch([content])[0],
        )
    )
    db_session.commit()

    fixtures_path = tmp_path / "fixtures.yaml"
    fixtures_path.write_text(
        textwrap.dedent(
            """
            - id: fixture-1
              query: "tf drift"
              interviewer_phrasing: "How do you know if infrastructure has drifted?"
              expected_notes:
                - "Terraform.md"
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingProvider", lambda base_url: FakeEmbeddingProvider())
    monkeypatch.setitem(cli_module.DATASET_PATHS, "sample-vault", str(fixtures_path))

    cli_module.main(["--dataset", "sample-vault"])

    captured = capsys.readouterr()
    assert "Shorthand" in captured.out
    assert "Natural phrasing" in captured.out
    assert "Recall@5" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/evaluation/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.evaluation.cli'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/evaluation/cli.py`:

```python
from __future__ import annotations

import argparse

from app.core.config import settings
from app.db.base import SessionLocal
from app.evaluation.runner import EvalGroupMetrics, load_fixtures, run_eval
from app.ingestion.embeddings import OllamaEmbeddingProvider

DATASET_PATHS = {
    "sample-vault": "../../evaluation/datasets/sample-vault/meridian-fixtures.yaml",
    "private": "../../evaluation/datasets/private/mock-interview-fixtures.yaml",
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.evaluation.cli",
        description="Score retrieval against a fixture dataset.",
    )
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASET_PATHS.keys()),
        required=True,
        help="Which fixture dataset to evaluate against.",
    )
    return parser.parse_args(argv if argv is not None else [])


def _print_group(label: str, group: EvalGroupMetrics) -> None:
    print(
        f"{label}: Recall@5: {group.recall_at_5:.0%}  Recall@10: {group.recall_at_10:.0%}  "
        f"MRR: {group.mrr:.2f}  Exact match: {group.exact_match_rate:.0%}"
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    fixtures = load_fixtures(DATASET_PATHS[args.dataset])

    session = SessionLocal()
    try:
        provider = OllamaEmbeddingProvider(base_url=settings.ollama_workstation_url)
        report = run_eval(session, provider, fixtures)

        _print_group("Shorthand", report.shorthand)
        _print_group("Natural phrasing", report.natural)
        print(
            f"Retrieval latency: p50 {report.shorthand.latency_p50_ms:.0f}ms, "
            f"p95 {report.shorthand.latency_p95_ms:.0f}ms"
        )
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
```

`DATASET_PATHS` uses relative paths from `apps/api/` (matching where `python -m app.evaluation.cli` is run from, per the established Phase 1 CLI convention) — resolve to repo-root-relative `evaluation/datasets/...`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/evaluation/test_cli.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/evaluation/cli.py apps/api/tests/evaluation/test_cli.py
git commit -m "feat(evaluation): add python -m app.evaluation.cli"
```

---

### Task 11: Retrofit `interviewer_phrasing` onto sample-vault fixtures

**Files:**
- Modify: `evaluation/datasets/sample-vault/meridian-fixtures.yaml`

**Interfaces:**
- Consumes: nothing from earlier tasks (content-only change).
- Produces: no new code — makes the sample-vault fixture set structurally match `evaluation/datasets/private/mock-interview-fixtures.yaml` (both `query` and `interviewer_phrasing` present on every fixture), so Task 12's exit-condition run actually exercises normalization against natural phrasing, not just shorthand.

**Why this is a task, not optional polish:** per the design spec, automated/CI runs only ever use `sample-vault` (the private set requires the real vault, run manually). Without `interviewer_phrasing` on these 6 fixtures, the Phase 2 exit-condition proof would never test whether normalization actually helps — it would only prove retrieval works on input that barely needed normalizing.

- [ ] **Step 1: Add `interviewer_phrasing` to each of the 6 fixtures**

Modify `evaluation/datasets/sample-vault/meridian-fixtures.yaml`. Insert an `interviewer_phrasing` line immediately after each fixture's `query` line, exactly as shown (six additions, one per fixture, nothing else in the file changes):

After `query: "terraform state drift"` (fixture `meridian-terraform-state-drift-001`), add:
```yaml
  interviewer_phrasing: "Walk me through how you actually manage your infrastructure once it's live — how do you know if something's drifted from what's in your Terraform config?"
```

After `query: "terraform state locking team"` (fixture `meridian-terraform-state-locking-002`), add:
```yaml
  interviewer_phrasing: "If you've got multiple people on a team all running Terraform, how do you keep the state file from getting corrupted?"
```

After `query: "pod scaling vs node scaling"` (fixture `meridian-pod-vs-node-scaling-003`), add:
```yaml
  interviewer_phrasing: "Can you describe the difference between how your pods scale and how your underlying nodes scale?"
```

After `query: "why gitops over jenkins"` (fixture `meridian-gitops-vs-jenkins-004`), add:
```yaml
  interviewer_phrasing: "Why did you go with a GitOps-style setup instead of just running everything through a Jenkins server?"
```

After `query: "jenkins cant containerize docker plugin"` (fixture `meridian-jenkins-docker-daemon-005`), add:
```yaml
  interviewer_phrasing: "Say your Jenkins pipeline can't containerize the app even though the Docker plugin's installed — what would you check?"
```

After `query: "node scaling cluster autoscaler config location"` (fixture `meridian-headingless-note-followup-006`), add:
```yaml
  interviewer_phrasing: "Where does the actual configuration for your Cluster Autoscaler live?"
```

- [ ] **Step 2: Validate the YAML still parses and every fixture has both fields**

Run:
```bash
cd /home/ben/Projects/vault-interview-copilot
python3 -c "
import yaml
with open('evaluation/datasets/sample-vault/meridian-fixtures.yaml') as f:
    data = yaml.safe_load(f)
assert len(data) == 6
for fixture in data:
    assert fixture.get('interviewer_phrasing'), f'{fixture[\"id\"]} missing interviewer_phrasing'
print('OK:', len(data), 'fixtures, all with interviewer_phrasing')
"
```
Expected: `OK: 6 fixtures, all with interviewer_phrasing`

- [ ] **Step 3: Commit**

```bash
git add evaluation/datasets/sample-vault/meridian-fixtures.yaml
git commit -m "feat(evaluation): add interviewer_phrasing to sample-vault fixtures

Automated/CI runs are sample-vault-only, so without this field the
exit-condition proof never exercised natural-phrasing normalization,
only shorthand. Matches the private fixture set's structure."
```

---

### Task 12: Exit-condition proof — measure, lock threshold, verify

**Files:**
- Test: `apps/api/tests/evaluation/test_retrieval_eval.py`

**Interfaces:**
- Consumes: `load_fixtures`, `run_eval` (Task 9), the retrofitted `evaluation/datasets/sample-vault/meridian-fixtures.yaml` (Task 11), the real indexed `sample-vault` content (real Postgres, `db_session` fixture).
- Produces: no new application code — this is the authoritative proof of the Phase 2 exit condition from `docs/architecture/10-delivery-plan.md`.

**Read this task's process before starting, not just its code.** The Recall@5 threshold below is not decided in advance — it comes from a real measurement you take as part of this task. There are exactly two things you're allowed to do if the first measurement isn't 100%, and only one of them:

- **Allowed:** if a specific fixture misses because of an actual bug in the retrieval code (wrong RRF weighting, a normalization gap, a query that should have matched but didn't due to a defect), fix that *code*, then re-run once. Whatever number comes back from that one re-run is the threshold you commit.
- **Not allowed, under any circumstance:** editing `meridian-fixtures.yaml`'s `expected_notes`, wording, or dropping a fixture to make the number climb. That is not "fixing" anything — it's inventing a passing test instead of proving the exit condition. If you find yourself opening the fixture file to make this test pass, stop and report the specific miss as a finding instead of editing it.

- [ ] **Step 1: Index `sample-vault` for real, into the same Postgres the test will query**

The `db_session` fixture (`apps/api/tests/conftest.py`) migrates and truncates a **fresh** schema per test — it does not contain `sample-vault`'s content. This task needs `sample-vault` actually indexed within the test itself, using the real chunker/parser/scanner pipeline (not hand-built `Note`/`Chunk` rows like earlier tasks' unit tests), so the eval is scored against real chunk boundaries and real heading structure, not simplified test fixtures.

Write the test to call `run_index` (from `app.ingestion.indexer`, Phase 1) against the real `sample-vault/` directory at the start of the test, using `FakeEmbeddingProvider` (fast, deterministic, no live Ollama dependency — matches how `test_sample_vault_integration.py` already does this in Phase 1).

Create `apps/api/tests/evaluation/test_retrieval_eval.py`:

```python
from pathlib import Path

from app.evaluation.runner import load_fixtures, run_eval
from app.ingestion.indexer import run_index
from tests.ingestion.fakes import FakeEmbeddingProvider

SAMPLE_VAULT = Path(__file__).resolve().parents[4] / "sample-vault"
FIXTURES_PATH = (
    Path(__file__).resolve().parents[4] / "evaluation" / "datasets" / "sample-vault" / "meridian-fixtures.yaml"
)


def test_shorthand_recall_at_5_meets_measured_threshold(db_session):
    provider = FakeEmbeddingProvider()
    index_result = run_index(
        db_session, str(SAMPLE_VAULT), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )
    assert index_result.status == "success"

    fixtures = load_fixtures(str(FIXTURES_PATH))
    report = run_eval(db_session, provider, fixtures)

    # Threshold below is the real value measured in Step 2 of this task —
    # see the task's own instructions before changing this number.
    assert report.shorthand.recall_at_5 >= 1.0
```

The `>= 1.0` above is a **starting placeholder for the first run only** — it exists so the test can execute at all. It is expected to either pass outright (if the real measurement is 100%) or fail with a specific, informative number (e.g. `assert 0.833... >= 1.0`), which is exactly what Step 2 needs to see. This is not the "no placeholders" violation the plan process normally forbids — it's the deliberate first data point in a measure-then-lock process the design spec explicitly calls for; leaving it at `1.0` after Step 2 without adjusting it to the real measured value would be the actual violation.

- [ ] **Step 2: Run the test to get the real measurement**

Run: `cd apps/api && pytest tests/evaluation/test_retrieval_eval.py -v -s`

Record the exact `recall_at_5` value from the assertion failure output (or PASS, if it's already 100%). If it fails, the pytest output shows the real value, e.g. `assert 0.8333333333333334 >= 1.0`.

- [ ] **Step 3: If below 100%, investigate — retrieval code only**

If Step 2 showed less than 100%: for each fixture that missed, run `python -m app.evaluation.cli --dataset sample-vault` (Task 10) or inspect `report.results` directly to see which specific fixture(s) missed and in which query form (shorthand vs. natural). For each miss, determine: is this a genuine retrieval defect (e.g., `websearch_to_tsquery` mishandling a specific phrase, RRF favoring the wrong candidate, an alias that should have expanded but didn't), or is the fixture asking for something retrieval structurally can't be expected to find yet (e.g., a concept covered only in `expected_concepts` prose, not in the actual chunk text)?

If it's a genuine code defect: fix it in the relevant `app/retrieval/` module, re-run Step 2's test once, and use *that* number going forward. Do not iterate further — one fix pass, one re-measurement.

If it's not a code defect (the fixture is legitimately hard, or is testing something out of Phase 2's scope): the measured number — including the miss — is what gets locked in. This is real information about where the system stands, not a problem to make disappear.

- [ ] **Step 4: Lock in the real threshold**

Edit `apps/api/tests/evaluation/test_retrieval_eval.py`, replacing the `>= 1.0` placeholder with the actual measured value from whichever run (Step 2's first run, or Step 3's one re-run) is the final one:

```python
    # Measured 2026-07-19 against sample-vault + retrofitted interviewer_phrasing
    # fixtures (Task 11). This is a regression floor from a real run, not a
    # target picked in advance — see this task's own process notes above.
    assert report.shorthand.recall_at_5 >= <ACTUAL_MEASURED_VALUE>
```

Replace `<ACTUAL_MEASURED_VALUE>` and the date comment with the real number and today's actual date — this plan cannot know that value in advance, by design.

- [ ] **Step 5: Run the test to verify it passes at the locked threshold**

Run: `cd apps/api && pytest tests/evaluation/test_retrieval_eval.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

Run: `cd apps/api && pytest -v`
Expected: PASS, full suite green. This is the last task of Phase 2 — a regression here could mean something in Tasks 1-11 broke Phase 1's existing behavior.

- [ ] **Step 7: Commit**

```bash
git add apps/api/tests/evaluation/test_retrieval_eval.py
git commit -m "test(evaluation): lock Phase 2 exit-condition threshold at measured shorthand Recall@5

Phase 2 exit condition (docs/architecture/10-delivery-plan.md): shorthand
queries consistently retrieve the expected sample notes. Threshold is the
real value measured against sample-vault + retrofitted interviewer_phrasing
fixtures, not an invented target."
```

---

## Summary

Twelve tasks, in dependency order: `search_vector` migration → normalization → full-text search → vector search → RRF fusion → search orchestration → debug endpoint → evaluation metrics → evaluation runner → evaluation CLI → fixture retrofit → exit-condition proof. Each task is independently testable and commits on its own. Phase 2's exit condition (`docs/architecture/10-delivery-plan.md`) is satisfied by Task 12, using a threshold measured during implementation, not decided in advance.
