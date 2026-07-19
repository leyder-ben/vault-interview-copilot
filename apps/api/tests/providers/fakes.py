from __future__ import annotations

from app.generation.schema import AnswerDraft, Confidence, ResponseMode
from app.retrieval.context import RetrievedChunk


class FakeLLMProvider:
    """Deterministic LLM provider for tests — no live Ollama dependency.

    When `response` isn't given, the default auto-generates a draft that
    cites every chunk_id in whatever context it's called with — this lets
    citation-validity tests work against real DB-assigned chunk IDs without
    each test needing to hand-construct a canned response.
    """

    def __init__(self, response: AnswerDraft | None = None):
        self.calls: list[tuple[str, list[RetrievedChunk], ResponseMode]] = []
        self._response = response

    def generate_answer(
        self, query: str, context: list[RetrievedChunk], mode: ResponseMode
    ) -> AnswerDraft:
        self.calls.append((query, context, mode))
        if self._response is not None:
            return self._response
        return AnswerDraft(
            say_this="This is a fake answer for testing.",
            supporting_points=[],
            personal_examples=[],
            used_source_chunk_ids=[c.chunk_id for c in context],
            confidence=Confidence.HIGH,
            limitations=[],
        )
