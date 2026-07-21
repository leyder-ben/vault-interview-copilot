from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.generation.relevance import citation_relevance_score
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


def _is_citation_valid(
    chunk_id: int,
    context_ids: set[int],
    content_by_id: dict[int, str],
    claim_text: str,
    relevance_threshold: float,
) -> bool:
    """A citation is valid only if the chunk was actually in context (never
    trust an out-of-context ID) AND its content is lexically relevant to the
    claim it's attached to. A real, in-context chunk can still be cited for a
    claim its content doesn't back -- see docs/superpowers/plans/2026-07-19-
    phase-3-grounded-answers.md's "Citation cross-check verifies membership,
    not relevance" section for the finding and the measurement behind
    relevance_threshold."""
    if chunk_id not in context_ids:
        return False
    return citation_relevance_score(content_by_id[chunk_id], claim_text) >= relevance_threshold


def _filter_examples(
    examples: list[PersonalExample],
    context_ids: set[int],
    content_by_id: dict[int, str],
    claim_text: str,
    relevance_threshold: float,
) -> tuple[list[PersonalExample], bool]:
    filtered: list[PersonalExample] = []
    dropped = False
    for example in examples:
        surviving_ids = [
            cid
            for cid in example.source_chunk_ids
            if _is_citation_valid(cid, context_ids, content_by_id, claim_text, relevance_threshold)
        ]
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
    relevance_threshold: float | None = None,
) -> AnswerResult:
    if mode != ResponseMode.SPEAKABLE:
        return AnswerResult(draft=_stub_draft(mode), sources=[])

    if score_threshold is None:
        score_threshold = settings.abstention_score_threshold
    if relevance_threshold is None:
        relevance_threshold = settings.citation_relevance_threshold

    if not context or context[0].rrf_score < score_threshold:
        return AnswerResult(draft=_abstention_draft(), sources=[])

    try:
        draft = llm_provider.generate_answer(raw_query, context, mode)
    except GenerationError:
        return AnswerResult(draft=_error_draft(), sources=[])

    context_ids = {c.chunk_id for c in context}
    content_by_id = {c.chunk_id: c.content for c in context}
    used_ids = [
        cid
        for cid in draft.used_source_chunk_ids
        if _is_citation_valid(cid, context_ids, content_by_id, draft.say_this, relevance_threshold)
    ]
    used_dropped = len(used_ids) != len(draft.used_source_chunk_ids)
    examples, examples_dropped = _filter_examples(
        draft.personal_examples, context_ids, content_by_id, draft.say_this, relevance_threshold
    )

    # The model can draw on retrieved context in `say_this` without
    # populating `used_source_chunk_ids` -- the system prompt forbids this
    # but doesn't always prevent it (non-deterministic across identical
    # calls; see docs/superpowers/plans/2026-07-19-phase-3-grounded-
    # answers.md's citation-recall follow-up). This check doesn't try to
    # verify what the model actually used (no lexical/relevance matching,
    # no new failure surface) -- it only refuses to let a self-reported
    # HIGH confidence stand uncontested when the model cited nothing at
    # all. A self-reported MEDIUM/LOW with no citations is left alone: the
    # model already hedged appropriately (e.g. "not aware of X in your
    # notes"), and re-flagging that would misrepresent an honest answer as
    # a suspected violation.
    missing_citations = not draft.used_source_chunk_ids and draft.confidence == Confidence.HIGH

    if used_dropped or examples_dropped:
        confidence = downgrade_confidence(draft.confidence)
        limitations = [
            *draft.limitations,
            "Some cited sources could not be verified and were removed; confidence reduced.",
        ]
    elif missing_citations:
        confidence = downgrade_confidence(draft.confidence)
        limitations = [
            *draft.limitations,
            "The model reported high confidence without citing any source; confidence reduced.",
        ]
    else:
        confidence = draft.confidence
        limitations = draft.limitations

    # The model can self-report a below-HIGH confidence and leave
    # `limitations` empty -- the prompt only requires an explanation for
    # one specific case (an unsupported personal claim), not generally
    # whenever confidence drops, and confirmed non-deterministic in
    # practice (identical query/context, repeated calls, sometimes
    # explained, sometimes not). This doesn't try to fix the model's
    # prompt adherence -- it just refuses to let a below-HIGH confidence
    # stand with no stated reason at all.
    if confidence != Confidence.HIGH and not limitations:
        limitations = [f"Confidence is {confidence.value}; the model did not explain why."]

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
