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
