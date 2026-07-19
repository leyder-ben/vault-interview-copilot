import textwrap
from datetime import UTC, datetime

import app.evaluation.cli as cli_module
from app.db.models import Chunk, Note
from tests.ingestion.fakes import FakeEmbeddingProvider


def test_parse_args_dataset_flag_sample_vault():
    args = cli_module._parse_args(["--dataset", "sample-vault"])
    assert args.dataset == "sample-vault"


def test_parse_args_dataset_flag_private():
    args = cli_module._parse_args(["--dataset", "private"])
    assert args.dataset == "private"


def test_parse_args_rejects_unknown_dataset():
    import pytest

    with pytest.raises(SystemExit):
        cli_module._parse_args(["--dataset", "nonsense"])


def test_main_runs_eval_and_prints_both_forms(tmp_path, db_session, monkeypatch, capsys):
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

    fixtures_path = tmp_path / "fixtures.yaml"
    fixtures_path.write_text(
        textwrap.dedent(
            """
            - id: fixture-1
              query: "tf drift"
              interviewer_phrasing: "How do you know if infrastructure has drifted?"
              expected_notes:
                - "Terraform.md"
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        cli_module, "OllamaEmbeddingProvider", lambda base_url, model=None: FakeEmbeddingProvider()
    )
    monkeypatch.setitem(cli_module.DATASET_PATHS, "sample-vault", str(fixtures_path))

    cli_module.main(["--dataset", "sample-vault"])

    captured = capsys.readouterr()
    assert "Shorthand" in captured.out
    assert "Natural phrasing" in captured.out
    assert "Recall@5" in captured.out
