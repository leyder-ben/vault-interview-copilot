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
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
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
