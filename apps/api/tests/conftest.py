import os
import re

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config
from app.core.config import settings


def _test_database_url(base_url: str) -> str:
    """Derive an isolated test database URL from settings.database_url by
    appending _test to the database name (.../vault_copilot ->
    .../vault_copilot_test). Tests must never run against the same database
    a developer's manual/live verification (uvicorn, CLI runs) uses -- a
    prior session lost a whole batch of live diagnostic data this way when
    a routine pytest run truncated query_runs/notes/chunks mid-investigation.
    See docs/architecture/09-testing.md."""
    return re.sub(r"/([^/]+)$", r"/\1_test", base_url)


TEST_DATABASE_URL = _test_database_url(settings.database_url)
os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL


def _ensure_test_database_exists() -> None:
    admin_url = re.sub(r"/[^/]+$", "/postgres", TEST_DATABASE_URL)
    test_db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1]
    admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                sa.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_db_name},
            ).scalar()
            if not exists:
                conn.execute(sa.text(f'CREATE DATABASE "{test_db_name}"'))
    finally:
        admin_engine.dispose()


_ensure_test_database_exists()


@pytest.fixture()
def db_engine():
    engine = sa.create_engine(TEST_DATABASE_URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    command.upgrade(Config("alembic.ini"), "head")
    session_factory = sessionmaker(bind=db_engine, future=True)
    session = session_factory()
    yield session
    session.rollback()
    session.close()
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                "TRUNCATE notes, chunks, note_links, index_runs, query_runs "
                "RESTART IDENTITY CASCADE"
            )
        )
