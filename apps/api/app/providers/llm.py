from __future__ import annotations

import json
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.generation.prompt import build_prompt
from app.generation.schema import AnswerDraft, ResponseMode
from app.retrieval.context import RetrievedChunk


class GenerationError(Exception):
    """Raised when the LLM provider cannot produce a valid AnswerDraft.

    Covers both structured-output failures (invalid JSON, schema mismatch)
    and network-level failures against Ollama (connection refused, timeout,
    non-2xx status) -- a dropped workstation connection mid-query must
    degrade to this typed error, not propagate as a raw httpx exception into
    a 500. generation/service.py's answer() catches this uniformly regardless
    of which underlying cause produced it.
    """


class LLMProvider(Protocol):
    def generate_answer(
        self, query: str, context: list[RetrievedChunk], mode: ResponseMode
    ) -> AnswerDraft: ...


class OllamaLLMProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)

    def generate_answer(
        self, query: str, context: list[RetrievedChunk], mode: ResponseMode
    ) -> AnswerDraft:
        messages = build_prompt(query, context)
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                content = self._chat_once(messages)
                return AnswerDraft.model_validate_json(content)
            except (ValidationError, json.JSONDecodeError, httpx.HTTPError) as exc:
                last_error = exc
        raise GenerationError(f"failed to get a valid structured answer after retry: {last_error}")

    def _chat_once(self, messages: list[dict[str, str]]) -> str:
        response = self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": messages,
                "format": AnswerDraft.model_json_schema(),
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
