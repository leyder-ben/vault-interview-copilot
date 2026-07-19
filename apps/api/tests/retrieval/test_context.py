from datetime import UTC, datetime

from app.db.models import Chunk, Note
from app.retrieval.context import select
from app.retrieval.fusion import FusedResult


def _make_note_and_chunk(db_session, vault_path, heading, content, tags=None):
    note = Note(
        vault_path=vault_path,
        filename=vault_path,
        title=vault_path,
        content_hash=f"hash-{vault_path}-{heading}",
        modified_at=datetime.now(UTC),
        tags=tags,
    )
    db_session.add(note)
    db_session.flush()
    chunk = Chunk(
        note_id=note.id,
        heading_path=heading,
        chunk_index=0,
        start_line=1,
        end_line=5,
        content=content,
        content_with_context=content,
        content_hash=f"chash-{vault_path}-{heading}",
    )
    db_session.add(chunk)
    db_session.flush()
    return chunk.id


def _fused(chunk_id, vault_path, heading_path, rank, score):
    return FusedResult(
        chunk_id=chunk_id,
        vault_path=vault_path,
        heading_path=heading_path,
        fused_rank=rank,
        rrf_score=score,
        fulltext_rank=rank,
        vector_rank=rank,
    )


def test_select_hydrates_content_and_preserves_rank_order(db_session):
    id_a = _make_note_and_chunk(db_session, "A.md", "H1", "content a")
    id_b = _make_note_and_chunk(db_session, "B.md", "H2", "content b")
    db_session.commit()
    fused = [_fused(id_a, "A.md", "H1", 1, 0.05), _fused(id_b, "B.md", "H2", 2, 0.03)]

    result = select(fused, db_session, max_sources=6)

    assert [c.chunk_id for c in result] == [id_a, id_b]
    assert result[0].content == "content a"
    assert result[0].rrf_score == 0.05


def test_select_stops_at_max_sources(db_session):
    ids = [_make_note_and_chunk(db_session, f"N{i}.md", "H", f"content {i}") for i in range(5)]
    db_session.commit()
    fused = [_fused(cid, f"N{i}.md", "H", i + 1, 0.05 - i * 0.001) for i, cid in enumerate(ids)]

    result = select(fused, db_session, max_sources=3)

    assert len(result) == 3


def test_select_caps_chunks_per_note_by_default_to_one(db_session):
    note = Note(
        vault_path="Same.md",
        filename="Same.md",
        title="Same.md",
        content_hash="hash-same",
        modified_at=datetime.now(UTC),
    )
    db_session.add(note)
    db_session.flush()
    chunk_1 = Chunk(
        note_id=note.id,
        heading_path="H1",
        chunk_index=0,
        start_line=1,
        end_line=5,
        content="c1",
        content_with_context="c1",
        content_hash="c1-hash",
    )
    chunk_2 = Chunk(
        note_id=note.id,
        heading_path="H2",
        chunk_index=1,
        start_line=6,
        end_line=10,
        content="c2",
        content_with_context="c2",
        content_hash="c2-hash",
    )
    db_session.add_all([chunk_1, chunk_2])
    db_session.flush()
    db_session.commit()
    fused = [
        _fused(chunk_1.id, "Same.md", "H1", 1, 0.05),
        _fused(chunk_2.id, "Same.md", "H2", 2, 0.04),
    ]

    result = select(fused, db_session, max_sources=6)

    assert len(result) == 1
    assert result[0].chunk_id == chunk_1.id


def test_select_allows_two_chunks_per_project_tagged_note(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "personal_project_tags", ["meridian"])
    note = Note(
        vault_path="Project.md",
        filename="Project.md",
        title="Project.md",
        content_hash="hash-project",
        modified_at=datetime.now(UTC),
        tags=["meridian"],
    )
    db_session.add(note)
    db_session.flush()
    chunk_1 = Chunk(
        note_id=note.id,
        heading_path="H1",
        chunk_index=0,
        start_line=1,
        end_line=5,
        content="c1",
        content_with_context="c1",
        content_hash="p1-hash",
    )
    chunk_2 = Chunk(
        note_id=note.id,
        heading_path="H2",
        chunk_index=1,
        start_line=6,
        end_line=10,
        content="c2",
        content_with_context="c2",
        content_hash="p2-hash",
    )
    db_session.add_all([chunk_1, chunk_2])
    db_session.flush()
    db_session.commit()
    fused = [
        _fused(chunk_1.id, "Project.md", "H1", 1, 0.05),
        _fused(chunk_2.id, "Project.md", "H2", 2, 0.04),
    ]

    result = select(fused, db_session, max_sources=6)

    assert len(result) == 2


def test_select_always_includes_first_chunk_even_if_it_exceeds_budget(db_session):
    big_content = "word " * 5000
    chunk_id = _make_note_and_chunk(db_session, "Big.md", "H", big_content)
    db_session.commit()
    fused = [_fused(chunk_id, "Big.md", "H", 1, 0.05)]

    result = select(fused, db_session, max_sources=6, budget_tokens=10)

    assert len(result) == 1


def test_select_skips_later_chunks_that_would_exceed_budget(db_session):
    # "short" is exactly 1 token under cl100k_base (verified: tiktoken.get_encoding
    # ("cl100k_base").encode("short") == [8846]). budget_tokens=1 means the forced
    # first chunk (1 token) exactly fills the budget, so every subsequent 1-token
    # chunk pushes the running total over it (1+1=2 > 1) and gets skipped.
    small_content = "short"
    ids = [_make_note_and_chunk(db_session, f"S{i}.md", "H", small_content) for i in range(20)]
    db_session.commit()
    fused = [_fused(cid, f"S{i}.md", "H", i + 1, 0.05 - i * 0.001) for i, cid in enumerate(ids)]

    result = select(fused, db_session, max_sources=20, budget_tokens=1)

    assert len(result) == 1


def test_select_empty_fused_results_returns_empty(db_session):
    assert select([], db_session, max_sources=6) == []
