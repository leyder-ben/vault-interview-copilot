from __future__ import annotations

import re

ALIASES: dict[str, str] = {
    "tf": "terraform",
    "k8s": "kubernetes",
    "sm": "secrets manager",
    "cw": "cloudwatch",
    "bluegreen": "blue green deployment",
    "gha": "github actions",
}

_PUNCTUATION_RE = re.compile(r"[^\w\s-]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_query(raw: str) -> str:
    lowered = raw.lower()
    no_punctuation = _PUNCTUATION_RE.sub("", lowered)
    collapsed = _WHITESPACE_RE.sub(" ", no_punctuation).strip()

    tokens = collapsed.split(" ")
    expanded = [ALIASES.get(token, token) for token in tokens]
    return " ".join(expanded)
