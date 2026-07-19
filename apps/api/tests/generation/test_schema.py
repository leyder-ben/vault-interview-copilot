import pytest
from pydantic import ValidationError

from app.generation.schema import (
    AnswerDraft,
    Confidence,
    PersonalExample,
    QueryRequest,
    ResponseMode,
    downgrade_confidence,
)


def test_answer_draft_requires_say_this_and_confidence():
    with pytest.raises(ValidationError):
        AnswerDraft()


def test_answer_draft_defaults_list_fields_to_empty():
    draft = AnswerDraft(say_this="Hello.", confidence=Confidence.HIGH)
    assert draft.supporting_points == []
    assert draft.personal_examples == []
    assert draft.used_source_chunk_ids == []
    assert draft.limitations == []


def test_answer_draft_accepts_full_shape():
    draft = AnswerDraft(
        say_this="Terraform drift means the deployed infra no longer matches state.",
        supporting_points=["Caused by manual changes.", "Detected via terraform plan."],
        personal_examples=[
            PersonalExample(
                project="Whetstone",
                example="Caught drift via scheduled plan.",
                source_chunk_ids=[101],
            )
        ],
        used_source_chunk_ids=[101, 205],
        confidence=Confidence.HIGH,
        limitations=[],
    )
    assert draft.personal_examples[0].project == "Whetstone"


def test_downgrade_confidence_steps_down_one_level():
    assert downgrade_confidence(Confidence.HIGH) == Confidence.MEDIUM
    assert downgrade_confidence(Confidence.MEDIUM) == Confidence.LOW


def test_downgrade_confidence_low_is_a_floor():
    assert downgrade_confidence(Confidence.LOW) == Confidence.LOW


def test_query_request_defaults_mode_and_max_sources():
    request = QueryRequest(query="terraform drift prod")
    assert request.mode == ResponseMode.SPEAKABLE
    assert request.max_sources == 6


def test_query_request_accepts_explicit_mode():
    request = QueryRequest(
        query="compare terraform vs pulumi", mode=ResponseMode.COMPARE, max_sources=3
    )
    assert request.mode == ResponseMode.COMPARE
    assert request.max_sources == 3
