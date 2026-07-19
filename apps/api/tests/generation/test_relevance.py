from app.generation.relevance import citation_relevance_score
from tests.generation.relevance_fixtures import CHUNK_CONTENT, LABELED_PAIRS


def test_identical_text_scores_high():
    assert (
        citation_relevance_score(
            "terraform state drift management", "terraform state drift management"
        )
        == 1.0
    )


def test_no_overlap_scores_zero():
    assert (
        citation_relevance_score("terraform state drift", "completely unrelated topic entirely")
        == 0.0
    )


def test_empty_chunk_content_scores_zero():
    assert citation_relevance_score("", "some claim text") == 0.0


def test_stopwords_are_excluded_from_scoring():
    # "the", "a", "is" etc. are stopwords -- sharing only these should not
    # inflate the score for otherwise-unrelated content.
    assert citation_relevance_score("the state is a thing", "the answer is a different thing") < 1.0


def test_short_words_are_excluded_from_scoring():
    # Words of length <= 2 (e.g. "to", "of", "an") are filtered as noise.
    score = citation_relevance_score("go to it", "go to it")
    assert (
        score == 0.0
    )  # every word here is <= 2 chars or a stopword, so nothing significant remains


def test_measured_threshold_precision_and_recall_on_labeled_set():
    """Locks in the measured threshold's real-world performance as a
    regression guard, the same way test_retrieval_eval.py locks in
    Recall@5 -- see docs/superpowers/plans/2026-07-19-phase-3-grounded-
    answers.md's "Citation cross-check verifies membership, not relevance"
    section for the full measurement (92 hand-labeled pairs across 4 chunks
    and 4 real queries against sample-vault content).

    Measured 2026-07-19: precision=0.93, recall=0.97 at threshold=0.30.
    """
    threshold = 0.30
    tp = fp = fn = tn = 0  # tp/fp/fn/tn are w.r.t. "correctly flags as NOT relevant"
    for chunk_id, claim_text, expected_relevant in LABELED_PAIRS:
        score = citation_relevance_score(CHUNK_CONTENT[chunk_id], claim_text)
        predicted_relevant = score >= threshold
        if not expected_relevant and not predicted_relevant:
            tp += 1  # correctly flagged as not relevant
        elif expected_relevant and not predicted_relevant:
            fp += 1  # wrongly flagged -- a genuinely relevant citation stripped
        elif not expected_relevant and predicted_relevant:
            fn += 1  # missed -- a not-relevant citation survives
        else:
            tn += 1  # correctly kept

    precision = tp / (tp + fp)
    recall = tp / (tp + fn)

    assert precision >= 0.90, f"precision regressed: {precision:.2f} (tp={tp} fp={fp})"
    assert recall >= 0.95, f"recall regressed: {recall:.2f} (tp={tp} fn={fn})"
