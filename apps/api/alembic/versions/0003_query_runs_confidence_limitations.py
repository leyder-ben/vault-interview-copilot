"""query_runs.confidence and query_runs.limitations

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("query_runs", sa.Column("confidence", sa.Text(), nullable=True))
    op.add_column("query_runs", sa.Column("limitations", ARRAY(sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("query_runs", "limitations")
    op.drop_column("query_runs", "confidence")
