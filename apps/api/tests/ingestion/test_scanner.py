from datetime import datetime

from app.ingestion.scanner import compute_content_hash, scan_vault


def _write(base, relative_path, content="# Title\n\nBody text.\n"):
    file_path = base / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def test_scan_returns_indexable_markdown_files(tmp_path):
    _write(tmp_path, "00-Inbox/note.md")
    _write(tmp_path, "02-Technical-Reference/Terraform.md")
    files = scan_vault(tmp_path)
    paths = {f.vault_path for f in files}
    assert paths == {"00-Inbox/note.md", "02-Technical-Reference/Terraform.md"}


def test_scan_ignores_named_folders(tmp_path):
    _write(tmp_path, "_Templates/Story-Template.md")
    _write(tmp_path, ".obsidian/workspace.md")
    _write(tmp_path, "keep/Real-Note.md")
    files = scan_vault(tmp_path)
    paths = {f.vault_path for f in files}
    assert paths == {"keep/Real-Note.md"}


def test_scan_does_not_ignore_source_docs_folder(tmp_path):
    _write(tmp_path, "03-Projects/Meridian/_Source-Docs/Transcript.md")
    files = scan_vault(tmp_path)
    assert {f.vault_path for f in files} == {"03-Projects/Meridian/_Source-Docs/Transcript.md"}


def test_scan_ignores_nested_occurrences_of_ignored_folders(tmp_path):
    _write(tmp_path, "03-Projects/Meridian/_Templates/nested.md")
    files = scan_vault(tmp_path)
    assert files == []


def test_content_hash_is_stable_for_identical_content():
    assert compute_content_hash("same text") == compute_content_hash("same text")


def test_content_hash_differs_for_different_content():
    assert compute_content_hash("a") != compute_content_hash("b")


def test_scanned_file_has_timezone_aware_modified_at(tmp_path):
    _write(tmp_path, "note.md")
    files = scan_vault(tmp_path)
    assert isinstance(files[0].modified_at, datetime)
    assert files[0].modified_at.tzinfo is not None


def test_scan_skips_files_with_invalid_utf8(tmp_path):
    # Write a valid file
    _write(tmp_path, "valid.md", "# Valid\n\nContent.")
    # Write a file with invalid UTF-8 bytes
    invalid_file = tmp_path / "invalid.md"
    invalid_file.parent.mkdir(parents=True, exist_ok=True)
    invalid_file.write_bytes(b"\xff\xfe\x00invalid")

    files = scan_vault(tmp_path)

    # Only the valid file should be returned
    paths = {f.vault_path for f in files}
    assert paths == {"valid.md"}
    assert len(files) == 1
