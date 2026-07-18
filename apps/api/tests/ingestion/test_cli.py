import app.ingestion.cli as cli_module
from tests.ingestion.fakes import FakeEmbeddingProvider


def test_main_runs_index_and_prints_summary(tmp_path, db_session, monkeypatch, capsys):
    (tmp_path / "Note-A.md").write_text("# Note A\n\nSome content.\n", encoding="utf-8")

    monkeypatch.setattr(cli_module.settings, "vault_path", str(tmp_path))
    monkeypatch.setattr(cli_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        cli_module, "OllamaEmbeddingProvider", lambda base_url: FakeEmbeddingProvider()
    )

    cli_module.main()

    captured = capsys.readouterr()
    assert "status=success" in captured.out
    assert "added=1" in captured.out


def test_parse_args_vault_path_flag_overrides():
    args = cli_module._parse_args(["--vault-path", "/some/vault"])
    assert args.vault_path == "/some/vault"


def test_parse_args_vault_path_omitted_is_none():
    args = cli_module._parse_args([])
    assert args.vault_path is None
