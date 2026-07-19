from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.generation.schema import (
    AnswerDraft,
    Confidence,
    PersonalExample,
    ResponseMode,
    downgrade_confidence,
)
from app.providers.llm import GenerationError, LLMProvider
from app.retrieval.context import RetrievedChunk
from app.retrieval.sources import SourceCitation, resolve_sources


@dataclass
class ResolvedSource:
    citation: SourceCitation
    score: float


@dataclass
class AnswerResult:
    draft: AnswerDraft
    sources: list[ResolvedSource]


def _stub_draft(mode: ResponseMode) -> AnswerDraft:
    return AnswerDraft(
        say_this=f"The '{mode.value}' response mode isn't implemented yet.",
        confidence=Confidence.LOW,
        limitations=["mode not implemented"],
    )


def _abstention_draft() -> AnswerDraft:
    return AnswerDraft(
        say_this="I don't have enough evidence in the vault to answer this.",
        confidence=Confidence.LOW,
        limitations=["The vault doesn't contain enough evidence to answer this."],
    )


def _error_draft() -> AnswerDraft:
    return AnswerDraft(
        say_this="Generation failed for this query.",
        confidence=Confidence.LOW,
        limitations=["Generation failed; please try again."],
    )


def _filter_examples(
    examples: list[PersonalExample], context_ids: set[int]
) -> tuple[list[PersonalExample], bool]:
    filtered: list[PersonalExample] = []
    dropped = False
    for example in examples:
        surviving_ids = [cid for cid in example.source_chunk_ids if cid in context_ids]
        if not surviving_ids:
            dropped = True
            continue
        if len(surviving_ids) != len(example.source_chunk_ids):
            dropped = True
        filtered.append(
            PersonalExample(
                project=example.project, example=example.example, source_chunk_ids=surviving_ids
            )
        )
    return filtered, dropped


def answer(
    session: Session,
    llm_provider: LLMProvider,
    raw_query: str,
    mode: ResponseMode,
    context: list[RetrievedChunk],
    score_threshold: float | None = None,
) -> AnswerResult:
    if mode != ResponseMode.SPEAKABLE:
        return AnswerResult(draft=_stub_draft(mode), sources=[])

    if score_threshold is None:
        score_threshold = settings.abstention_score_threshold

    if not context or context[0].rrf_score < score_threshold:
        return AnswerResult(draft=_abstention_draft(), sources=[])

    try:
        draft = llm_provider.generate_answer(raw_query, context, mode)
    except GenerationError:
        return AnswerResult(draft=_error_draft(), sources=[])

    context_ids = {c.chunk_id for c in context}
    used_ids = [cid for cid in draft.used_source_chunk_ids if cid in context_ids]
    used_dropped = len(used_ids) != len(draft.used_source_chunk_ids)
    examples, examples_dropped = _filter_examples(draft.personal_examples, context_ids)

    if used_dropped or examples_dropped:
        confidence = downgrade_confidence(draft.confidence)
        limitations = [
            *draft.limitations,
            "Some cited sources could not be verified and were removed; confidence reduced.",
        ]
    else:
        confidence = draft.confidence
        limitations = draft.limitations

    surviving_ids = sorted(set(used_ids) | {cid for ex in examples for cid in ex.source_chunk_ids})
    citations = resolve_sources(session, surviving_ids)
    score_by_id = {c.chunk_id: c.rrf_score for c in context}
    sources = [
        ResolvedSource(citation=citation, score=score_by_id.get(citation.chunk_id, 0.0))
        for citation in citations
    ]

    final_draft = AnswerDraft(
        say_this=draft.say_this,
        supporting_points=draft.supporting_points,
        personal_examples=examples,
        used_source_chunk_ids=used_ids,
        confidence=confidence,
        limitations=limitations,
    )
    return AnswerResult(draft=final_draft, sources=sources)
