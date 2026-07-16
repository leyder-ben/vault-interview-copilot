"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    op.create_index("ix_chunks_search_vector", "chunks", ["search_vector"], postgresql_using="gin")

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
