# Phase 1: Vault Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Index `sample-vault/` into Postgres (notes, heading-aware chunks, embeddings) incrementally, provable by running the indexer twice against an unchanged vault with the second run touching zero files.

**Architecture:** New `app/ingestion/` module (scanner → parser → chunker → embeddings → indexer) orchestrated by a single `run_index()` function, triggered via a CLI entry point. A read-only `GET /api/index/status` endpoint exposes the latest run. Full design: `docs/superpowers/specs/2026-07-16-phase-1-vault-indexing-design.md`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, httpx, PyYAML, tiktoken, pytest (existing stack from Phase 0, plus PyYAML + tiktoken new this phase).

## Global Constraints

- Ignore list (exact folder names, never a blanket `_*` pattern): `.git`, `.obsidian`, `.trash`, `_Templates`, `_Agents`, `_Skills`, `_Workflows`, `_About-Ben`. `_Source-Docs/` and `00-Inbox/` are **not** ignored.
- Content hashing uses `sha256` throughout (notes and chunks).
- `EMBEDDING_DIM = 768` (already defined in `app/db/models.py` — vectors must match this dimension).
- Oversized-section threshold is a named config field, `chunk_max_section_tokens`, default `400`, not a bare code constant.
- No `settings` DB table this phase — the embedding provider's `base_url` is resolved once, at construction time, in `cli.py`, from `settings.ollama_workstation_url`. `OllamaEmbeddingProvider` itself never reads `settings`.
- No `POST /api/index/run` HTTP endpoint this phase — only `GET /api/index/status` (read-only) and the CLI trigger.
- Renames are delete-plus-add — no rename detection.
- New dependencies: `tiktoken>=0.8,<0.9`, `PyYAML>=6.0,<7`.
- Ruff config (`line-length = 100`, `target-version = "py312"`) and existing `pytest`/`ruff` conventions apply to all new code.
- CI (`.github/workflows/ci.yml`) already runs `ruff format --check`, `ruff check`, `pytest -v` against a real `pgvector/pgvector:pg16` service container — no changes needed to CI config itself, new tests just need to pass under it.

---

### Task 1: Config additions and new dependencies

**Files:**
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/requirements.txt`
- Modify: `.env.example`
- Test: `apps/api/tests/test_config.py`

**Interfaces:**
- Produces: `settings.chunk_max_section_tokens: int` (default `400`), consumed by the chunker (Task 4) and indexer (Task 6+).

- [x] **Step 1: Write the failing test**

Add to `apps/api/tests/test_config.py` (append to the existing file, don't remove the current tests):

```python
def test_chunk_max_section_tokens_default():
    settings = Settings(_env_file=None)
    assert settings.chunk_max_section_tokens == 400


def test_chunk_max_section_tokens_env_override(monkeypatch):
    monkeypatch.setenv("CHUNK_MAX_SECTION_TOKENS", "250")
    settings = Settings(_env_file=None)
    assert settings.chunk_max_section_tokens == 250
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError` or `ValidationError`, `chunk_max_section_tokens` not defined on `Settings`.

- [x] **Step 3: Add the config field**

In `apps/api/app/core/config.py`, add one field to the `Settings` class (after `embedding_model`):

```python
    chunk_max_section_tokens: int = 400
```

- [x] **Step 4: Add new dependencies to requirements.txt**

Append to `apps/api/requirements.txt`:

```
tiktoken>=0.8,<0.9
PyYAML>=6.0,<7
```

Run: `cd apps/api && pip install -r requirements.txt`

- [x] **Step 5: Document the new env var**

In `.env.example`, add a new section after `# Models`:

```
# Chunking
# Oversized-section fallback threshold (tokens, tiktoken cl100k_base
# approximation). Tune from evaluation results without a code change.
CHUNK_MAX_SECTION_TOKENS=400
```

- [x] **Step 6: Run test to verify it passes**

Run: `cd apps/api && pytest tests/test_config.py -v`
Expected: PASS (all tests in the file, old and new)

- [x] **Step 7: Commit**

```bash
git add apps/api/app/core/config.py apps/api/requirements.txt apps/api/tests/test_config.py .env.example
git commit -m "feat(config): add chunk_max_section_tokens and ingestion dependencies"
```

---

### Task 2: File scanner and ignore patterns

**Files:**
- Create: `apps/api/app/ingestion/__init__.py`
- Create: `apps/api/app/ingestion/scanner.py`
- Create: `apps/api/tests/ingestion/__init__.py`
- Test: `apps/api/tests/ingestion/test_scanner.py`

**Interfaces:**
- Produces: `ScannedFile(vault_path: str, content: str, content_hash: str, modified_at: datetime)`, `compute_content_hash(content: str) -> str`, `scan_vault(vault_path: str | Path) -> list[ScannedFile]`, `IGNORED_DIRS: set[str]`. Consumed by the indexer (Task 6).

- [x] **Step 1: Write the failing test**

Create `apps/api/app/ingestion/__init__.py` (empty) and `apps/api/tests/ingestion/__init__.py` (empty).

Create `apps/api/tests/ingestion/test_scanner.py`:

```python
from datetime import datetime

from app.ingestion.scanner import compute_content_hash, scan_vault


def _write(base, relative_path, content="# Title\n\nBody text.\n"):
    file_path = base / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def test_scan_returns_indexable_markdown_files(tmp_path):
    _write(tmp_path, "00-Inbox/note.md")
    _write(tmp_path, "02-Technical-Reference/Terraform.md")
    files = scan_vault(tmp_path)
    paths = {f.vault_path for f in files}
    assert paths == {"00-Inbox/note.md", "02-Technical-Reference/Terraform.md"}


def test_scan_ignores_named_folders(tmp_path):
    _write(tmp_path, "_Templates/Story-Template.md")
    _write(tmp_path, ".obsidian/workspace.md")
    _write(tmp_path, "keep/Real-Note.md")
    files = scan_vault(tmp_path)
    paths = {f.vault_path for f in files}
    assert paths == {"keep/Real-Note.md"}


def test_scan_does_not_ignore_source_docs_folder(tmp_path):
    _write(tmp_path, "03-Projects/Meridian/_Source-Docs/Transcript.md")
    files = scan_vault(tmp_path)
    assert {f.vault_path for f in files} == {"03-Projects/Meridian/_Source-Docs/Transcript.md"}


def test_scan_ignores_nested_occurrences_of_ignored_folders(tmp_path):
    _write(tmp_path, "03-Projects/Meridian/_Templates/nested.md")
    files = scan_vault(tmp_path)
    assert files == []


def test_content_hash_is_stable_for_identical_content():
    assert compute_content_hash("same text") == compute_content_hash("same text")


def test_content_hash_differs_for_different_content():
    assert compute_content_hash("a") != compute_content_hash("b")


def test_scanned_file_has_timezone_aware_modified_at(tmp_path):
    _write(tmp_path, "note.md")
    files = scan_vault(tmp_path)
    assert isinstance(files[0].modified_at, datetime)
    assert files[0].modified_at.tzinfo is not None
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/ingestion/test_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.scanner'`

- [x] **Step 3: Write the implementation**

Create `apps/api/app/ingestion/scanner.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".obsidian",
    ".trash",
    "_Templates",
    "_Agents",
    "_Skills",
    "_Workflows",
    "_About-Ben",
}


@dataclass
class ScannedFile:
    vault_path: str
    content: str
    content_hash: str
    modified_at: datetime


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _is_ignored(relative_parts: tuple[str, ...]) -> bool:
    return any(part in IGNORED_DIRS for part in relative_parts[:-1])


def scan_vault(vault_path: str | Path) -> list[ScannedFile]:
    root = Path(vault_path)
    results: list[ScannedFile] = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if _is_ignored(relative.parts):
            continue
        content = path.read_text(encoding="utf-8")
        stat = path.stat()
        results.append(
            ScannedFile(
                vault_path=relative.as_posix(),
                content=content,
                content_hash=compute_content_hash(content),
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
        )
    return results
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/ingestion/test_scanner.py -v`
Expected: PASS (7 tests)

- [x] **Step 5: Commit**

```bash
git add apps/api/app/ingestion/__init__.py apps/api/app/ingestion/scanner.py apps/api/tests/ingestion/__init__.py apps/api/tests/ingestion/test_scanner.py
git commit -m "feat(ingestion): add vault file scanner with ignore-pattern handling"
```

---

### Task 3: Markdown/frontmatter parser

**Files:**
- Create: `apps/api/app/ingestion/parser.py`
- Test: `apps/api/tests/ingestion/test_parser.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Section(heading_path: str | None, level: int, start_line: int, end_line: int, content: str, code_block_ranges: list[tuple[int, int]])`, `Link(target: str, link_text: str | None, link_type: str)`, `ParsedNote(frontmatter: dict, title: str, tags: list[str], aliases: list[str], sections: list[Section], links: list[Link])`, `parse_note(raw_text: str, *, fallback_title: str) -> ParsedNote`. Consumed by the chunker (Task 4) and indexer (Task 6+).

- [x] **Step 1: Write the failing test**

Create `apps/api/tests/ingestion/test_parser.py`:

```python
from app.ingestion.parser import parse_note

FRONTMATTER_NOTE = """---
title: Terraform Fundamentals
tags: [terraform, iac]
aliases: [tf-fundamentals]
---

# Terraform Fundamentals

## State Management

### Drift Management

State drift happens when real infra diverges from the state file.

```hcl
resource "aws_instance" "example" {
  ami = "ami-123456"
}
```

See [[Meridian-Tool-Stack-Articulation]] and [Terraform docs](https://terraform.io).
"""


def test_parses_frontmatter_fields():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    assert parsed.title == "Terraform Fundamentals"
    assert parsed.tags == ["terraform", "iac"]
    assert parsed.aliases == ["tf-fundamentals"]


def test_builds_heading_ancestry():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    heading_paths = [s.heading_path for s in parsed.sections]
    assert "Terraform Fundamentals > State Management > Drift Management" in heading_paths


def test_code_block_is_captured_within_its_section():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    drift_section = next(
        s for s in parsed.sections if s.heading_path and s.heading_path.endswith("Drift Management")
    )
    assert drift_section.code_block_ranges, "expected the hcl fence to be captured"
    start, end = drift_section.code_block_ranges[0]
    fenced_text = "\n".join(FRONTMATTER_NOTE.splitlines()[start - 1 : end])
    assert 'resource "aws_instance"' in fenced_text


def test_extracts_wikilinks_and_markdown_links():
    parsed = parse_note(FRONTMATTER_NOTE, fallback_title="fallback.md")
    wikilinks = [link for link in parsed.links if link.link_type == "wikilink"]
    mdlinks = [link for link in parsed.links if link.link_type == "markdown"]
    assert wikilinks[0].target == "Meridian-Tool-Stack-Articulation"
    assert mdlinks[0].target == "https://terraform.io"


def test_note_without_headings_becomes_single_section():
    parsed = parse_note("Just a quick capture, no structure yet.\n", fallback_title="Quick-Note.md")
    assert len(parsed.sections) == 1
    assert parsed.sections[0].heading_path is None


def test_title_falls_back_to_first_heading_then_filename():
    parsed = parse_note("# My Heading\n\nBody\n", fallback_title="fallback.md")
    assert parsed.title == "My Heading"
    parsed_no_heading = parse_note("Body only\n", fallback_title="fallback.md")
    assert parsed_no_heading.title == "fallback.md"


def test_heading_inside_code_block_is_not_treated_as_a_heading():
    note = "# Real Heading\n\n```text\n# not a heading\n```\n\nBody after.\n"
    parsed = parse_note(note, fallback_title="fallback.md")
    heading_paths = {s.heading_path for s in parsed.sections}
    assert heading_paths == {"Real Heading"}
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/ingestion/test_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.parser'`

- [x] **Step 3: Write the implementation**

Create `apps/api/app/ingestion/parser.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE_RE = re.compile(r"^(```+|~~~+)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_MDLINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)")


@dataclass
class Section:
    heading_path: str | None
    level: int
    start_line: int
    end_line: int
    content: str
    code_block_ranges: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class Link:
    target: str
    link_text: str | None
    link_type: str  # "wikilink" or "markdown"


@dataclass
class ParsedNote:
    frontmatter: dict
    title: str
    tags: list[str]
    aliases: list[str]
    sections: list[Section]
    links: list[Link]


def _split_frontmatter(raw_text: str) -> tuple[dict, int]:
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            block = "\n".join(lines[1:i])
            data = yaml.safe_load(block) or {}
            return data, i + 1
    return {}, 0


def _extract_links(text: str) -> list[Link]:
    links: list[Link] = []
    for match in _WIKILINK_RE.finditer(text):
        target, alias = match.group(1), match.group(2)
        links.append(
            Link(target=target.strip(), link_text=(alias.strip() if alias else None), link_type="wikilink")
        )
    for match in _MDLINK_RE.finditer(text):
        text_part, target = match.group(1), match.group(2)
        links.append(Link(target=target.strip(), link_text=text_part.strip(), link_type="markdown"))
    return links


def parse_note(raw_text: str, *, fallback_title: str) -> ParsedNote:
    frontmatter, body_start_index = _split_frontmatter(raw_text)
    all_lines = raw_text.splitlines()

    fence_stack: list[str] = []
    code_block_ranges: list[tuple[int, int]] = []
    fence_open_line: int | None = None

    heading_stack: list[tuple[int, str]] = []
    sections: list[Section] = []
    current_start = body_start_index + 1
    current_heading_path: str | None = None
    current_level = 0

    def close_section(end_line: int) -> None:
        if end_line < current_start:
            return
        content = "\n".join(all_lines[current_start - 1 : end_line])
        if content.strip() == "":
            return
        sections.append(
            Section(
                heading_path=current_heading_path,
                level=current_level,
                start_line=current_start,
                end_line=end_line,
                content=content,
                code_block_ranges=[
                    (s, e) for s, e in code_block_ranges if s >= current_start and e <= end_line
                ],
            )
        )

    for idx in range(body_start_index, len(all_lines)):
        line_number = idx + 1
        line = all_lines[idx]

        fence_match = _FENCE_RE.match(line.strip())
        if fence_match:
            marker = fence_match.group(1)[0] * 3
            if fence_stack and fence_stack[-1] == marker:
                fence_stack.pop()
                code_block_ranges.append((fence_open_line, line_number))
                fence_open_line = None
            elif not fence_stack:
                fence_stack.append(marker)
                fence_open_line = line_number
            continue

        if fence_stack:
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            close_section(line_number - 1)
            level = len(heading_match.group(1))
            title = heading_match.group(2)
            heading_stack = [h for h in heading_stack if h[0] < level]
            heading_stack.append((level, title))
            current_heading_path = " > ".join(t for _, t in heading_stack)
            current_level = level
            current_start = line_number

    close_section(len(all_lines))

    tags = list(frontmatter.get("tags") or [])
    aliases = list(frontmatter.get("aliases") or [])
    title = frontmatter.get("title") or next(
        (s.heading_path for s in sections if s.level == 1 and s.heading_path), fallback_title
    )
    links = _extract_links("\n".join(all_lines[body_start_index:]))

    return ParsedNote(
        frontmatter=frontmatter,
        title=title,
        tags=tags,
        aliases=aliases,
        sections=sections,
        links=links,
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/ingestion/test_parser.py -v`
Expected: PASS (7 tests)

- [x] **Step 5: Commit**

```bash
git add apps/api/app/ingestion/parser.py apps/api/tests/ingestion/test_parser.py
git commit -m "feat(ingestion): add heading-aware markdown/frontmatter parser"
```

---

### Task 4: Heading-aware chunker

**Files:**
- Create: `apps/api/app/ingestion/chunker.py`
- Test: `apps/api/tests/ingestion/test_chunker.py`

**Interfaces:**
- Consumes: `ParsedNote`, `Section` from `app.ingestion.parser` (Task 3).
- Produces: `ChunkData(heading_path: str | None, chunk_index: int, start_line: int, end_line: int, content: str, content_with_context: str, token_count: int, content_hash: str)`, `chunk_note(parsed: ParsedNote, *, title: str, vault_path: str, max_section_tokens: int) -> list[ChunkData]`. Consumed by the indexer (Task 6+).

- [x] **Step 1: Write the failing test**

Create `apps/api/tests/ingestion/test_chunker.py`:

```python
from app.ingestion.chunker import chunk_note
from app.ingestion.parser import parse_note

SMALL_NOTE = """# Fundamentals

## Overview

Short paragraph, well under the token budget.
"""


def test_small_section_becomes_single_chunk():
    parsed = parse_note(SMALL_NOTE, fallback_title="fallback.md")
    chunks = chunk_note(parsed, title="Fundamentals", vault_path="Fundamentals.md", max_section_tokens=400)
    overview_chunks = [c for c in chunks if c.heading_path and c.heading_path.endswith("Overview")]
    assert len(overview_chunks) == 1


def test_content_with_context_includes_metadata_header():
    parsed = parse_note(SMALL_NOTE, fallback_title="fallback.md")
    chunks = chunk_note(parsed, title="Fundamentals", vault_path="Fundamentals.md", max_section_tokens=400)
    chunk = chunks[0]
    assert chunk.content_with_context.startswith("Document: Fundamentals\n")
    assert "Path: Fundamentals.md" in chunk.content_with_context
    assert chunk.content in chunk.content_with_context


def test_oversized_section_falls_back_to_paragraph_splitting():
    long_paragraph = "\n\n".join(
        f"Paragraph {i} with some filler words to pad the token count for this test." for i in range(80)
    )
    note_text = f"# Big Note\n\n## Everything\n\n{long_paragraph}\n"
    parsed = parse_note(note_text, fallback_title="fallback.md")
    chunks = chunk_note(parsed, title="Big Note", vault_path="Big-Note.md", max_section_tokens=100)
    everything_chunks = [c for c in chunks if c.heading_path and c.heading_path.endswith("Everything")]
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
    chunks_a = chunk_note(parsed, title="Fundamentals", vault_path="Fundamentals.md", max_section_tokens=400)
    chunks_b = chunk_note(parsed, title="Fundamentals", vault_path="Fundamentals.md", max_section_tokens=400)
    assert chunks_a[0].content_hash == chunks_b[0].content_hash


def test_chunk_index_is_sequential_across_sections():
    parsed = parse_note(SMALL_NOTE, fallback_title="fallback.md")
    chunks = chunk_note(parsed, title="Fundamentals", vault_path="Fundamentals.md", max_section_tokens=400)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/ingestion/test_chunker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.chunker'`

- [x] **Step 3: Write the implementation**

Create `apps/api/app/ingestion/chunker.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import tiktoken

from app.ingestion.parser import ParsedNote, Section

_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class ChunkData:
    heading_path: str | None
    chunk_index: int
    start_line: int
    end_line: int
    content: str
    content_with_context: str
    token_count: int
    content_hash: str


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_context_header(*, title: str, vault_path: str, heading_path: str | None, tags: list[str]) -> str:
    return (
        f"Document: {title}\n"
        f"Path: {vault_path}\n"
        f"Section: {heading_path or title}\n"
        f"Tags: {', '.join(tags)}\n\n"
    )


def _paragraphs(section: Section) -> list[tuple[int, int, str]]:
    """(start_offset, end_offset, text) paragraphs, 0-indexed relative to section.start_line."""
    lines = section.content.splitlines()
    paragraphs: list[tuple[int, int, str]] = []
    current: list[str] = []
    start = 0
    for offset, line in enumerate(lines):
        if line.strip() == "" and current:
            paragraphs.append((start, offset - 1, "\n".join(current)))
            current = []
        else:
            if not current:
                start = offset
            current.append(line)
    if current:
        paragraphs.append((start, len(lines) - 1, "\n".join(current)))
    return paragraphs


def _merge_across_code_blocks(
    paragraphs: list[tuple[int, int, str]], section: Section
) -> list[tuple[int, int, str]]:
    """Merge adjacent paragraphs so no resulting unit's boundary falls inside a code block."""
    protected = [(s - section.start_line, e - section.start_line) for s, e in section.code_block_ranges]

    def inside_open_code_block(offset: int) -> bool:
        return any(cb_start <= offset < cb_end for cb_start, cb_end in protected)

    merged: list[tuple[int, int, str]] = []
    buffer: tuple[int, int, str] | None = None
    for start, end, text in paragraphs:
        buffer = (start, end, text) if buffer is None else (buffer[0], end, buffer[2] + "\n\n" + text)
        if not inside_open_code_block(buffer[1]):
            merged.append(buffer)
            buffer = None
    if buffer is not None:
        merged.append(buffer)
    return merged


def _pack_by_token_budget(units: list[tuple[int, int, str]], max_tokens: int) -> list[tuple[int, int, str]]:
    packed: list[tuple[int, int, str]] = []
    buffer: tuple[int, int, str] | None = None
    for start, end, text in units:
        if buffer is None:
            buffer = (start, end, text)
            continue
        candidate_text = buffer[2] + "\n\n" + text
        if _count_tokens(candidate_text) > max_tokens:
            packed.append(buffer)
            buffer = (start, end, text)
        else:
            buffer = (buffer[0], end, candidate_text)
    if buffer is not None:
        packed.append(buffer)
    return packed


def _split_oversized_section(section: Section, max_tokens: int) -> list[tuple[int, int, str]]:
    paragraphs = _paragraphs(section)
    units = _merge_across_code_blocks(paragraphs, section)
    packed = _pack_by_token_budget(units, max_tokens)
    return [(section.start_line + s, section.start_line + e, text) for s, e, text in packed]


def chunk_note(
    parsed: ParsedNote,
    *,
    title: str,
    vault_path: str,
    max_section_tokens: int,
) -> list[ChunkData]:
    chunks: list[ChunkData] = []
    chunk_index = 0
    for section in parsed.sections:
        if _count_tokens(section.content) <= max_section_tokens:
            pieces = [(section.start_line, section.end_line, section.content)]
        else:
            pieces = _split_oversized_section(section, max_section_tokens)

        for start_line, end_line, content in pieces:
            header = _build_context_header(
                title=title, vault_path=vault_path, heading_path=section.heading_path, tags=parsed.tags
            )
            chunks.append(
                ChunkData(
                    heading_path=section.heading_path,
                    chunk_index=chunk_index,
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                    content_with_context=header + content,
                    token_count=_count_tokens(content),
                    content_hash=_content_hash(content),
                )
            )
            chunk_index += 1
    return chunks
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/ingestion/test_chunker.py -v`
Expected: PASS (6 tests)

- [x] **Step 5: Commit**

```bash
git add apps/api/app/ingestion/chunker.py apps/api/tests/ingestion/test_chunker.py
git commit -m "feat(ingestion): add heading-aware chunker with oversized-section fallback"
```

---

### Task 5: Embedding provider

**Files:**
- Create: `apps/api/app/ingestion/embeddings.py`
- Create: `apps/api/tests/ingestion/fakes.py`
- Test: `apps/api/tests/ingestion/test_embeddings.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `EmbeddingProvider` (Protocol, method `embed_batch(texts: list[str]) -> list[list[float]]`), `OllamaEmbeddingProvider(base_url: str, model: str = "nomic-embed-text", timeout: float = 60.0, client: httpx.Client | None = None)`, `FakeEmbeddingProvider(dim: int = 768)` (test double with a `.calls: list[list[str]]` attribute recording every batch it was asked to embed). Consumed by the indexer (Task 6+) and its tests.

- [x] **Step 1: Write the failing test**

Create `apps/api/tests/ingestion/test_embeddings.py`:

```python
import json

import httpx
import pytest

from app.ingestion.embeddings import OllamaEmbeddingProvider


def _client_with_response(expected_embeddings):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        assert body["model"] == "nomic-embed-text"
        assert isinstance(body["input"], list)
        return httpx.Response(200, json={"embeddings": expected_embeddings})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_embed_batch_returns_vectors_in_order():
    expected = [[0.1, 0.2], [0.3, 0.4]]
    client = _client_with_response(expected)
    provider = OllamaEmbeddingProvider(base_url="http://workstation:11434", client=client)
    result = provider.embed_batch(["chunk one", "chunk two"])
    assert result == expected


def test_embed_batch_with_empty_list_makes_no_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not be called")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(base_url="http://workstation:11434", client=client)
    assert provider.embed_batch([]) == []


def test_embed_batch_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaEmbeddingProvider(base_url="http://workstation:11434", client=client)
    with pytest.raises(httpx.HTTPStatusError):
        provider.embed_batch(["text"])
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/ingestion/test_embeddings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.embeddings'`

- [x] **Step 3: Write the implementation**

Create `apps/api/app/ingestion/embeddings.py`:

```python
from __future__ import annotations

from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingProvider:
    def __init__(
        self,
        base_url: str,
        model: str = "nomic-embed-text",
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": texts},
        )
        response.raise_for_status()
        return response.json()["embeddings"]
```

Create `apps/api/tests/ingestion/fakes.py` (test double, not shipped application code):

```python
from __future__ import annotations

import hashlib


class FakeEmbeddingProvider:
    """Deterministic embedding provider for tests — no live Ollama dependency."""

    def __init__(self, dim: int = 768):
        self._dim = dim
        self.calls: list[list[str]] = []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [digest[i % len(digest)] / 255.0 for i in range(self._dim)]
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/ingestion/test_embeddings.py -v`
Expected: PASS (3 tests)

- [x] **Step 5: Commit**

```bash
git add apps/api/app/ingestion/embeddings.py apps/api/tests/ingestion/fakes.py apps/api/tests/ingestion/test_embeddings.py
git commit -m "feat(ingestion): add batch Ollama embedding provider and test fake"
```

---

### Task 6: DB session test fixture + indexer new/unchanged handling

**Files:**
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/app/ingestion/indexer.py`
- Test: `apps/api/tests/ingestion/test_indexer.py`

**Interfaces:**
- Consumes: `ScannedFile`, `scan_vault` (Task 2); `ParsedNote`, `parse_note` (Task 3); `ChunkData`, `chunk_note` (Task 4); `EmbeddingProvider` (Task 5); `Note`, `Chunk`, `NoteLink`, `IndexRun` SQLAlchemy models (`app.db.models`, already exist).
- Produces: `IndexRunResult(status: str, files_scanned: int, files_added: int, files_updated: int, files_deleted: int, chunks_created: int, chunks_deleted: int, errors: list[dict])`, `run_index(session: Session, vault_path: str, embedding_provider: EmbeddingProvider, *, max_section_tokens: int, embedding_model: str) -> IndexRunResult`. Consumed by Tasks 7, 8, 9, 10, 11, 12.
- New test fixture `db_session` (function-scoped, migrated + truncated between tests), consumed by all subsequent DB-touching tests.

- [x] **Step 1: Add the `db_session` fixture**

Modify `apps/api/tests/conftest.py` to the full contents:

```python
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

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
            sa.text("TRUNCATE notes, chunks, note_links, index_runs, query_runs RESTART IDENTITY CASCADE")
        )
```

- [x] **Step 2: Write the failing test**

Create `apps/api/tests/ingestion/test_indexer.py`:

```python
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
        db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
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

    run_index(db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text")
    provider.calls.clear()
    second_result = run_index(
        db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    assert second_result.files_added == 0
    assert second_result.files_updated == 0
    assert second_result.files_deleted == 0
    assert provider.calls == []


def test_index_run_row_is_recorded(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()

    run_index(db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    run = db_session.query(IndexRun).order_by(IndexRun.id.desc()).first()
    assert run.status == "success"
    assert run.files_added == 1
```

- [x] **Step 3: Run test to verify it fails**

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.indexer'`

- [x] **Step 4: Write the implementation**

Create `apps/api/app/ingestion/indexer.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Chunk, IndexRun, Note, NoteLink
from app.ingestion.chunker import chunk_note
from app.ingestion.embeddings import EmbeddingProvider
from app.ingestion.parser import parse_note
from app.ingestion.scanner import scan_vault


@dataclass
class IndexRunResult:
    status: str
    files_scanned: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    chunks_created: int = 0
    chunks_deleted: int = 0
    errors: list[dict] = field(default_factory=list)


def _title_from_path(vault_path: str) -> str:
    return vault_path.rsplit("/", 1)[-1]


def run_index(
    session: Session,
    vault_path: str,
    embedding_provider: EmbeddingProvider,
    *,
    max_section_tokens: int,
    embedding_model: str,
) -> IndexRunResult:
    started_at = datetime.now(timezone.utc)

    try:
        scanned_files = scan_vault(vault_path)
    except OSError as exc:
        index_run = IndexRun(
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            status="failed",
            errors_json={"errors": [{"vault_path": None, "error": str(exc)}]},
        )
        session.add(index_run)
        session.commit()
        return IndexRunResult(status="failed", errors=[{"vault_path": None, "error": str(exc)}])

    result = IndexRunResult(status="success", files_scanned=len(scanned_files))
    existing_notes = {note.vault_path: note for note in session.query(Note).all()}

    for scanned in scanned_files:
        try:
            existing = existing_notes.get(scanned.vault_path)
            if existing is not None and existing.content_hash == scanned.content_hash:
                continue

            parsed = parse_note(scanned.content, fallback_title=_title_from_path(scanned.vault_path))
            chunk_data = chunk_note(
                parsed, title=parsed.title, vault_path=scanned.vault_path, max_section_tokens=max_section_tokens
            )
            vectors = embedding_provider.embed_batch([c.content_with_context for c in chunk_data])

            if existing is None:
                note = Note(
                    vault_path=scanned.vault_path,
                    filename=scanned.vault_path.rsplit("/", 1)[-1],
                    title=parsed.title,
                    content_hash=scanned.content_hash,
                    modified_at=scanned.modified_at,
                    frontmatter_json=parsed.frontmatter,
                    tags=parsed.tags,
                    aliases=parsed.aliases,
                    indexed_at=datetime.now(timezone.utc),
                    embedding_version=embedding_model,
                )
                session.add(note)
                result.files_added += 1
            else:
                note = existing
                note.content_hash = scanned.content_hash
                note.modified_at = scanned.modified_at
                note.frontmatter_json = parsed.frontmatter
                note.tags = parsed.tags
                note.aliases = parsed.aliases
                note.indexed_at = datetime.now(timezone.utc)
                note.embedding_version = embedding_model
                result.files_updated += 1

            note.chunks = [
                Chunk(
                    heading_path=c.heading_path,
                    chunk_index=c.chunk_index,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    content=c.content,
                    content_with_context=c.content_with_context,
                    token_count=c.token_count,
                    embedding=vector,
                    content_hash=c.content_hash,
                )
                for c, vector in zip(chunk_data, vectors)
            ]
            note.links = [
                NoteLink(target_path=link.target, link_text=link.link_text, link_type=link.link_type)
                for link in parsed.links
            ]
            result.chunks_created += len(chunk_data)
        except Exception as exc:  # noqa: BLE001
            result.errors.append({"vault_path": scanned.vault_path, "error": str(exc)})

    if result.errors:
        result.status = "partial"

    index_run = IndexRun(
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        status=result.status,
        files_scanned=result.files_scanned,
        files_added=result.files_added,
        files_updated=result.files_updated,
        files_deleted=result.files_deleted,
        chunks_created=result.chunks_created,
        chunks_deleted=result.chunks_deleted,
        errors_json={"errors": result.errors} if result.errors else None,
    )
    session.add(index_run)
    session.commit()
    return result
```

- [x] **Step 5: Run test to verify it passes**

Requires a real Postgres reachable at `settings.database_url` — start it first if not already running: `docker compose up -d postgres` (from repo root).

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py -v`
Expected: PASS (3 tests)

- [x] **Step 6: Commit**

```bash
git add apps/api/tests/conftest.py apps/api/app/ingestion/indexer.py apps/api/tests/ingestion/test_indexer.py
git commit -m "feat(ingestion): add indexer with new-file and unchanged-skip handling"
```

---

### Task 7: Changed-file diffing and chunk-level embedding reuse

**Files:**
- Modify: `apps/api/app/ingestion/indexer.py`
- Test: `apps/api/tests/ingestion/test_indexer.py` (append)

**Interfaces:**
- Consumes: `Chunk` model instances' `.embedding`/`.content_hash`/`.heading_path` (already exist on the model from Phase 0).
- Produces: no new public names — refines the existing-note branch of `run_index` to reuse embeddings for chunks whose `content_hash` didn't change (keyed by `heading_path`), only calling `embedding_provider.embed_batch` for new/changed chunks.

- [x] **Step 1: Write the failing tests**

Append to `apps/api/tests/ingestion/test_indexer.py`:

```python
def test_changed_note_reuses_unchanged_chunk_embeddings(tmp_path, db_session):
    note_v1 = "# Note A\n\n## Section One\n\nOriginal content.\n\n## Section Two\n\nUnchanged content.\n"
    note_v2 = "# Note A\n\n## Section One\n\nEdited content.\n\n## Section Two\n\nUnchanged content.\n"
    _write(tmp_path, "Note-A.md", note_v1)
    provider = FakeEmbeddingProvider()
    run_index(db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    note = db_session.query(Note).filter_by(vault_path="Note-A.md").one()
    section_two_before = next(c.embedding for c in note.chunks if c.heading_path.endswith("Section Two"))

    _write(tmp_path, "Note-A.md", note_v2)
    provider.calls.clear()
    result = run_index(db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    assert result.files_updated == 1
    db_session.refresh(note)
    section_two_after = next(c.embedding for c in note.chunks if c.heading_path.endswith("Section Two"))
    assert section_two_after == section_two_before
    embedded_texts = [text for call in provider.calls for text in call]
    assert not any("Unchanged content." in text for text in embedded_texts)
    assert any("Edited content." in text for text in embedded_texts)


def test_oversized_section_chunks_are_matched_by_heading_and_index_on_rerun(tmp_path, db_session):
    """Regression test: a naive diff keyed by heading_path alone collapses multiple
    chunks that share one heading (produced by the oversized-section fallback) down
    to a single dict entry, losing reuse for every sibling but the last one seen."""
    filler_a = "\n\n".join(f"Paragraph A{i} filler text to pad the token count for this test." for i in range(30))
    filler_b = "\n\n".join(f"Paragraph B{i} filler text to pad the token count for this test." for i in range(30))
    note_v1 = (
        f"# Note A\n\n## Everything\n\n{filler_a}\n\n{filler_b}\n\n## Other\n\nOriginal other content.\n"
    )
    note_v2 = (
        f"# Note A\n\n## Everything\n\n{filler_a}\n\n{filler_b}\n\n## Other\n\nEdited other content.\n"
    )
    _write(tmp_path, "Note-A.md", note_v1)
    provider = FakeEmbeddingProvider()
    run_index(db_session, str(tmp_path), provider, max_section_tokens=100, embedding_model="nomic-embed-text")

    note = db_session.query(Note).filter_by(vault_path="Note-A.md").one()
    everything_chunks = sorted(
        (c for c in note.chunks if c.heading_path.endswith("Everything")), key=lambda c: c.chunk_index
    )
    assert len(everything_chunks) > 1, "expected the oversized section to split into multiple chunks"
    embeddings_before = {c.chunk_index: c.embedding for c in everything_chunks}

    _write(tmp_path, "Note-A.md", note_v2)
    provider.calls.clear()
    result = run_index(db_session, str(tmp_path), provider, max_section_tokens=100, embedding_model="nomic-embed-text")

    assert result.files_updated == 1
    db_session.refresh(note)
    everything_chunks_after = sorted(
        (c for c in note.chunks if c.heading_path.endswith("Everything")), key=lambda c: c.chunk_index
    )
    assert len(everything_chunks_after) == len(everything_chunks)
    for chunk in everything_chunks_after:
        assert chunk.embedding == embeddings_before[chunk.chunk_index], (
            "every sub-chunk of the unchanged oversized section must reuse its own prior "
            "embedding, not collide with a sibling chunk under the same heading"
        )
    embedded_texts = [text for call in provider.calls for text in call]
    assert not any("filler text" in text for text in embedded_texts), (
        "no Everything sub-chunk should have been re-embedded — only Other actually changed"
    )
    assert any("Edited other content." in text for text in embedded_texts)
```

- [x] **Step 2: Run tests to verify the new one fails**

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py -v`
Expected: `test_changed_note_reuses_unchanged_chunk_embeddings` FAILs (current implementation re-embeds every chunk on any change). `test_oversized_section_chunks_are_matched_by_heading_and_index_on_rerun` also FAILs — with `chunk_note` and `run_index` not yet using the fixed key, that test's `embedded_texts` assertion catches the actual bug: a naive `heading_path`-only dedup dict collapses all "Everything" sub-chunks to one entry, so every sub-chunk except whichever was last registered for that heading gets wrongly compared against the wrong old chunk's hash and gets spuriously re-embedded — even though none of "Everything"'s content changed.

- [x] **Step 3: Refactor the changed-note branch to diff and reuse**

Modify `apps/api/app/ingestion/indexer.py`. Add this helper function above `run_index`:

```python
def _diff_and_embed_chunks(
    existing_chunks: list[Chunk],
    chunk_data: list,
    embedding_provider: EmbeddingProvider,
) -> list[Chunk]:
    # Keyed by (heading_path, chunk_index), not heading_path alone — an oversized
    # section (see chunker.py's fallback splitting) can produce multiple sibling
    # chunks under the same heading_path, and heading_path-only keys would collapse
    # them to a single dict entry, causing every sibling but one to be compared
    # against the wrong old chunk's content_hash.
    existing_by_key = {(c.heading_path, c.chunk_index): c for c in existing_chunks}
    to_embed_indexes: list[int] = []
    texts_to_embed: list[str] = []
    resolved: dict[int, list[float]] = {}

    for i, c in enumerate(chunk_data):
        old = existing_by_key.get((c.heading_path, c.chunk_index))
        if old is not None and old.content_hash == c.content_hash:
            resolved[i] = old.embedding
        else:
            to_embed_indexes.append(i)
            texts_to_embed.append(c.content_with_context)

    new_vectors = embedding_provider.embed_batch(texts_to_embed)
    for idx, vector in zip(to_embed_indexes, new_vectors):
        resolved[idx] = vector

    return [
        Chunk(
            heading_path=c.heading_path,
            chunk_index=c.chunk_index,
            start_line=c.start_line,
            end_line=c.end_line,
            content=c.content,
            content_with_context=c.content_with_context,
            token_count=c.token_count,
            embedding=resolved[i],
            content_hash=c.content_hash,
        )
        for i, c in enumerate(chunk_data)
    ]
```

Then replace the body of the `for scanned in scanned_files:` loop's try block (from `parsed = parse_note(...)` through `result.chunks_created += len(chunk_data)`) with:

```python
            parsed = parse_note(scanned.content, fallback_title=_title_from_path(scanned.vault_path))
            chunk_data = chunk_note(
                parsed, title=parsed.title, vault_path=scanned.vault_path, max_section_tokens=max_section_tokens
            )

            if existing is None:
                note = Note(
                    vault_path=scanned.vault_path,
                    filename=scanned.vault_path.rsplit("/", 1)[-1],
                    title=parsed.title,
                    content_hash=scanned.content_hash,
                    modified_at=scanned.modified_at,
                    frontmatter_json=parsed.frontmatter,
                    tags=parsed.tags,
                    aliases=parsed.aliases,
                    indexed_at=datetime.now(timezone.utc),
                    embedding_version=embedding_model,
                )
                session.add(note)
                vectors = embedding_provider.embed_batch([c.content_with_context for c in chunk_data])
                note.chunks = [
                    Chunk(
                        heading_path=c.heading_path,
                        chunk_index=c.chunk_index,
                        start_line=c.start_line,
                        end_line=c.end_line,
                        content=c.content,
                        content_with_context=c.content_with_context,
                        token_count=c.token_count,
                        embedding=vector,
                        content_hash=c.content_hash,
                    )
                    for c, vector in zip(chunk_data, vectors)
                ]
                result.files_added += 1
            else:
                note = existing
                note.content_hash = scanned.content_hash
                note.modified_at = scanned.modified_at
                note.frontmatter_json = parsed.frontmatter
                note.tags = parsed.tags
                note.aliases = parsed.aliases
                note.indexed_at = datetime.now(timezone.utc)
                note.embedding_version = embedding_model
                note.chunks = _diff_and_embed_chunks(list(existing.chunks), chunk_data, embedding_provider)
                result.files_updated += 1

            note.links = [
                NoteLink(target_path=link.target, link_text=link.link_text, link_type=link.link_type)
                for link in parsed.links
            ]
            result.chunks_created += len(chunk_data)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py -v`
Expected: PASS (5 tests)

- [x] **Step 5: Commit**

```bash
git add apps/api/app/ingestion/indexer.py apps/api/tests/ingestion/test_indexer.py
git commit -m "feat(ingestion): reuse chunk embeddings across unchanged sections"
```

---

### Task 8: Surfaced scan errors, deleted-file cleanup, and failure handling

**Files:**
- Modify: `apps/api/app/ingestion/scanner.py`
- Modify: `apps/api/app/ingestion/indexer.py`
- Modify: `apps/api/tests/ingestion/test_scanner.py`
- Test: `apps/api/tests/ingestion/test_indexer.py` (append)

**Interfaces:**
- `scan_vault` changes return type from `list[ScannedFile]` to a new `ScanResult(files: list[ScannedFile], errors: list[dict])` dataclass. `run_index` (Task 6/7) is updated to unpack `.files`/`.errors` at its one call site.
- Adds the deleted-file cleanup pass to `run_index` (already fails cleanly for a bad `vault_path` per Task 6's implementation; this task adds a test proving it).

**Known gap being closed here:** Task 2's `scan_vault` catches `UnicodeDecodeError` per file, logs a warning, and skips the file — so a bad file doesn't crash the scan. But that error never reaches `run_index`'s `errors_json`: the top-level `except OSError` around `scan_vault(...)` doesn't fire (the bad file is already handled inside `scan_vault`, and `UnicodeDecodeError` isn't an `OSError`), and the per-file `try/except` inside the indexing loop never sees it either, since `scan_vault` has already returned by the time that loop starts. Net effect: a non-UTF-8 file is silently dropped and the resulting `IndexRun` row still reports `status="success"` with no trace anything was skipped. Zero risk to the sample vault (all authored UTF-8), but it breaks the guarantee this task exists to establish — one bad file should show up in `errors_json`, not vanish. Close it here since it's squarely this task's failure-handling scope.

- [x] **Step 1: Write the failing test for surfaced scan errors**

In `apps/api/tests/ingestion/test_scanner.py`, update every existing test that does `files = scan_vault(tmp_path)` (all of them except the two `content_hash`-only tests, which don't call `scan_vault` at all) to `files = scan_vault(tmp_path).files` instead. Then update `test_scan_skips_files_with_invalid_utf8` and add one new test:

```python
def test_scan_skips_files_with_invalid_utf8(tmp_path):
    _write(tmp_path, "valid.md", "# Valid\n\nContent.")
    invalid_file = tmp_path / "invalid.md"
    invalid_file.write_bytes(b"\xff\xfe\x00invalid")

    result = scan_vault(tmp_path)

    paths = {f.vault_path for f in result.files}
    assert paths == {"valid.md"}
    assert len(result.files) == 1


def test_scan_reports_unreadable_files_as_errors(tmp_path):
    _write(tmp_path, "valid.md", "# Valid\n\nContent.")
    invalid_file = tmp_path / "invalid.md"
    invalid_file.write_bytes(b"\xff\xfe\x00invalid")

    result = scan_vault(tmp_path)

    assert len(result.errors) == 1
    assert result.errors[0]["vault_path"] == "invalid.md"


def test_scan_raises_for_missing_vault_path(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        scan_vault(missing)
```

Add `import pytest` at the top of `test_scanner.py` if it isn't already there (it isn't, per Task 2's version of this file).

Run: `cd apps/api && pytest tests/ingestion/test_scanner.py -v`
Expected: FAIL — every test using `scan_vault(...)` as a bare list now breaks on `.files`/`.errors` attribute access, since `scan_vault` still returns a plain list. `test_scan_raises_for_missing_vault_path` also FAILs (no exception raised yet).

- [x] **Step 2: Make `scan_vault` return `ScanResult`**

Modify `apps/api/app/ingestion/scanner.py`: add a `ScanResult` dataclass next to `ScannedFile`:

```python
@dataclass
class ScanResult:
    files: list[ScannedFile]
    errors: list[dict]
```

In `scan_vault`, introduce an `errors: list[dict] = []` list alongside `results`. In the existing `except UnicodeDecodeError as exc:` block (which currently only logs and `continue`s), also append `{"vault_path": relative.as_posix(), "error": str(exc)}` to `errors` before continuing — keep the existing `logger.warning(...)` call too, the log line and the surfaced error are complementary. Change the function's final `return results` to `return ScanResult(files=results, errors=errors)`.

**Also fix a second, related bug while touching this function:** `scan_vault` currently never raises for a missing `vault_path` — `Path(vault_path).rglob(...)` on a nonexistent directory silently returns an empty iterator rather than raising, so `run_index`'s `except OSError` branch (written in Task 6) is actually unreachable dead code, and the `test_unreadable_vault_path_marks_run_failed` test later in this task would fail as written. Add an explicit check at the top of `scan_vault`, before the `rglob` call:

```python
    root = Path(vault_path)
    if not root.is_dir():
        raise FileNotFoundError(f"vault path does not exist or is not a directory: {root}")
```

(`FileNotFoundError` is a subclass of `OSError`, so `run_index`'s existing `except OSError` handler now has something real to catch.)

Run: `cd apps/api && pytest tests/ingestion/test_scanner.py -v`
Expected: PASS (10 tests).

- [x] **Step 3: Wire surfaced scan errors into `run_index`**

Modify `apps/api/app/ingestion/indexer.py`'s call site. Replace:

```python
    try:
        scanned_files = scan_vault(vault_path)
    except OSError as exc:
```

with:

```python
    try:
        scan_result = scan_vault(vault_path)
    except OSError as exc:
```

and replace the line immediately after the `try/except` block, currently:

```python
    result = IndexRunResult(status="success", files_scanned=len(scanned_files))
```

with:

```python
    scanned_files = scan_result.files
    result = IndexRunResult(status="success", files_scanned=len(scanned_files))
    result.errors.extend(scan_result.errors)
```

(This runs before the per-file loop, so a scan-time error and a per-file processing error both land in the same `result.errors` list and both flip final `status` to `"partial"` via the existing `if result.errors: result.status = "partial"` check later in the function.)

Add to `apps/api/tests/ingestion/test_indexer.py`:

```python
def test_unreadable_file_is_recorded_as_error_and_other_files_still_index(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    invalid_file = tmp_path / "Invalid.md"
    invalid_file.write_bytes(b"\xff\xfe\x00invalid")
    provider = FakeEmbeddingProvider()

    result = run_index(
        db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    assert result.status == "partial"
    assert any(e["vault_path"] == "Invalid.md" for e in result.errors)
    assert db_session.query(Note).filter_by(vault_path="Note-A.md").one() is not None
```

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py tests/ingestion/test_scanner.py -v`
Expected: PASS (6 indexer tests, 10 scanner tests).

- [x] **Step 4: Write the failing test for deleted-file cleanup**

Append to `apps/api/tests/ingestion/test_indexer.py`:

```python
def test_deleted_file_removes_note_and_chunks(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()
    run_index(db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    (tmp_path / "Note-A.md").unlink()
    result = run_index(db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    assert result.files_deleted == 1
    assert db_session.query(Note).filter_by(vault_path="Note-A.md").first() is None


def test_unreadable_vault_path_marks_run_failed(db_session):
    provider = FakeEmbeddingProvider()
    result = run_index(
        db_session, "/nonexistent/vault/path", provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )
    assert result.status == "failed"
    run = db_session.query(IndexRun).order_by(IndexRun.id.desc()).first()
    assert run.status == "failed"
```

- [x] **Step 5: Run test to verify it fails**

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py -v`
Expected: FAIL on `test_deleted_file_removes_note_and_chunks` — nothing currently removes notes whose files disappeared. `test_unreadable_vault_path_marks_run_failed` should already PASS (Task 6's try/except around `scan_vault` handles this) — confirms that behavior with an explicit test.

- [x] **Step 6: Add the deleted-file cleanup pass**

Modify `apps/api/app/ingestion/indexer.py`. After the `for scanned in scanned_files:` loop (i.e., after the loop that adds/updates notes, before the `if result.errors:` line), add:

```python
    scanned_paths = {f.vault_path for f in scanned_files}
    for vault_path_key, note in existing_notes.items():
        if vault_path_key not in scanned_paths:
            result.chunks_deleted += len(note.chunks)
            session.delete(note)
            result.files_deleted += 1
```

- [x] **Step 7: Run test to verify it passes**

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py -v`
Expected: PASS (8 tests)

- [x] **Step 8: Commit**

```bash
git add apps/api/app/ingestion/scanner.py apps/api/app/ingestion/indexer.py \
  apps/api/tests/ingestion/test_scanner.py apps/api/tests/ingestion/test_indexer.py
git commit -m "feat(ingestion): surface scan errors and clean up deleted-file notes on reindex"
```

**Post-Task-8 fix (commit `fa4e9c8`):** Step 6's deleted-file cleanup pass built `scanned_paths` from `scan_result.files` only, so a file that indexed successfully in a prior run and then became transiently unreadable (caught in `scan_result.errors`, not raised) was wrongly treated as deleted and its `Note` row was silently removed. Fixed by also including the `vault_path` of every scan error in `scanned_paths`, so an unreadable-but-still-present file is left in place with its error surfaced instead of being discarded. Landed before Task 9 started.

---

### Task 9: CLI entry point

**Files:**
- Create: `apps/api/app/ingestion/cli.py`
- Test: `apps/api/tests/ingestion/test_cli.py`

**Interfaces:**
- Consumes: `settings` (`app.core.config`), `SessionLocal` (`app.db.base`), `OllamaEmbeddingProvider` (Task 5), `run_index` (Task 6+).
- Produces: `main() -> None`, runnable as `python -m app.ingestion.cli`. This is the file Phase 3 will change (the one `base_url=` line) to resolve the active provider from the DB instead of `settings.ollama_workstation_url` directly.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/ingestion/test_cli.py`:

```python
import app.ingestion.cli as cli_module
from tests.ingestion.fakes import FakeEmbeddingProvider


def test_main_runs_index_and_prints_summary(tmp_path, db_session, monkeypatch, capsys):
    (tmp_path / "Note-A.md").write_text("# Note A\n\nSome content.\n", encoding="utf-8")

    monkeypatch.setattr(cli_module.settings, "vault_path", str(tmp_path))
    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(cli_module, "OllamaEmbeddingProvider", lambda base_url: FakeEmbeddingProvider())

    cli_module.main()

    captured = capsys.readouterr()
    assert "status=success" in captured.out
    assert "added=1" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/ingestion/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.cli'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/ingestion/cli.py`:

```python
from __future__ import annotations

from app.core.config import settings
from app.db.base import SessionLocal
from app.ingestion.embeddings import OllamaEmbeddingProvider
from app.ingestion.indexer import run_index


def main() -> None:
    session = SessionLocal()
    try:
        provider = OllamaEmbeddingProvider(base_url=settings.ollama_workstation_url)
        result = run_index(
            session,
            settings.vault_path,
            provider,
            max_section_tokens=settings.chunk_max_section_tokens,
            embedding_model=settings.embedding_model,
        )
        print(
            f"status={result.status} scanned={result.files_scanned} "
            f"added={result.files_added} updated={result.files_updated} "
            f"deleted={result.files_deleted} errors={len(result.errors)}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/ingestion/test_cli.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/ingestion/cli.py apps/api/tests/ingestion/test_cli.py
git commit -m "feat(ingestion): add python -m app.ingestion.cli manual indexing entry point"
```

---

### Task 10: GET /api/index/status endpoint

**Files:**
- Create: `apps/api/app/api/deps.py`
- Create: `apps/api/app/api/index_status.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_index_status.py`

**Interfaces:**
- Consumes: `IndexRun`, `Note` models; `settings.embedding_model`; `run_index` (for the test's setup, not the endpoint itself).
- Produces: `get_db()` (FastAPI dependency, `Iterator[Session]`), `GET /api/index/status` route returning `{"embedding_model": str, "note_count": int, "last_run": dict | None}`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_index_status.py`:

```python
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.ingestion.indexer import run_index
from app.main import app
from tests.ingestion.fakes import FakeEmbeddingProvider


def test_status_with_no_runs_yet(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.get("/api/index/status")
        assert response.status_code == 200
        body = response.json()
        assert body["note_count"] == 0
        assert body["last_run"] is None
        assert body["embedding_model"] == "nomic-embed-text"
    finally:
        app.dependency_overrides.clear()


def test_status_reflects_latest_index_run(tmp_path, db_session):
    (tmp_path / "Note-A.md").write_text("# Note A\n\nBody.\n", encoding="utf-8")
    run_index(
        db_session, str(tmp_path), FakeEmbeddingProvider(), max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        response = client.get("/api/index/status")
        body = response.json()
        assert body["note_count"] == 1
        assert body["last_run"]["status"] == "success"
        assert body["last_run"]["files_added"] == 1
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest tests/test_index_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.deps'`

- [ ] **Step 3: Write the implementation**

Create `apps/api/app/api/deps.py`:

```python
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db.base import SessionLocal


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

Create `apps/api/app/api/index_status.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import IndexRun, Note

router = APIRouter()


@router.get("/api/index/status")
def get_index_status(db: Session = Depends(get_db)) -> dict:
    latest_run = db.query(IndexRun).order_by(IndexRun.id.desc()).first()
    note_count = db.query(func.count(Note.id)).scalar()

    return {
        "embedding_model": settings.embedding_model,
        "note_count": note_count,
        "last_run": None
        if latest_run is None
        else {
            "status": latest_run.status,
            "started_at": latest_run.started_at.isoformat(),
            "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
            "files_scanned": latest_run.files_scanned,
            "files_added": latest_run.files_added,
            "files_updated": latest_run.files_updated,
            "files_deleted": latest_run.files_deleted,
            "errors": latest_run.errors_json,
        },
    }
```

Modify `apps/api/app/main.py` to the full contents:

```python
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.index_status import router as index_status_router

app = FastAPI(title="vault-interview-copilot")
app.include_router(health_router)
app.include_router(index_status_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest tests/test_index_status.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd apps/api && pytest -v`
Expected: PASS (all tests, old and new)

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/deps.py apps/api/app/api/index_status.py apps/api/app/main.py apps/api/tests/test_index_status.py
git commit -m "feat(api): add GET /api/index/status endpoint"
```

---

### Task 11: Sample vault content

**Files:**
- Create: `sample-vault/00-Inbox/Quick-Note-Kubernetes-Question.md`
- Create: `sample-vault/02-Technical-Reference/Terraform/Terraform-Fundamentals.md`
- Create: `sample-vault/02-Technical-Reference/Kubernetes/Kubernetes-Fundamentals.md`
- Create: `sample-vault/01-Interview-Prep/Project-Talking-Points/Meridian-Tool-Stack-Articulation.md`
- Create: `sample-vault/01-Interview-Prep/Technical-Concepts/CICD-Pipeline-Walkthrough.md`
- Create: `sample-vault/02-Technical-Reference/Troubleshooting-Log/Interview-Ready-Troubleshooting-Stories.md`
- Create: `sample-vault/03-Projects/Meridian/_Source-Docs/Mock-Interview-Notes.md`
- Create: `sample-vault/_Templates/STAR-Story-Template.md`

**Interfaces:**
- No code interfaces — this is fixture content consumed by Task 12's integration tests and by manual CLI verification.

- [ ] **Step 1: Create the headingless inbox note**

Create `sample-vault/00-Inbox/Quick-Note-Kubernetes-Question.md`:

```markdown
---
tags: [kubernetes, quick-capture]
---

Interviewer asked how node scaling actually differs from pod scaling in practice — need to double check whether the Cluster Autoscaler config lives in the Terraform node group definition or somewhere else before the next mock. Follow up with [[Kubernetes-Fundamentals]].
```

- [ ] **Step 2: Create the Terraform reference note**

Create `sample-vault/02-Technical-Reference/Terraform/Terraform-Fundamentals.md`. **Note the outer fence below is 4 backticks, not 3** — this file's own content contains a 3-backtick `hcl` fence, and a 3-backtick outer fence would terminate early at that inner fence. Write the file's contents exactly as shown between the 4-backtick markers, excluding the markers themselves:

````markdown
---
title: Terraform Fundamentals
tags: [terraform, iac, aws]
aliases: [tf-fundamentals]
---

# Terraform Fundamentals

## Module Structure

Meridian's infrastructure is split by resource type rather than fully modularized — a `compute.tf`, a `network.tf`, and an `iam.tf` per environment. Modules become worth the overhead once there's more than one environment or vertical to manage; for a single-environment project the extra abstraction isn't paying for itself yet.

## State Management

### Drift Management

State drift happens when the real infrastructure diverges from what the state file records — usually from a manual console change made during an incident. Detecting it means running a plan on a schedule and treating any non-empty diff as a signal, not just relying on someone noticing later.

```hcl
resource "aws_instance" "app_server" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.medium"

  tags = {
    Project     = "Meridian"
    Environment = "prod"
  }
}
```

### State Locking

Team-wide state safety comes from locking the state file during writes — an S3 backend with DynamoDB-based locking prevents two people from applying at the same time and corrupting the state. See [[Meridian-Tool-Stack-Articulation]] for how this fits into the broader tool choices on this project.
````

- [ ] **Step 3: Create the Kubernetes reference note**

Create `sample-vault/02-Technical-Reference/Kubernetes/Kubernetes-Fundamentals.md`. **Outer fence is 4 backticks** for the same reason as Task 11 Step 2 — this file contains a 3-backtick `yaml` fence internally:

````markdown
---
title: Kubernetes Fundamentals
tags: [kubernetes, scaling]
---

# Kubernetes Fundamentals

## Pod Scaling vs Node Scaling

The Horizontal Pod Autoscaler (HPA) scales the number of pod replicas based on observed CPU or memory usage. It has nothing to do with how many nodes exist underneath — that's the Cluster Autoscaler's job, which adds or removes nodes based on whether pending pods can actually be scheduled on current capacity.

## HPA Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: meridian-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: meridian-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## Cluster Autoscaler

The Cluster Autoscaler is configured through the Terraform node group's min/max size settings, not through a Kubernetes manifest — see [[Terraform-Fundamentals]] for where that lives.
````

- [ ] **Step 4: Create the talking-points note**

Create `sample-vault/01-Interview-Prep/Project-Talking-Points/Meridian-Tool-Stack-Articulation.md`:

```markdown
---
title: Meridian Tool Stack Articulation
tags: [meridian, talking-points]
---

# Meridian Tool Stack Articulation

## Why Terraform Over Manual Provisioning

Manual console changes don't leave an audit trail and don't scale past a handful of resources. Terraform gives a single source of truth for infrastructure and makes drift detectable instead of invisible. Full walkthrough in [[Terraform-Fundamentals]].

## Why GitOps Over a Long-Running CI Server

Meridian's deployment pipeline pulls changes into the cluster via GitOps rather than pushing them from a long-running Jenkins-style server — no server to patch and babysit, and the cluster's actual state is always reconciled against Git rather than trusted to have received the last push. See [[CICD-Pipeline-Walkthrough]] for the full pipeline shape.
```

- [ ] **Step 5: Create the CI/CD pipeline note**

Create `sample-vault/01-Interview-Prep/Technical-Concepts/CICD-Pipeline-Walkthrough.md`. **Outer fence is 4 backticks**, same reason — this file contains a 3-backtick `yaml` fence internally:

````markdown
---
title: CICD Pipeline Walkthrough
tags: [cicd, github-actions]
---

# CICD Pipeline Walkthrough

## Build Stage

Every push builds a container image and runs a security scan before anything is allowed to be pushed to the registry.

```yaml
name: build
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t meridian-api:${{ github.sha }} .
      - name: Scan image
        run: trivy image meridian-api:${{ github.sha }}
      - name: Push to registry
        run: docker push meridian-api:${{ github.sha }}
```

## Deploy Stage

The build stage pushes an image; it does not touch the cluster directly. A separate GitOps controller notices the new image reference and reconciles the cluster to match — see [[Meridian-Tool-Stack-Articulation]] for the reasoning behind that split.
````

- [ ] **Step 6: Create the troubleshooting story note**

Create `sample-vault/02-Technical-Reference/Troubleshooting-Log/Interview-Ready-Troubleshooting-Stories.md`:

```markdown
---
title: Interview-Ready Troubleshooting Stories
tags: [troubleshooting, star-stories]
---

# Interview-Ready Troubleshooting Stories

## Jenkins Agent Could Not Reach the Docker Daemon

### Situation

A pipeline stage that containerized the application started failing on a freshly provisioned build agent, even though the Docker plugin was installed and configured in Jenkins.

### Task

Get the containerize step working again without weakening the agent's security posture.

### Action

Confirmed the Docker plugin only manages Jenkins-side configuration — it doesn't grant the agent access to an actual Docker daemon. Mounted the host's Docker socket into the agent container so `docker build` had somewhere real to run against.

### Result

The pipeline went green again, and the fix became the standard bootstrap step for any new build agent going forward.
```

- [ ] **Step 7: Create the `_Source-Docs` proof file**

Create `sample-vault/03-Projects/Meridian/_Source-Docs/Mock-Interview-Notes.md`:

```markdown
---
title: Mock Interview Notes
tags: [meridian, mock-interview, source-doc]
---

# Mock Interview Notes

## Raw Notes From Practice Session

Interviewer pushed hard on the difference between rolling deployments and blue-green — worth re-confirming the canary distinction is crisp before the next one. Reference: [[Meridian-Tool-Stack-Articulation]].
```

- [ ] **Step 8: Create the `_Templates` exclusion-proof file**

Create `sample-vault/_Templates/STAR-Story-Template.md`:

```markdown
---
title: STAR Story Template
tags: [template]
---

# {{Story Title}}

## Situation

## Task

## Action

## Result
```

- [ ] **Step 9: Remove the now-unneeded placeholder**

Run: `rm sample-vault/.gitkeep` (no longer needed now that the directory has real content)

- [ ] **Step 10: Commit**

```bash
git add sample-vault/
git commit -m "feat(sample-vault): add fictional Meridian project content for Phase 1 testing"
```

---

### Task 12: Exit-condition integration tests

**Files:**
- Test: `apps/api/tests/ingestion/test_sample_vault_integration.py`

**Interfaces:**
- Consumes: `run_index` (Task 6+), `FakeEmbeddingProvider` (Task 5), the real `sample-vault/` content (Task 11).
- Produces: no new application code — this is the authoritative proof of the Phase 1 exit condition from `docs/architecture/10-delivery-plan.md`.

- [ ] **Step 1: Write the integration tests**

Create `apps/api/tests/ingestion/test_sample_vault_integration.py`:

```python
import shutil
from pathlib import Path

from app.db.models import Chunk, Note
from app.ingestion.indexer import run_index
from tests.ingestion.fakes import FakeEmbeddingProvider

SAMPLE_VAULT = Path(__file__).resolve().parents[4] / "sample-vault"


def _copy_sample_vault(tmp_path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(SAMPLE_VAULT, dest)
    return dest


def test_second_run_against_unchanged_sample_vault_touches_zero_files(tmp_path, db_session):
    vault = _copy_sample_vault(tmp_path)
    provider = FakeEmbeddingProvider()

    first = run_index(db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text")
    assert first.files_added > 0

    provider.calls.clear()
    second = run_index(db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    assert second.files_added == 0
    assert second.files_updated == 0
    assert second.files_deleted == 0
    assert provider.calls == []


def test_ignore_patterns_exclude_templates_but_keep_source_docs(tmp_path, db_session):
    vault = _copy_sample_vault(tmp_path)
    provider = FakeEmbeddingProvider()

    run_index(db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    indexed_paths = {n.vault_path for n in db_session.query(Note).all()}
    assert "03-Projects/Meridian/_Source-Docs/Mock-Interview-Notes.md" in indexed_paths
    assert not any("_Templates" in p for p in indexed_paths)


def test_editing_one_section_only_reembeds_that_chunk(tmp_path, db_session):
    vault = _copy_sample_vault(tmp_path)
    provider = FakeEmbeddingProvider()
    run_index(db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    terraform_path = vault / "02-Technical-Reference" / "Terraform" / "Terraform-Fundamentals.md"
    original = terraform_path.read_text(encoding="utf-8")
    edited = original.replace("State drift", "State drift (edited for test)", 1)
    assert edited != original
    terraform_path.write_text(edited, encoding="utf-8")

    provider.calls.clear()
    result = run_index(db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    assert result.files_updated == 1
    assert result.files_added == 0
    embedded_texts = [text for call in provider.calls for text in call]
    assert len(embedded_texts) >= 1
    assert any("edited for test" in text for text in embedded_texts)


def test_deleting_a_file_cascades_chunk_cleanup(tmp_path, db_session):
    vault = _copy_sample_vault(tmp_path)
    provider = FakeEmbeddingProvider()
    run_index(db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    target = vault / "00-Inbox" / "Quick-Note-Kubernetes-Question.md"
    target.unlink()

    result = run_index(db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    assert result.files_deleted == 1
    remaining = db_session.query(Note).filter_by(vault_path="00-Inbox/Quick-Note-Kubernetes-Question.md").first()
    assert remaining is None
    assert db_session.query(Chunk).join(Note).filter(Note.vault_path.like("00-Inbox%")).count() == 0
```

- [ ] **Step 2: Run the tests**

Requires a real Postgres reachable at `settings.database_url`: `docker compose up -d postgres` (from repo root) if not already running.

Run: `cd apps/api && pytest tests/ingestion/test_sample_vault_integration.py -v`
Expected: PASS (4 tests) — this is the automated proof of the Phase 1 exit condition.

- [ ] **Step 3: Run the full test suite**

Run: `cd apps/api && pytest -v`
Expected: PASS (all tests across the whole Phase 1 build)

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/ingestion/test_sample_vault_integration.py
git commit -m "test(ingestion): add exit-condition integration tests against sample-vault"
```

- [ ] **Step 5 (optional, manual — requires a real Ollama running locally): hand-verify via the CLI**

This isn't a scripted test — it's the manual proof described in `Phase-1-Scope.md`'s exit condition, using the real embedding provider instead of the fake.

1. Ensure Postgres is up: `docker compose up -d postgres`
2. Ensure Ollama is running locally with `nomic-embed-text` pulled: `ollama pull nomic-embed-text`
3. Set `VAULT_PATH=../../sample-vault` in `apps/api/.env` (or export `VAULT_PATH` pointing at the repo's `sample-vault/`)
4. Run migrations: `cd apps/api && alembic upgrade head`
5. Run the indexer twice:
   ```bash
   python -m app.ingestion.cli
   python -m app.ingestion.cli
   ```
6. Confirm the second run's printed summary shows `added=0 updated=0 deleted=0` — the hand-verified proof of the exit condition.

---

### Task 13: Defer note-state mutation until chunks/embeddings are confirmed committed

**Context:** Flagged as an Important finding at Phase 1 final review (post Task 12), previously deferred at Task 6/Task 8 as low-probability. This is a follow-up fix landing after Phase 1's original 12 tasks are already committed — not a gap in the original sequence.

If `run_index` hits an embedding-provider error partway through processing a file, two failure modes are currently possible:
- A new note gets added to the session with its `content_hash` set, but zero chunks — permanently skipped on future runs, since the hash now matches and nothing flags it as incomplete.
- A changed note commits its new `content_hash` while its old, stale chunks remain attached — also permanently skipped, silently serving outdated content.

Both are silent and undetectable from `errors_json` or run status. Fix: reorder the per-file update so chunk building and embedding happen before any note-state mutation, so a mid-file failure leaves the note exactly as it was pre-run, and a retry on the next `run_index` call picks it up cleanly instead of treating it as already-indexed.

**Files:**
- Modify: `apps/api/app/ingestion/indexer.py`
- Test: `apps/api/tests/ingestion/test_indexer.py` (append)

**Interfaces:** No public signature changes. This is a reordering + atomicity fix inside `run_index`'s per-file processing loop only.

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/ingestion/test_indexer.py`. You'll need a `FakeEmbeddingProvider` variant (or a parameter on the existing one) that raises partway through a batch — e.g. `FailingEmbeddingProvider(fail_after: int)` that succeeds for the first N calls/items then raises. Check the existing `FakeEmbeddingProvider` in this file and extend it in the way that fits its current shape (constructor param, or a subclass) rather than duplicating it.

```python
def test_new_note_not_committed_if_embedding_fails_partway(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)  # a note whose content splits into 2+ chunks
    provider = FailingEmbeddingProvider(fail_after=0)  # fails on first batch

    result = run_index(
        db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    # Note must not exist at all — not "exists with 0 chunks"
    assert db_session.query(Note).filter_by(vault_path="Note-A.md").first() is None
    assert any(e["vault_path"] == "Note-A.md" for e in result.errors)
    assert result.status == "partial"


def test_changed_note_keeps_old_chunks_if_embedding_fails_partway(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    provider = FakeEmbeddingProvider()
    run_index(db_session, str(tmp_path), provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    original_note = db_session.query(Note).filter_by(vault_path="Note-A.md").one()
    original_hash = original_note.content_hash
    original_chunk_count = len(original_note.chunks)

    _write(tmp_path, "Note-A.md", NOTE_A_MODIFIED)  # changed content, different chunk count
    failing_provider = FailingEmbeddingProvider(fail_after=0)
    result = run_index(
        db_session, str(tmp_path), failing_provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    db_session.refresh(original_note)
    # Old hash and old chunks must be untouched — not partially replaced
    assert original_note.content_hash == original_hash
    assert len(original_note.chunks) == original_chunk_count
    assert any(e["vault_path"] == "Note-A.md" for e in result.errors)
    assert result.status == "partial"


def test_failed_note_is_retried_cleanly_on_next_run(tmp_path, db_session):
    _write(tmp_path, "Note-A.md", NOTE_A)
    failing_provider = FailingEmbeddingProvider(fail_after=0)
    run_index(db_session, str(tmp_path), failing_provider, max_section_tokens=400, embedding_model="nomic-embed-text")

    working_provider = FakeEmbeddingProvider()
    result = run_index(
        db_session, str(tmp_path), working_provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    note = db_session.query(Note).filter_by(vault_path="Note-A.md").one()
    assert len(note.chunks) > 0
    assert result.status == "success"
```

If `NOTE_A_MODIFIED` doesn't already exist as a fixture in this file, add a small constant near `NOTE_A` with different content that produces a different chunk count.

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py -v`
Expected: FAIL on all three new tests — current code commits note state before/independent of embedding success.

- [ ] **Step 2: Locate and reorder the per-file processing block**

In `apps/api/app/ingestion/indexer.py`, find the loop that processes each scanned file (the same loop Task 8 added the deleted-file cleanup after — and check whether Task 9, 11, or 12 touched this loop too, since you're past those now; reconcile against current source, not this description). The current order is roughly: mutate/create the `Note` row (set `content_hash`, add to session) → build chunks → call `provider.embed_batch(...)` → attach chunks to the note.

Reorder to:
1. Build the chunk data (text + metadata) and call `provider.embed_batch(...)` first, fully, before touching the `Note` row at all.
2. Only once chunk data + vectors are back successfully, create/update the `Note` (set `content_hash`, `session.add(note)` if new) and assign the fully-built chunk list to it — as a single atomic reassignment (`note.chunks = new_chunk_objects`), not a clear-then-append.
3. Wrap the `embed_batch` call (or the whole per-file block) in a `try`/`except` at the same level as the existing per-file error handling. On exception:
   - New note: never call `session.add()` — nothing to roll back, it simply never entered the session.
   - Changed note: don't touch `content_hash` or `note.chunks` — the existing DB row stays exactly as it was before this run.
   - Append the failure to `result.errors` in the same shape already used (`{"vault_path": ..., "error": str(exc)}`), and continue to the next file rather than aborting the whole run.

Keep the existing per-file try/except structure and `errors_json` shape intact — this is a reordering and atomicity fix within that structure, not a new error-handling mechanism.

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd apps/api && pytest tests/ingestion/test_indexer.py tests/ingestion/test_scanner.py -v`
Expected: PASS (all indexer + scanner tests, including the 3 new ones).

- [ ] **Step 4: Run full suite to confirm no regressions**

Run: `cd apps/api && pytest -v`
Expected: PASS, full suite green. This matters more than usual here since Task 13 touches shared code (the per-file loop) that Tasks 9–12 may also have built on top of — a regression here could ripple into CLI or later Phase 1 work you've already committed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/ingestion/indexer.py apps/api/tests/ingestion/test_indexer.py
git commit -m "fix(ingestion): don't commit note state until chunks/embeddings succeed

Prevents new notes from landing with zero chunks and changed notes from
keeping stale chunks under a new content_hash when embed_batch fails
partway through a file. Both were previously silent and permanent —
the hash comparison on the next run treated the file as already
correctly indexed with no trace in errors_json. Deferred at Task 6/8,
fixed as Task 13 after Phase 1 final review flagged it. Fix reorders
note mutation to happen only after chunks and vectors are confirmed."
```

---

## Summary

Twelve tasks, in dependency order: config → scanner → parser → chunker → embeddings → indexer (new/unchanged → diff/reuse → delete/failure) → CLI → API status → sample vault content → exit-condition integration tests. Each task is independently testable and commits on its own. Phase 1's exit condition (`docs/architecture/10-delivery-plan.md`) is satisfied by Task 12.
