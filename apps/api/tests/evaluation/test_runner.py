import textwrap
from datetime import UTC, datetime

from app.db.models import Chunk, Note
from app.evaluation.runner import load_fixtures, run_eval
from tests.ingestion.fakes import FakeEmbeddingProvider


def _write_fixture_file(tmp_path, contents):
    path = tmp_path / "fixtures.yaml"
    path.write_text(textwrap.dedent(contents), encoding="utf-8")
    return str(path)


def test_load_fixtures_parses_both_query_forms(tmp_path):
    path = _write_fixture_file(
        tmp_path,
        """
        - id: fixture-1
          query: "tf drift"
          interviewer_phrasing: "How do you know if your infrastructure has drifted?"
          expected_notes:
            - "Terraform.md"
          expected_concepts:
            - state drift
          expected_personal_project:
            - Meridian
        """,
    )

    fixtures = load_fixtures(path)

    assert len(fixtures) == 1
    assert fixtures[0].id == "fixture-1"
    assert fixtures[0].query == "tf drift"
    assert fixtures[0].interviewer_phrasing == "How do you know if your infrastructure has drifted?"
    assert fixtures[0].expected_notes == ["Terraform.md"]


def test_load_fixtures_handles_missing_interviewer_phrasing(tmp_path):
    path = _write_fixture_file(
        tmp_path,
        """
        - id: fixture-1
          query: "tf drift"
          expected_notes:
            - "Terraform.md"
        """,
    )

    fixtures = load_fixtures(path)

    assert fixtures[0].interviewer_phrasing is None


def test_run_eval_scores_shorthand_and_natural_forms_separately(db_session, tmp_path):
    note = Note(
        vault_path="Terraform.md",
        filename="Terraform.md",
        title="Terraform.md",
        content_hash="hash-terraform",
        modified_at=datetime.now(UTC),
    )
    db_session.add(note)
    db_session.flush()
    content = "Document: Terraform\nState drift happens when infrastructure diverges."
    db_session.add(
        Chunk(
            note_id=note.id,
            chunk_index=0,
            start_line=1,
            end_line=5,
            content=content,
            content_with_context=content,
            content_hash="chash-terraform",
            embedding=FakeEmbeddingProvider().embed_batch([content])[0],
        )
    )
    db_session.commit()

    path = _write_fixture_file(
        tmp_path,
        """
        - id: fixture-1
          query: "tf drift"
          interviewer_phrasing: "How do you know if your infrastructure has drifted?"
          expected_notes:
            - "Terraform.md"
        """,
    )
    fixtures = load_fixtures(path)

    report = run_eval(db_session, FakeEmbeddingProvider(), fixtures)

    shorthand_results = [r for r in report.results if r.query_form == "shorthand"]
    natural_results = [r for r in report.results if r.query_form == "natural"]
    assert len(shorthand_results) == 1
    assert len(natural_results) == 1
    assert shorthand_results[0].query_text == "tf drift"
    assert natural_results[0].query_text == "How do you know if your infrastructure has drifted?"
    assert 0.0 <= report.shorthand.recall_at_5 <= 1.0
    assert 0.0 <= report.natural.recall_at_5 <= 1.0


def test_run_eval_skips_natural_form_when_absent(db_session, tmp_path):
    path = _write_fixture_file(
        tmp_path,
        """
        - id: fixture-1
          query: "tf drift"
          expected_notes:
            - "Terraform.md"
        """,
    )
    fixtures = load_fixtures(path)

    report = run_eval(db_session, FakeEmbeddingProvider(), fixtures)

    assert len(report.results) == 1
    assert report.results[0].query_form == "shorthand"
