from app.ingestion.chunker import chunk_note
from app.ingestion.parser import parse_note

SMALL_NOTE = """# Fundamentals

## Overview

Short paragraph, well under the token budget.
"""


def test_small_section_becomes_single_chunk():
    parsed = parse_note(SMALL_NOTE, fallback_title="fallback.md")
    chunks = chunk_note(
        parsed,
        title="Fundamentals",
        vault_path="Fundamentals.md",
        max_section_tokens=400,
    )
    overview_chunks = [c for c in chunks if c.heading_path and c.heading_path.endswith("Overview")]
    assert len(overview_chunks) == 1


def test_content_with_context_includes_metadata_header():
    parsed = parse_note(SMALL_NOTE, fallback_title="fallback.md")
    chunks = chunk_note(
        parsed,
        title="Fundamentals",
        vault_path="Fundamentals.md",
        max_section_tokens=400,
    )
    chunk = chunks[0]
    assert chunk.content_with_context.startswith("Document: Fundamentals\n")
    assert "Path: Fundamentals.md" in chunk.content_with_context
    assert chunk.content in chunk.content_with_context


def test_oversized_section_falls_back_to_paragraph_splitting():
    long_paragraph = "\n\n".join(
        f"Paragraph {i} with some filler words to pad the token count for this test."
        for i in range(80)
    )
    note_text = f"# Big Note\n\n## Everything\n\n{long_paragraph}\n"
    parsed = parse_note(note_text, fallback_title="fallback.md")
    chunks = chunk_note(parsed, title="Big Note", vault_path="Big-Note.md", max_section_tokens=100)
    everything_chunks = [
        c for c in chunks if c.heading_path and c.heading_path.endswith("Everything")
    ]
    assert len(everything_chunks) > 1


def test_fallback_splitting_never_cuts_inside_code_block():
    filler = "\n\n".join(f"Line {i} of filler text to pad token count." for i in range(40))
    note_text = (
        "# Big Note\n\n## Everything\n\n"
        f"{filler}\n\n"
        "```python\n"
        "def example():\n"
        "    return 1\n"
        "```\n\n"
        f"{filler}\n"
    )
    parsed = parse_note(note_text, fallback_title="fallback.md")
    chunks = chunk_note(parsed, title="Big Note", vault_path="Big-Note.md", max_section_tokens=80)
    for chunk in chunks:
        if "def example()" in chunk.content:
            assert chunk.content.count("```") == 2


def test_content_hash_is_stable_for_identical_chunk_content():
    parsed = parse_note(SMALL_NOTE, fallback_title="fallback.md")
    chunks_a = chunk_note(
        parsed,
        title="Fundamentals",
        vault_path="Fundamentals.md",
        max_section_tokens=400,
    )
    chunks_b = chunk_note(
        parsed,
        title="Fundamentals",
        vault_path="Fundamentals.md",
        max_section_tokens=400,
    )
    assert chunks_a[0].content_hash == chunks_b[0].content_hash


def test_chunk_index_is_sequential_across_sections():
    parsed = parse_note(SMALL_NOTE, fallback_title="fallback.md")
    chunks = chunk_note(
        parsed,
        title="Fundamentals",
        vault_path="Fundamentals.md",
        max_section_tokens=400,
    )
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
