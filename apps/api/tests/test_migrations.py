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
