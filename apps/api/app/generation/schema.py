from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ResponseMode(str, Enum):
    SPEAKABLE = "speakable"
    EXPLAIN = "explain"
    COMPARE = "compare"
    TROUBLESHOOT = "troubleshoot"
    EXAMPLE = "example"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_DOWNGRADE: dict[Confidence, Confidence] = {
    Confidence.HIGH: Confidence.MEDIUM,
    Confidence.MEDIUM: Confidence.LOW,
    Confidence.LOW: Confidence.LOW,
}


def downgrade_confidence(confidence: Confidence) -> Confidence:
    """One level down; LOW is a floor (never goes lower)."""
    return _DOWNGRADE[confidence]


class PersonalExample(BaseModel):
    project: str
    example: str
    source_chunk_ids: list[int]


class AnswerDraft(BaseModel):
    """Exact shape the LLM is constrained to emit as JSON (see providers/llm.py)."""

    say_this: str
    supporting_points: list[str] = Field(default_factory=list)
    personal_examples: list[PersonalExample] = Field(default_factory=list)
    used_source_chunk_ids: list[int] = Field(default_factory=list)
    confidence: Confidence
    limitations: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str
    mode: ResponseMode = ResponseMode.SPEAKABLE
    max_sources: int = 6


class QuerySource(BaseModel):
    path: str
    heading: str | None
    start_line: int
    end_line: int
    score: float


class QueryAnswer(BaseModel):
    say_this: str
    supporting_points: list[str]
    personal_examples: list[PersonalExample]


class QueryResponse(BaseModel):
    answer: QueryAnswer
    sources: list[QuerySource]
    confidence: Confidence
    limitations: list[str]
    timing_ms: dict[str, float]
