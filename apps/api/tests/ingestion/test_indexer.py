from app.db.models import IndexRun, Note
from app.ingestion.indexer import run_index
from tests.ingestion.fakes import FakeEmbeddingProvider

NOTE_A = "# Note A\n\n## Section One\n\nContent for section one.\n"


def _write(base, relative_path, content):
    file_path = base / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def test_new_files_are_added_with_chunks_and_embeddings(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()

    result = run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    assert result.files_added == 1
    assert result.status == "success"
    note = db_session.query(Note).filter_by(vault_path="Note-A.md").one()
    assert note.title == "Note A"
    assert len(note.chunks) >= 1
    assert all(c.embedding is not None for c in note.chunks)


def test_second_run_with_no_changes_touches_zero_files(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()

    run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )
    provider.calls.clear()
    second_result = run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    assert second_result.files_added == 0
    assert second_result.files_updated == 0
    assert second_result.files_deleted == 0
    assert provider.calls == []


def test_index_run_row_is_recorded(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()

    run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    run = db_session.query(IndexRun).order_by(IndexRun.id.desc()).first()
    assert run.status == "success"
    assert run.files_added == 1


def test_changed_note_reuses_unchanged_chunk_embeddings(tmp_path, db_session):
    note_v1 = (
        "# Note A\n\n## Section One\n\nOriginal content.\n\n## Section Two\n\nUnchanged content.\n"
    )
    note_v2 = (
        "# Note A\n\n## Section One\n\nEdited content.\n\n## Section Two\n\nUnchanged content.\n"
    )
    _write(tmp_path, "Note-A.md", note_v1)
    provider = FakeEmbeddingProvider()
    run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    note = db_session.query(Note).filter_by(vault_path="Note-A.md").one()
    section_two_before = next(
        c.embedding for c in note.chunks if c.heading_path.endswith("Section Two")
    )

    _write(tmp_path, "Note-A.md", note_v2)
    provider.calls.clear()
    result = run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )

    assert result.files_updated == 1
    db_session.refresh(note)
    section_two_after = next(
        c.embedding for c in note.chunks if c.heading_path.endswith("Section Two")
    )
    # pgvector round-trips embedding columns as numpy arrays; compare as lists so
    # multi-element `==` reduces to a single bool instead of an elementwise array.
    assert list(section_two_after) == list(section_two_before)
    embedded_texts = [text for call in provider.calls for text in call]
    assert not any("Unchanged content." in text for text in embedded_texts)
    assert any("Edited content." in text for text in embedded_texts)


def test_oversized_section_chunks_are_matched_by_heading_and_index_on_rerun(tmp_path, db_session):
    """Regression test: a naive diff keyed by heading_path alone collapses multiple
    chunks that share one heading (produced by the oversized-section fallback) down
    to a single dict entry, losing reuse for every sibling but the last one seen."""
    filler_a = "\n\n".join(
        f"Paragraph A{i} filler text to pad the token count for this test." for i in range(30)
    )
    filler_b = "\n\n".join(
        f"Paragraph B{i} filler text to pad the token count for this test." for i in range(30)
    )
    note_v1 = (
        f"# Note A\n\n## Everything\n\n{filler_a}\n\n{filler_b}\n\n"
        "## Other\n\nOriginal other content.\n"
    )
    note_v2 = (
        f"# Note A\n\n## Everything\n\n{filler_a}\n\n{filler_b}\n\n"
        "## Other\n\nEdited other content.\n"
    )
    _write(tmp_path, "Note-A.md", note_v1)
    provider = FakeEmbeddingProvider()
    run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=100,
        embedding_model="nomic-embed-text",
    )

    note = db_session.query(Note).filter_by(vault_path="Note-A.md").one()
    everything_chunks = sorted(
        (c for c in note.chunks if c.heading_path.endswith("Everything")),
        key=lambda c: c.chunk_index,
    )
    assert (
        len(everything_chunks) > 1
    ), "expected the oversized section to split into multiple chunks"
    embeddings_before = {c.chunk_index: c.embedding for c in everything_chunks}

    _write(tmp_path, "Note-A.md", note_v2)
    provider.calls.clear()
    result = run_index(
        db_session,
        str(tmp_path),
        provider,
        max_section_tokens=100,
        embedding_model="nomic-embed-text",
    )

    assert result.files_updated == 1
    db_session.refresh(note)
    everything_chunks_after = sorted(
        (c for c in note.chunks if c.heading_path.endswith("Everything")),
        key=lambda c: c.chunk_index,
    )
    assert len(everything_chunks_after) == len(everything_chunks)
    for chunk in everything_chunks_after:
        # pgvector round-trips embedding columns as numpy arrays; compare as lists so
        # multi-element `==` reduces to a single bool instead of an elementwise array.
        assert list(chunk.embedding) == list(embeddings_before[chunk.chunk_index]), (
            "every sub-chunk of the unchanged oversized section must reuse its own prior "
            "embedding, not collide with a sibling chunk under the same heading"
        )
    embedded_texts = [text for call in provider.calls for text in call]
    assert not any(
        "filler text" in text for text in embedded_texts
    ), "no Everything sub-chunk should have been re-embedded — only Other actually changed"
    assert any("Edited other content." in text for text in embedded_texts)
