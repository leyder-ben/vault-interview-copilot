import shutil
from pathlib import Path

from app.db.models import Chunk, Note
from app.ingestion.indexer import run_index
from tests.ingestion.fakes import FakeEmbeddingProvider

SAMPLE_VAULT = Path(__file__).resolve().parents[4] / "sample-vault"


def _copy_sample_vault(tmp_path) -> Path:
    dest = tmp_path / "vault"
    shutil.copytree(SAMPLE_VAULT, dest)
    return dest


def test_second_run_against_unchanged_sample_vault_touches_zero_files(tmp_path, db_session):
    vault = _copy_sample_vault(tmp_path)
    provider = FakeEmbeddingProvider()

    first = run_index(
        db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )
    assert first.files_added > 0

    provider.calls.clear()
    second = run_index(
        db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    assert second.files_added == 0
    assert second.files_updated == 0
    assert second.files_deleted == 0
    assert provider.calls == []


def test_ignore_patterns_exclude_templates_but_keep_source_docs(tmp_path, db_session):
    vault = _copy_sample_vault(tmp_path)
    provider = FakeEmbeddingProvider()

    run_index(
        db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    indexed_paths = {n.vault_path for n in db_session.query(Note).all()}
    assert "03-Projects/Meridian/_Source-Docs/Mock-Interview-Notes.md" in indexed_paths
    assert not any("_Templates" in p for p in indexed_paths)


def test_editing_one_section_only_reembeds_that_chunk(tmp_path, db_session):
    vault = _copy_sample_vault(tmp_path)
    provider = FakeEmbeddingProvider()
    run_index(
        db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    terraform_path = vault / "02-Technical-Reference" / "Terraform" / "Terraform-Fundamentals.md"
    original = terraform_path.read_text(encoding="utf-8")
    edited = original.replace("State drift", "State drift (edited for test)", 1)
    assert edited != original
    terraform_path.write_text(edited, encoding="utf-8")

    provider.calls.clear()
    result = run_index(
        db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    assert result.files_updated == 1
    assert result.files_added == 0
    embedded_texts = [text for call in provider.calls for text in call]
    assert len(embedded_texts) >= 1
    assert any("edited for test" in text for text in embedded_texts)


def test_deleting_a_file_cascades_chunk_cleanup(tmp_path, db_session):
    vault = _copy_sample_vault(tmp_path)
    provider = FakeEmbeddingProvider()
    run_index(
        db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    target = vault / "00-Inbox" / "Quick-Note-Kubernetes-Question.md"
    target.unlink()

    result = run_index(
        db_session, str(vault), provider, max_section_tokens=400, embedding_model="nomic-embed-text"
    )

    assert result.files_deleted == 1
    remaining = (
        db_session.query(Note)
        .filter_by(vault_path="00-Inbox/Quick-Note-Kubernetes-Question.md")
        .first()
    )
    assert remaining is None
    assert db_session.query(Chunk).join(Note).filter(Note.vault_path.like("00-Inbox%")).count() == 0
