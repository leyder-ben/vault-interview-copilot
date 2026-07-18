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
