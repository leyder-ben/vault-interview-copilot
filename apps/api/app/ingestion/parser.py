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
