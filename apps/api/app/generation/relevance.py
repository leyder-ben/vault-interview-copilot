from __future__ import annotations

import re

_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "at",
    "by",
    "from",
    "as",
    "that",
    "this",
    "it",
    "its",
    "i",
    "we",
    "you",
    "they",
    "he",
    "she",
    "if",
    "when",
    "while",
    "so",
    "not",
    "no",
    "do",
    "does",
    "did",
    "can",
    "could",
    "will",
    "would",
    "should",
    "which",
    "what",
    "how",
    "into",
    "over",
    "than",
    "then",
    "also",
    "just",
    "my",
    "our",
    "their",
    "these",
    "those",
    "each",
    "either",
    "one",
    "two",
    "see",
}


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9\-]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def citation_relevance_score(chunk_content: str, claim_text: str) -> float:
    """Fraction of the chunk's significant words that also appear in the
    claim text (the generated answer citing it).

    A citation can be a real, in-context chunk ID and still not back the
    claim it's attached to -- the membership check alone can't see that. See
    docs/superpowers/plans/2026-07-19-phase-3-grounded-answers.md's
    "Citation cross-check verifies membership, not relevance" section for the
    finding and the measurement behind settings.citation_relevance_threshold.
    """
    chunk_words = _significant_words(chunk_content)
    if not chunk_words:
        return 0.0
    claim_words = _significant_words(claim_text)
    return len(chunk_words & claim_words) / len(chunk_words)
