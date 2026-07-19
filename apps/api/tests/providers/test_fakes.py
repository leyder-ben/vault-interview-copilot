from app.generation.schema import AnswerDraft, Confidence, ResponseMode
from app.retrieval.context import RetrievedChunk
from tests.providers.fakes import FakeLLMProvider

_CONTEXT = [
    RetrievedChunk(chunk_id=101, vault_path="A.md", heading_path="H", content="c", rrf_score=0.05),
    RetrievedChunk(chunk_id=205, vault_path="B.md", heading_path="H", content="c", rrf_score=0.03),
]


def test_fake_provider_records_calls():
    fake = FakeLLMProvider()
    fake.generate_answer("query one", _CONTEXT, ResponseMode.SPEAKABLE)
    assert fake.calls == [("query one", _CONTEXT, ResponseMode.SPEAKABLE)]


def test_fake_provider_default_response_cites_all_given_context_chunk_ids():
    fake = FakeLLMProvider()
    draft = fake.generate_answer("query", _CONTEXT, ResponseMode.SPEAKABLE)
    assert draft.used_source_chunk_ids == [101, 205]


def test_fake_provider_default_response_cites_nothing_for_empty_context():
    fake = FakeLLMProvider()
    draft = fake.generate_answer("query", [], ResponseMode.SPEAKABLE)
    assert draft.used_source_chunk_ids == []


def test_fake_provider_returns_explicit_response_when_given():
    canned = AnswerDraft(say_this="Canned answer.", confidence=Confidence.LOW, limitations=["test"])
    fake = FakeLLMProvider(response=canned)
    draft = fake.generate_answer("query", _CONTEXT, ResponseMode.SPEAKABLE)
    assert draft is canned
