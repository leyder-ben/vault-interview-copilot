from datetime import UTC, datetime

from app.db.models import Chunk, Note
from app.generation.schema import AnswerDraft, Confidence, PersonalExample, ResponseMode
from app.generation.service import answer
from app.providers.llm import GenerationError
from app.retrieval.context import RetrievedChunk
from tests.providers.fakes import FakeLLMProvider


def _make_chunk(db_session, vault_path, heading, content):
    note = Note(
        vault_path=vault_path,
        filename=vault_path,
        title=vault_path,
        content_hash=f"hash-{vault_path}",
        modified_at=datetime.now(UTC),
    )
    db_session.add(note)
    db_session.flush()
    chunk = Chunk(
        note_id=note.id,
        heading_path=heading,
        chunk_index=0,
        start_line=1,
        end_line=5,
        content=content,
        content_with_context=content,
        content_hash=f"chash-{vault_path}",
    )
    db_session.add(chunk)
    db_session.flush()
    db_session.commit()
    return chunk.id


def test_non_speakable_mode_returns_stub_without_calling_llm(db_session):
    fake = FakeLLMProvider()
    result = answer(db_session, fake, "compare terraform vs pulumi", ResponseMode.COMPARE, [])
    assert fake.calls == []
    assert result.draft.confidence == Confidence.LOW
    assert "not implemented" in " ".join(result.draft.limitations)


def test_empty_context_abstains_without_calling_llm(db_session):
    fake = FakeLLMProvider()
    result = answer(db_session, fake, "obscure query", ResponseMode.SPEAKABLE, [])
    assert fake.calls == []
    assert result.draft.confidence == Confidence.LOW
    assert result.sources == []


def test_low_score_context_abstains_without_calling_llm(db_session):
    fake = FakeLLMProvider()
    weak_context = [
        RetrievedChunk(
            chunk_id=1, vault_path="A.md", heading_path=None, content="c", rrf_score=0.001
        )
    ]
    result = answer(
        db_session, fake, "obscure query", ResponseMode.SPEAKABLE, weak_context, score_threshold=0.5
    )
    assert fake.calls == []
    assert result.draft.confidence == Confidence.LOW


def test_strong_score_context_calls_llm_and_resolves_sources(db_session):
    chunk_id = _make_chunk(db_session, "Terraform.md", "Drift", "State drift content.")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="State drift content.",
            rrf_score=0.9,
        )
    ]
    fake = FakeLLMProvider()  # default response cites all given context chunk_ids

    result = answer(
        db_session,
        fake,
        "terraform drift",
        ResponseMode.SPEAKABLE,
        context,
        score_threshold=0.01,
        relevance_threshold=0.0,  # this test is about membership + resolution, not relevance
    )

    assert len(fake.calls) == 1
    assert result.draft.confidence == Confidence.HIGH
    assert len(result.sources) == 1
    assert result.sources[0].citation.chunk_id == chunk_id
    assert result.sources[0].citation.path == "Terraform.md"
    assert result.sources[0].score == 0.9


def test_fabricated_used_source_id_is_dropped_and_confidence_downgraded(db_session):
    chunk_id = _make_chunk(db_session, "Terraform.md", "Drift", "content")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="content",
            rrf_score=0.9,
        )
    ]
    fabricated_draft = AnswerDraft(
        say_this="Answer citing a fabricated source.",
        used_source_chunk_ids=[chunk_id, 999999],  # 999999 not in context
        confidence=Confidence.HIGH,
    )
    fake = FakeLLMProvider(response=fabricated_draft)

    result = answer(
        db_session,
        fake,
        "terraform drift",
        ResponseMode.SPEAKABLE,
        context,
        score_threshold=0.01,
        relevance_threshold=0.0,  # this test is about membership, not relevance
    )

    assert result.draft.used_source_chunk_ids == [chunk_id]
    assert result.draft.confidence == Confidence.MEDIUM
    assert len(result.sources) == 1


def test_personal_example_losing_all_source_ids_is_dropped_entirely(db_session):
    chunk_id = _make_chunk(db_session, "Terraform.md", "Drift", "content")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="content",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="Answer with a fully-fabricated personal example.",
        personal_examples=[
            PersonalExample(project="Ghost", example="Never happened.", source_chunk_ids=[999999])
        ],
        confidence=Confidence.HIGH,
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "query", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.personal_examples == []
    assert result.draft.confidence == Confidence.MEDIUM


def test_personal_example_losing_some_source_ids_keeps_example_with_filtered_ids(db_session):
    real_id = _make_chunk(db_session, "Terraform.md", "Drift", "content")
    context = [
        RetrievedChunk(
            chunk_id=real_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="content",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="Answer with a partially-fabricated personal example.",
        personal_examples=[
            PersonalExample(
                project="Whetstone",
                example="Real and fake mixed.",
                source_chunk_ids=[real_id, 999999],
            )
        ],
        confidence=Confidence.HIGH,
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session,
        fake,
        "query",
        ResponseMode.SPEAKABLE,
        context,
        score_threshold=0.01,
        relevance_threshold=0.0,  # this test is about membership, not relevance
    )

    assert len(result.draft.personal_examples) == 1
    assert result.draft.personal_examples[0].source_chunk_ids == [real_id]
    assert result.draft.confidence == Confidence.MEDIUM


def test_confidence_downgrade_floor_stays_low(db_session):
    chunk_id = _make_chunk(db_session, "Terraform.md", "Drift", "content")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="content",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="Already-low-confidence answer citing a fabricated source.",
        used_source_chunk_ids=[999999],
        confidence=Confidence.LOW,
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "query", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.confidence == Confidence.LOW


def test_relevant_citation_survives_the_relevance_check(db_session):
    chunk_id = _make_chunk(
        db_session,
        "Terraform.md",
        "Drift",
        "State drift happens when infrastructure diverges from the state file, "
        "usually caused by manual console changes.",
    )
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="State drift happens when infrastructure diverges from the state file, "
            "usually caused by manual console changes.",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="State drift happens when infrastructure diverges from the state file "
        "due to manual console changes.",
        used_source_chunk_ids=[chunk_id],
        confidence=Confidence.HIGH,
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "terraform drift", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.used_source_chunk_ids == [chunk_id]
    assert result.draft.confidence == Confidence.HIGH
    assert len(result.sources) == 1


def test_irrelevant_in_context_citation_is_dropped_and_confidence_downgraded(db_session):
    # chunk_id is a real, in-context ID (passes membership) but its content
    # has nothing to do with the claim it's cited against -- this is the
    # gap the plain membership check can't see. See docs/superpowers/plans/
    # 2026-07-19-phase-3-grounded-answers.md's "Citation cross-check
    # verifies membership, not relevance" section.
    chunk_id = _make_chunk(
        db_session,
        "Terraform.md",
        "Drift",
        "State drift happens when infrastructure diverges from the state file, "
        "usually caused by manual console changes.",
    )
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="State drift happens when infrastructure diverges from the state file, "
            "usually caused by manual console changes.",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="I prefer blue-green deployments because they provide a clean "
        "rollback path with minimal downtime.",
        used_source_chunk_ids=[chunk_id],
        confidence=Confidence.HIGH,
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "rollout strategy", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.used_source_chunk_ids == []
    assert result.draft.confidence == Confidence.MEDIUM
    assert result.sources == []
    assert "could not be verified" in " ".join(result.draft.limitations)


def test_personal_example_source_id_dropped_for_irrelevance_not_just_membership(db_session):
    chunk_id = _make_chunk(
        db_session,
        "Docker.md",
        "Fix",
        "Mounted the host's Docker socket into the agent container so docker build "
        "had somewhere real to run against.",
    )
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Docker.md",
            heading_path="Fix",
            content="Mounted the host's Docker socket into the agent container so docker build "
            "had somewhere real to run against.",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="On Meridian I lean toward blue-green deployments for major releases.",
        personal_examples=[
            PersonalExample(
                project="Meridian",
                example="Prefer blue-green for major releases.",
                source_chunk_ids=[chunk_id],
            )
        ],
        confidence=Confidence.HIGH,
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "rollout strategy", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.personal_examples == []
    assert result.draft.confidence == Confidence.MEDIUM


def test_high_confidence_with_no_citations_is_downgraded_and_flagged(db_session):
    # The model can silently draw on retrieved context in `say_this` while
    # leaving `used_source_chunk_ids` empty -- a structured-output
    # compliance failure the system prompt explicitly forbids but doesn't
    # always avoid. This is a deterministic, membership/relevance-free
    # check: it doesn't try to verify *what* the model used, it just
    # refuses to let "high confidence, zero citations" pass through
    # unflagged. See docs/superpowers/plans/2026-07-19-phase-3-grounded-
    # answers.md's citation-recall follow-up.
    chunk_id = _make_chunk(db_session, "Terraform.md", "Drift", "State drift content.")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="State drift content.",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="Drift happens when infrastructure diverges from the state file.",
        used_source_chunk_ids=[],
        confidence=Confidence.HIGH,
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "terraform drift", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.confidence == Confidence.MEDIUM
    assert result.sources == []
    assert "without citing" in " ".join(result.draft.limitations)


def test_medium_confidence_with_no_citations_is_not_further_downgraded(db_session):
    # An honest self-hedge (model already reported medium confidence and
    # explained why in its own limitations, e.g. "nothing relevant in the
    # notes") must NOT be double-penalized by the new check above -- it
    # already told the truth about not using the context.
    chunk_id = _make_chunk(db_session, "Helm.md", "Usage", "Unrelated content.")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Helm.md",
            heading_path="Usage",
            content="Unrelated content.",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="I'm not aware of Helm usage in your notes; generally it's a package manager.",
        used_source_chunk_ids=[],
        confidence=Confidence.MEDIUM,
        limitations=["No retrieved context mentions Helm usage or related projects."],
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "how do I use helm", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.confidence == Confidence.MEDIUM
    assert result.draft.limitations == [
        "No retrieved context mentions Helm usage or related projects."
    ]


def test_low_confidence_with_no_explanation_gets_a_fallback_limitation(db_session):
    # The model can self-report a below-HIGH confidence and leave
    # `limitations` empty -- the prompt only requires an explanation for
    # one specific case (an unsupported personal claim), not generally
    # whenever confidence drops. Confirmed non-deterministic in practice:
    # identical query/context, repeated calls, sometimes explained,
    # sometimes not. This guard doesn't try to fix the model's prompt
    # adherence -- it just refuses to let a below-HIGH confidence stand
    # with no stated reason at all.
    chunk_id = _make_chunk(db_session, "ECS.md", "Comparison", "Unrelated content.")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="ECS.md",
            heading_path="Comparison",
            content="Unrelated content.",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="I don't have notes comparing Kubernetes and ECS.",
        used_source_chunk_ids=[],
        confidence=Confidence.LOW,
        limitations=[],
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "kubernetes vs ecs", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.confidence == Confidence.LOW
    assert result.draft.limitations == ["Confidence is low; the model did not explain why."]


def test_medium_confidence_with_no_explanation_gets_a_fallback_limitation(db_session):
    chunk_id = _make_chunk(db_session, "ECS.md", "Comparison", "Unrelated content.")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="ECS.md",
            heading_path="Comparison",
            content="Unrelated content.",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="I don't have notes comparing Kubernetes and ECS.",
        used_source_chunk_ids=[],
        confidence=Confidence.MEDIUM,
        limitations=[],
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "kubernetes vs ecs", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.confidence == Confidence.MEDIUM
    assert result.draft.limitations == ["Confidence is medium; the model did not explain why."]


def test_high_confidence_with_real_citations_gets_no_fallback_limitation(db_session):
    # Regression guard: a genuinely well-cited HIGH-confidence answer must
    # not be flagged just because `limitations` happens to be empty --
    # empty limitations on a HIGH-confidence, real-citation answer is the
    # expected, healthy case, not a gap to fill.
    chunk_id = _make_chunk(db_session, "Terraform.md", "Drift", "State drift content.")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="State drift content.",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="Drift happens when infrastructure diverges from the state file.",
        used_source_chunk_ids=[chunk_id],
        confidence=Confidence.HIGH,
        limitations=[],
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session,
        fake,
        "terraform drift",
        ResponseMode.SPEAKABLE,
        context,
        score_threshold=0.01,
        relevance_threshold=0.0,
    )

    assert result.draft.confidence == Confidence.HIGH
    assert result.draft.limitations == []


def test_existing_downgrade_limitation_is_not_double_flagged(db_session):
    # Regression guard: when an existing downgrade branch already appends
    # its own explanatory limitation, the new fallback must not also fire
    # (limitations is non-empty by the time the guard runs).
    chunk_id = _make_chunk(db_session, "Terraform.md", "Drift", "content")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="content",
            rrf_score=0.9,
        )
    ]
    draft = AnswerDraft(
        say_this="Drift happens when infrastructure diverges from the state file.",
        used_source_chunk_ids=[],
        confidence=Confidence.HIGH,
        limitations=[],
    )
    fake = FakeLLMProvider(response=draft)

    result = answer(
        db_session, fake, "terraform drift", ResponseMode.SPEAKABLE, context, score_threshold=0.01
    )

    assert result.draft.confidence == Confidence.MEDIUM
    assert result.draft.limitations == [
        "The model reported high confidence without citing any source; confidence reduced."
    ]


def test_generation_error_returns_typed_error_draft(db_session):
    class AlwaysFailsProvider:
        def generate_answer(self, query, context, mode):
            raise GenerationError("simulated failure")

    chunk_id = _make_chunk(db_session, "Terraform.md", "Drift", "content")
    context = [
        RetrievedChunk(
            chunk_id=chunk_id,
            vault_path="Terraform.md",
            heading_path="Drift",
            content="content",
            rrf_score=0.9,
        )
    ]

    result = answer(
        db_session,
        AlwaysFailsProvider(),
        "query",
        ResponseMode.SPEAKABLE,
        context,
        score_threshold=0.01,
    )

    assert result.draft.confidence == Confidence.LOW
    assert result.sources == []
    assert "failed" in " ".join(result.draft.limitations).lower()
