import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config
from app.core.config import settings


@pytest.fixture()
def db_engine():
    engine = sa.create_engine(settings.database_url, future=True)
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
