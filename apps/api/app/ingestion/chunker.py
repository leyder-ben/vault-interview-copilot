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


def _build_context_header(
    *, title: str, vault_path: str, heading_path: str | None, tags: list[str]
) -> str:
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
    protected = [
        (s - section.start_line, e - section.start_line) for s, e in section.code_block_ranges
    ]

    def inside_open_code_block(offset: int) -> bool:
        return any(cb_start <= offset < cb_end for cb_start, cb_end in protected)

    merged: list[tuple[int, int, str]] = []
    buffer: tuple[int, int, str] | None = None
    for start, end, text in paragraphs:
        if buffer is None:
            buffer = (start, end, text)
        else:
            buffer = (buffer[0], end, buffer[2] + "\n\n" + text)
        if not inside_open_code_block(buffer[1]):
            merged.append(buffer)
            buffer = None
    if buffer is not None:
        merged.append(buffer)
    return merged


def _pack_by_token_budget(
    units: list[tuple[int, int, str]], max_tokens: int
) -> list[tuple[int, int, str]]:
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
                title=title,
                vault_path=vault_path,
                heading_path=section.heading_path,
                tags=parsed.tags,
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
