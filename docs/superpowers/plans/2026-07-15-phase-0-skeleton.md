# Phase 0 Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Meet the Phase 0 exit condition — `docker compose up` starts Postgres+pgvector and a FastAPI API end to end, the API exposes a working `/health` endpoint, the first Alembic migration stands up the five tables from `docs/architecture/01-data-model.md`, and CI runs formatting and tests.

**Architecture:** A minimal FastAPI app (`apps/api/app`) with `core` (settings), `api` (routers), and `db` (SQLAlchemy models + Alembic) modules, matching the module boundaries already scaffolded in the repo. SQLAlchemy 2.0 declarative models map 1:1 to the five tables in the data model doc; one hand-written Alembic migration creates the `vector` extension and all five tables. The API container runs `alembic upgrade head` before `uvicorn` on startup so `docker compose up` alone produces a fully-migrated database.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.0, Alembic, psycopg3, pgvector (Python package), pytest, ruff.

## Global Constraints

- Postgres image: `pgvector/pgvector:pg16` (already in `docker-compose.yml` — do not change).
- No containerized Ollama; CI and tests must never require a live Ollama instance.
- Embedding model is `nomic-embed-text`, which produces 768-dimensional vectors — the `chunks.embedding` column must be `Vector(768)`.
- Schema is exactly the five tables in `docs/architecture/01-data-model.md` (`notes`, `chunks`, `note_links`, `index_runs`, `query_runs`) — no extra tables (e.g. no `settings` table; that's a later-phase concern, not part of this doc).
- All schema changes go through Alembic — no hand-written SQL run outside it.
- Query logging (`query_runs`) is on by default per the locked decisions — no schema toggle needed, just the table.
- Standard CI must be deterministic — no dependency on a real LLM/Ollama call.

---

## File Structure

```
apps/api/
  Dockerfile
  requirements.txt
  requirements-dev.txt
  alembic.ini
  pyproject.toml                 # ruff + pytest config only, no packaging
  alembic/
    env.py
    script.py.mako
    versions/
      0001_initial_schema.py
  app/
    __init__.py
    main.py                      # FastAPI() instance, includes routers
    core/
      __init__.py
      config.py                  # pydantic-settings Settings
    api/
      __init__.py
      health.py                  # GET /health router
    db/
      __init__.py
      base.py                    # engine, SessionLocal, declarative Base
      models.py                  # Note, Chunk, NoteLink, IndexRun, QueryRun
  tests/
    __init__.py
    conftest.py                  # db_engine fixture
    test_health.py
    test_migrations.py
.github/
  workflows/
    ci.yml
docker-compose.yml               # modify: add api environment override, remove stale comment
.env.example                     # modify: DATABASE_URL scheme -> postgresql+psycopg://
README.md                        # modify: update Phase 0 status once verified end-to-end
```

---

### Task 1: Python project scaffolding (dependencies, lint/test config)

**Files:**
- Create: `apps/api/requirements.txt`
- Create: `apps/api/requirements-dev.txt`
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/app/__init__.py` (empty)
- Test: none (config-only task, verified by Task 2's test run)

**Interfaces:**
- Produces: an installable dependency set every later task assumes is present (`fastapi`, `sqlalchemy`, `alembic`, `psycopg[binary]`, `pgvector`, `pydantic-settings`, `httpx`, `structlog`, `pytest`, `ruff`).

- [ ] **Step 1: Write `apps/api/requirements.txt`**

```text
fastapi>=0.115,<0.116
uvicorn[standard]>=0.32,<0.33
sqlalchemy>=2.0.36,<2.1
alembic>=1.14,<1.15
psycopg[binary]>=3.2,<3.3
pgvector>=0.3.6,<0.4
pydantic>=2.9,<3
pydantic-settings>=2.6,<3
httpx>=0.27,<0.28
structlog>=24.4,<25
```

- [ ] **Step 2: Write `apps/api/requirements-dev.txt`**

```text
-r requirements.txt
pytest>=8.3,<9
ruff>=0.7,<0.8
```

- [ ] **Step 3: Write `apps/api/pyproject.toml`**

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Create `apps/api/app/__init__.py`**

Empty file — just makes `app` a package.

- [ ] **Step 5: Install and sanity-check**

Run:
```bash
cd apps/api
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```
Expected: install completes with no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/api/requirements.txt apps/api/requirements-dev.txt apps/api/pyproject.toml apps/api/app/__init__.py
git commit -m "chore(api): add Python project scaffolding and dependencies"
```

---

### Task 2: Settings module

**Files:**
- Create: `apps/api/app/core/__init__.py` (empty)
- Create: `apps/api/app/core/config.py`
- Test: `apps/api/tests/__init__.py` (empty), `apps/api/tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `app.core.config.settings` — a `Settings` instance with attributes `database_url: str`, `ollama_workstation_url: str`, `ollama_ai_inference_url: str`, `generation_model: str`, `embedding_model: str`, `vault_path: str`, `query_logging: bool`, `api_host: str`, `api_port: int`, `log_level: str`. All later tasks import this singleton.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_config.py
from app.core.config import Settings


def test_defaults_match_env_example():
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.generation_model == "qwen2.5:14b"
    assert settings.query_logging is True
    assert settings.api_port == 8000


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@z:5432/db")
    monkeypatch.setenv("QUERY_LOGGING", "false")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://x:y@z:5432/db"
    assert settings.query_logging is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core'`

- [ ] **Step 3: Write `apps/api/app/core/__init__.py`**

Empty file.

- [ ] **Step 4: Write `apps/api/app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://copilot:copilot@localhost:5432/vault_copilot"
    ollama_workstation_url: str = "http://localhost:11434"
    ollama_ai_inference_url: str = "http://localhost:11434"
    generation_model: str = "qwen2.5:14b"
    embedding_model: str = "nomic-embed-text"
    vault_path: str = "/vault"
    query_logging: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "info"


settings = Settings()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/api && .venv/bin/pytest tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/core/__init__.py apps/api/app/core/config.py apps/api/tests/__init__.py apps/api/tests/test_config.py
git commit -m "feat(api): add pydantic-settings configuration module"
```

---

### Task 3: FastAPI app with `/health` endpoint

**Files:**
- Create: `apps/api/app/api/__init__.py` (empty)
- Create: `apps/api/app/api/health.py`
- Create: `apps/api/app/main.py`
- Test: `apps/api/tests/test_health.py`

**Interfaces:**
- Consumes: nothing beyond FastAPI/starlette.
- Produces: `app.main.app` (the `FastAPI` instance), importable by the Dockerfile's `uvicorn app.main:app` command and by tests.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_health.py
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write `apps/api/app/api/__init__.py`**

Empty file.

- [ ] **Step 4: Write `apps/api/app/api/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Write `apps/api/app/main.py`**

```python
from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(title="vault-interview-copilot")
app.include_router(health_router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/api && .venv/bin/pytest tests/test_health.py -v`
Expected: PASS (1 test)

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/api/__init__.py apps/api/app/api/health.py apps/api/app/main.py apps/api/tests/test_health.py
git commit -m "feat(api): add FastAPI app with /health endpoint"
```

---

### Task 4: SQLAlchemy models for the five data-model tables

**Files:**
- Create: `apps/api/app/db/__init__.py` (empty)
- Create: `apps/api/app/db/base.py`
- Create: `apps/api/app/db/models.py`
- Test: `apps/api/tests/test_models.py`

**Interfaces:**
- Consumes: `app.core.config.settings.database_url`.
- Produces: `app.db.base.Base` (declarative base, `Base.metadata` used by Alembic's `env.py` in Task 5), `app.db.base.engine`, `app.db.base.SessionLocal`, and ORM classes `Note`, `Chunk`, `NoteLink`, `IndexRun`, `QueryRun` in `app.db.models`, each with `__tablename__` matching the data-model doc exactly (`notes`, `chunks`, `note_links`, `index_runs`, `query_runs`).

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_models.py
from app.db.base import Base
from app.db.models import Chunk, IndexRun, Note, NoteLink, QueryRun


def test_all_five_tables_registered_on_metadata():
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"notes", "chunks", "note_links", "index_runs", "query_runs"}


def test_chunk_embedding_is_768_dimensional_vector():
    from pgvector.sqlalchemy import Vector

    embedding_col = Chunk.__table__.columns["embedding"]
    assert isinstance(embedding_col.type, Vector)
    assert embedding_col.type.dim == 768


def test_foreign_keys_point_at_notes():
    chunk_fk = next(iter(Chunk.__table__.columns["note_id"].foreign_keys))
    assert chunk_fk.column.table.name == "notes"
    link_fk = next(iter(NoteLink.__table__.columns["source_note_id"].foreign_keys))
    assert link_fk.column.table.name == "notes"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write `apps/api/app/db/__init__.py`**

Empty file.

- [ ] **Step 4: Write `apps/api/app/db/base.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 5: Write `apps/api/app/db/models.py`**

```python
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

EMBEDDING_DIM = 768


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    vault_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frontmatter_json: Mapped[dict | None] = mapped_column(JSONB)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding_version: Mapped[str | None] = mapped_column(Text)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="note", cascade="all, delete-orphan"
    )
    links: Mapped[list["NoteLink"]] = relationship(
        back_populates="source_note", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
    )
    heading_path: Mapped[str | None] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    start_line: Mapped[int] = mapped_column(nullable=False)
    end_line: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_with_context: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column()
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)

    note: Mapped["Note"] = relationship(back_populates="chunks")


class NoteLink(Base):
    __tablename__ = "note_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
    )
    target_path: Mapped[str] = mapped_column(Text, nullable=False)
    link_text: Mapped[str | None] = mapped_column(Text)
    link_type: Mapped[str] = mapped_column(Text, nullable=False)

    source_note: Mapped["Note"] = relationship(back_populates="links")


class IndexRun(Base):
    __tablename__ = "index_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    files_scanned: Mapped[int] = mapped_column(default=0)
    files_added: Mapped[int] = mapped_column(default=0)
    files_updated: Mapped[int] = mapped_column(default=0)
    files_deleted: Mapped[int] = mapped_column(default=0)
    chunks_created: Mapped[int] = mapped_column(default=0)
    chunks_deleted: Mapped[int] = mapped_column(default=0)
    errors_json: Mapped[dict | None] = mapped_column(JSONB)


class QueryRun(Base):
    __tablename__ = "query_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str | None] = mapped_column(Text)
    response_mode: Mapped[str | None] = mapped_column(Text)
    retrieval_latency_ms: Mapped[int | None] = mapped_column()
    rerank_latency_ms: Mapped[int | None] = mapped_column()
    generation_latency_ms: Mapped[int | None] = mapped_column()
    total_latency_ms: Mapped[int | None] = mapped_column()
    retrieved_chunk_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    retrieval_scores: Mapped[dict | None] = mapped_column(JSONB)
    selected_source_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    provider_name: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/api && .venv/bin/pytest tests/test_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/db/__init__.py apps/api/app/db/base.py apps/api/app/db/models.py apps/api/tests/test_models.py
git commit -m "feat(api): add SQLAlchemy models for the five data-model tables"
```

---

### Task 5: Alembic setup and first migration

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/script.py.mako`
- Create: `apps/api/alembic/versions/0001_initial_schema.py`
- Test: `apps/api/tests/conftest.py`, `apps/api/tests/test_migrations.py`

**Interfaces:**
- Consumes: `app.db.base.Base`, `app.db.models` (Task 4), `app.core.config.settings.database_url` (Task 2).
- Produces: a runnable `alembic upgrade head` / `alembic downgrade base` against any Postgres reachable at `settings.database_url`, used by the Dockerfile (Task 6) and CI (Task 8).

This task requires a real Postgres with pgvector reachable at `settings.database_url` (default `postgresql+psycopg://copilot:copilot@localhost:5432/vault_copilot`). Start one locally before running the steps below:

```bash
docker run --rm -d --name copilot-test-pg \
  -e POSTGRES_USER=copilot -e POSTGRES_PASSWORD=copilot -e POSTGRES_DB=vault_copilot \
  -p 5432:5432 pgvector/pgvector:pg16
```

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/conftest.py
import pytest
import sqlalchemy as sa

from app.core.config import settings


@pytest.fixture()
def db_engine():
    engine = sa.create_engine(settings.database_url, future=True)
    yield engine
    engine.dispose()
```

```python
# apps/api/tests/test_migrations.py
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

EXPECTED_TABLES = {"notes", "chunks", "note_links", "index_runs", "query_runs"}


def _alembic_config() -> Config:
    return Config("alembic.ini")


def test_upgrade_head_creates_all_tables(db_engine):
    command.upgrade(_alembic_config(), "head")
    try:
        inspector = sa.inspect(db_engine)
        assert EXPECTED_TABLES.issubset(set(inspector.get_table_names()))
    finally:
        command.downgrade(_alembic_config(), "base")


def test_downgrade_base_removes_all_tables(db_engine):
    command.upgrade(_alembic_config(), "head")
    command.downgrade(_alembic_config(), "base")
    inspector = sa.inspect(db_engine)
    assert EXPECTED_TABLES.isdisjoint(set(inspector.get_table_names()))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/pytest tests/test_migrations.py -v`
Expected: FAIL with `FileNotFoundError` or similar — `alembic.ini` does not exist yet.

- [ ] **Step 3: Write `apps/api/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 4: Write `apps/api/alembic/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db import models  # noqa: F401  registers tables on Base.metadata
from app.db.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Write `apps/api/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Write `apps/api/alembic/versions/0001_initial_schema.py`**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vault_path", sa.Text(), nullable=False, unique=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frontmatter_json", JSONB(), nullable=True),
        sa.Column("tags", ARRAY(sa.Text()), nullable=True),
        sa.Column("aliases", ARRAY(sa.Text()), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding_version", sa.Text(), nullable=True),
    )
    op.create_index("ix_notes_content_hash", "notes", ["content_hash"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "note_id",
            sa.Integer(),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_with_context", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("search_vector", TSVECTOR(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
    )
    op.create_index("ix_chunks_note_id", "chunks", ["note_id"])
    op.create_index(
        "ix_chunks_search_vector", "chunks", ["search_vector"], postgresql_using="gin"
    )

    op.create_table(
        "note_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_note_id",
            sa.Integer(),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_path", sa.Text(), nullable=False),
        sa.Column("link_text", sa.Text(), nullable=True),
        sa.Column("link_type", sa.Text(), nullable=False),
    )
    op.create_index("ix_note_links_source_note_id", "note_links", ["source_note_id"])

    op.create_table(
        "index_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("files_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_json", JSONB(), nullable=True),
    )

    op.create_table(
        "query_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=True),
        sa.Column("response_mode", sa.Text(), nullable=True),
        sa.Column("retrieval_latency_ms", sa.Integer(), nullable=True),
        sa.Column("rerank_latency_ms", sa.Integer(), nullable=True),
        sa.Column("generation_latency_ms", sa.Integer(), nullable=True),
        sa.Column("total_latency_ms", sa.Integer(), nullable=True),
        sa.Column("retrieved_chunk_ids", ARRAY(sa.Integer()), nullable=True),
        sa.Column("retrieval_scores", JSONB(), nullable=True),
        sa.Column("selected_source_ids", ARRAY(sa.Integer()), nullable=True),
        sa.Column("provider_name", sa.Text(), nullable=True),
        sa.Column("model_name", sa.Text(), nullable=True),
    )
    op.create_index("ix_query_runs_created_at", "query_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("query_runs")
    op.drop_table("index_runs")
    op.drop_table("note_links")
    op.drop_table("chunks")
    op.drop_table("notes")
    # Deliberately not dropping the vector extension: it's shared at the
    # database level and safe to leave installed even with no tables using it.
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd apps/api && .venv/bin/pytest tests/test_migrations.py -v`
Expected: PASS (2 tests) — requires the local Postgres container from the task preamble to be running.

- [ ] **Step 8: Commit**

```bash
git add apps/api/alembic.ini apps/api/alembic/env.py apps/api/alembic/script.py.mako apps/api/alembic/versions/0001_initial_schema.py apps/api/tests/conftest.py apps/api/tests/test_migrations.py
git commit -m "feat(api): add Alembic setup and initial schema migration"
```

---

### Task 6: Dockerfile and docker-compose wiring

**Files:**
- Create: `apps/api/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Interfaces:**
- Consumes: everything from Tasks 1–5 (`requirements.txt`, `alembic.ini`, `alembic/`, `app/`).
- Produces: a built `copilot-api` image that runs migrations then serves the FastAPI app on `0.0.0.0:8000`.

- [ ] **Step 1: Write `apps/api/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2: Update `.env.example`** — change the `DATABASE_URL` line so the scheme matches the psycopg3 driver used by `app/db/base.py`

Old:
```text
DATABASE_URL=postgresql://copilot:copilot@localhost:5432/vault_copilot
```
New:
```text
DATABASE_URL=postgresql+psycopg://copilot:copilot@localhost:5432/vault_copilot
```

- [ ] **Step 3: Update `docker-compose.yml`** — the `api` service needs `DATABASE_URL` pointed at the `postgres` service hostname (not `localhost`, which only works from the host machine), overriding whatever's in `.env`. Also remove the now-stale "No Dockerfile yet" comment.

Replace:
```yaml
  api:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    container_name: copilot-api
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - ${VAULT_PATH:-./sample-vault}:/vault:ro
    depends_on:
      postgres:
        condition: service_healthy
    # No Dockerfile yet — Phase 0 next step. This service will fail to
    # build until apps/api/Dockerfile exists.
```
With:
```yaml
  api:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    container_name: copilot-api
    restart: unless-stopped
    env_file:
      - .env
    environment:
      # Overrides .env's localhost value — inside the compose network the
      # database is reachable at the "postgres" service name, not localhost.
      DATABASE_URL: postgresql+psycopg://copilot:copilot@postgres:5432/vault_copilot
    ports:
      - "8000:8000"
    volumes:
      - ${VAULT_PATH:-./sample-vault}:/vault:ro
    depends_on:
      postgres:
        condition: service_healthy
```

- [ ] **Step 4: Build and run the full stack**

Run:
```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```
Expected: both `copilot-postgres` and `copilot-api` show as running/healthy.

- [ ] **Step 5: Verify the health endpoint and migration**

Run:
```bash
curl -s http://localhost:8000/health
docker compose exec postgres psql -U copilot -d vault_copilot -c '\dt'
```
Expected: `curl` returns `{"status":"ok"}`; `\dt` lists `notes`, `chunks`, `note_links`, `index_runs`, `query_runs`, and `alembic_version`.

- [ ] **Step 6: Tear down**

```bash
docker compose down
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/Dockerfile docker-compose.yml .env.example
git commit -m "feat(api): add Dockerfile and wire api service into docker-compose"
```

---

### Task 7: CI workflow (formatting + tests)

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `apps/api/requirements-dev.txt`, `apps/api/pyproject.toml` (ruff config), `apps/api/tests/`.
- Produces: a GitHub Actions workflow satisfying the Phase 0 exit condition "CI runs formatting and tests."

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  api:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: copilot
          POSTGRES_PASSWORD: copilot
          POSTGRES_DB: vault_copilot
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U copilot -d vault_copilot"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+psycopg://copilot:copilot@localhost:5432/vault_copilot
    defaults:
      run:
        working-directory: apps/api
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Check formatting
        run: ruff format --check .
      - name: Lint
        run: ruff check .
      - name: Run tests
        run: pytest -v
```

- [ ] **Step 2: Validate YAML syntax locally**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK
```
Expected: `OK`

- [ ] **Step 3: Run the same checks locally that CI will run**

Run:
```bash
cd apps/api
.venv/bin/ruff format --check .
.venv/bin/ruff check .
```
Expected: `ruff format --check` reports no changes needed (if it does, run `.venv/bin/ruff format .` to fix and re-check); `ruff check` reports no issues.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for formatting and tests"
```

---

### Task 8: Final end-to-end verification and README update

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the fully assembled stack from Tasks 1–7.
- Produces: nothing new — this task is a final gate confirming the Phase 0 exit condition and reflecting it in the README.

- [ ] **Step 1: Run the full local test suite one more time**

```bash
cd apps/api
.venv/bin/pytest -v
```
Expected: all tests pass (config, health, models, migrations).

- [ ] **Step 2: Run the full docker compose stack from a clean state**

```bash
cd /home/ben/Projects/vault-interview-copilot
docker compose down -v
cp -n .env.example .env
docker compose up -d --build
sleep 5
curl -sf http://localhost:8000/health && echo
docker compose exec postgres psql -U copilot -d vault_copilot -c '\dt'
docker compose down
```
Expected: `/health` returns `{"status":"ok"}`, `\dt` lists all five tables plus `alembic_version`, no errors on teardown.

- [ ] **Step 3: Update `README.md`** — change the status line to reflect Phase 0 completion

Old:
```markdown
**Status:** Phase 0 — repo skeleton. Not yet functional.
```
New:
```markdown
**Status:** Phase 0 complete — `docker compose up` starts Postgres+pgvector and the API end to end; `/health` responds; schema is migrated. Phase 1 (vault indexing) not yet started.
```

Old:
```markdown
Not yet runnable — Phase 0 in progress. Docker Compose skeleton is in place; API and web apps are not yet implemented.
```
New:
```markdown
```bash
cp .env.example .env
docker compose up -d
curl http://localhost:8000/health
```
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README status for Phase 0 completion"
```
