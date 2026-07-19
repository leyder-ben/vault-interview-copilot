from pathlib import Path

from app.evaluation.runner import load_fixtures, run_eval
from app.ingestion.indexer import run_index
from tests.ingestion.fakes import FakeEmbeddingProvider

SAMPLE_VAULT = Path(__file__).resolve().parents[4] / "sample-vault"
FIXTURES_PATH = (
    Path(__file__).resolve().parents[4]
    / "evaluation"
    / "datasets"
    / "sample-vault"
    / "meridian-fixtures.yaml"
)


def test_shorthand_recall_at_5_meets_measured_threshold(db_session):
    provider = FakeEmbeddingProvider()
    index_result = run_index(
        db_session,
        str(SAMPLE_VAULT),
        provider,
        max_section_tokens=400,
        embedding_model="nomic-embed-text",
    )
    assert index_result.status == "success"

    fixtures = load_fixtures(str(FIXTURES_PATH))
    report = run_eval(db_session, provider, fixtures)

    # Measured 2026-07-18 against sample-vault + retrofitted interviewer_phrasing
    # fixtures (Task 11). First measurement was 0.8333 (5/6): "jenkins cant
    # containerize docker plugin" missed because websearch_to_tsquery ANDs every
    # unquoted term, and the filler word "cant" doesn't lexically match anywhere
    # in the target note (which says "doesn't", not "can't"/"cant") — that zeroed
    # out full-text results entirely even though 4 of 5 terms were strong exact
    # matches. Fixed in app/retrieval/fulltext.py: search_fulltext now falls back
    # to an OR-of-terms tsquery when the strict AND query returns nothing. One
    # re-run after the fix measured 1.0 (6/6); that is the number locked in here,
    # per this task's one-fix-one-remeasure process — see notes above.
    assert report.shorthand.recall_at_5 >= 1.0
