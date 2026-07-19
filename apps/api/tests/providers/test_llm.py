import json

import httpx
import pytest

from app.generation.schema import Confidence, ResponseMode
from app.providers.llm import GenerationError, OllamaLLMProvider
from app.retrieval.context import RetrievedChunk

VALID_DRAFT_JSON = json.dumps(
    {
        "say_this": "Terraform drift means the deployed infra no longer matches state.",
        "supporting_points": ["Caused by manual changes."],
        "personal_examples": [],
        "used_source_chunk_ids": [101],
        "confidence": "high",
        "limitations": [],
    }
)

_CONTEXT = [
    RetrievedChunk(
        chunk_id=101, vault_path="Terraform.md", heading_path="Drift", content="...", rrf_score=0.05
    )
]


def _client_with_response(content: str, model_check: str = "gpt-oss:20b"):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        assert body["model"] == model_check
        assert body["messages"][1]["content"] == "terraform drift prod"
        assert "format" in body
        assert body["stream"] is False
        assert body["think"] == "low"
        return httpx.Response(200, json={"message": {"content": content}})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_generate_answer_returns_parsed_answer_draft():
    client = _client_with_response(VALID_DRAFT_JSON)
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )

    draft = provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)

    assert draft.say_this.startswith("Terraform drift means")
    assert draft.confidence == Confidence.HIGH
    assert draft.used_source_chunk_ids == [101]


def test_generate_answer_retries_once_on_invalid_json_then_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200, json={"message": {"content": "not valid json"}})
        return httpx.Response(200, json={"message": {"content": VALID_DRAFT_JSON}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )

    draft = provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)

    assert calls["count"] == 2
    assert draft.confidence == Confidence.HIGH


def test_generate_answer_raises_generation_error_after_two_failed_attempts():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "still not valid json"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )

    with pytest.raises(GenerationError):
        provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)


def test_generate_answer_raises_generation_error_on_missing_required_field():
    invalid_shape = json.dumps({"supporting_points": [], "confidence": "high"})  # missing say_this

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": invalid_shape}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )

    with pytest.raises(GenerationError):
        provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)


def test_generate_answer_posts_to_chat_endpoint_with_configured_model():
    client = _client_with_response(VALID_DRAFT_JSON, model_check="custom-model:latest")
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="custom-model:latest", client=client
    )
    draft = provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)
    # The handler asserts the request body's "model" field matches model_check;
    # this asserts the call actually completed and returned a valid draft, so
    # the test fails loudly (not silently) if the handler is ever bypassed.
    assert draft.confidence == Confidence.HIGH


def test_generate_answer_sets_think_low_in_request_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.read())
        return httpx.Response(200, json={"message": {"content": VALID_DRAFT_JSON}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )
    provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)

    # gpt-oss:20b defaults to unconstrained/high reasoning effort when "think"
    # is unset -- measured at ~10.4s median / 17-22s tail per call with no
    # benefit to this app. "low" cut that to 2-5s across 30+ real reps with
    # no loss of structured-output validity (think=false was tested and
    # rejected -- it breaks structured output entirely). See
    # docs/architecture/11-locked-decisions.md for the full measurement.
    assert captured["body"]["think"] == "low"


def test_generate_answer_raises_generation_error_on_connection_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )

    with pytest.raises(GenerationError):
        provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)


def test_generate_answer_raises_generation_error_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )

    with pytest.raises(GenerationError):
        provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)


def test_generate_answer_raises_generation_error_on_http_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )

    with pytest.raises(GenerationError):
        provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)


def test_generate_answer_retries_once_on_connection_failure_then_succeeds():
    """Simulates the workstation Ollama dropping mid-call and recovering — the
    live-interview failure mode this fix exists for."""
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"message": {"content": VALID_DRAFT_JSON}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        base_url="http://workstation:11434", model="gpt-oss:20b", client=client
    )

    draft = provider.generate_answer("terraform drift prod", _CONTEXT, ResponseMode.SPEAKABLE)

    assert calls["count"] == 2
    assert draft.confidence == Confidence.HIGH
