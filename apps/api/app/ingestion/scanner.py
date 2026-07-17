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
