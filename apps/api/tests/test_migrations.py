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


def test_0002_backfills_search_vector_for_preexisting_chunks(db_engine):
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    # Establish a known starting state before downgrading: this test runs
    # after test_downgrade_base_removes_all_tables in file order, which
    # leaves the schema at "base" (no revisions applied). Alembic can't
    # downgrade to "0001" from "base" — there's nothing to downgrade from —
    # so without this upgrade-to-head, the test fails on an unrelated
    # CommandError depending on execution order. upgrade is a no-op if
    # already at head, so this is always safe to call.
    command.upgrade(alembic_cfg, "head")
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
            note_id = conn.execute(
                sa.text("SELECT id FROM notes WHERE vault_path = 'Note-A.md'")
            ).scalar_one()
            conn.execute(
                sa.text(
                    """
                    INSERT INTO chunks
                        (note_id, chunk_index, start_line, end_line, content,
                         content_with_context, content_hash)
                    VALUES
                        (:note_id, 0, 1, 3,
                         'Terraform drift happens when state diverges.',
                         'Document: Note A\nTerraform drift happens when state diverges.',
                         'chash-a')
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
                sa.text(
                    "TRUNCATE notes, chunks, note_links, index_runs, query_runs "
                    "RESTART IDENTITY CASCADE"
                )
            )
