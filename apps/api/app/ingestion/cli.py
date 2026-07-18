from __future__ import annotations

import argparse
import sys

from app.core.config import settings
from app.db.base import SessionLocal
from app.ingestion.embeddings import OllamaEmbeddingProvider
from app.ingestion.indexer import run_index


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.ingestion.cli",
        description="Index the vault into Postgres (notes, chunks, embeddings).",
    )
    parser.add_argument(
        "--vault-path",
        default=None,
        help="Path to the vault to index. Overrides settings.vault_path when given.",
    )
    return parser.parse_args(argv if argv is not None else [])


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    vault_path = args.vault_path if args.vault_path is not None else settings.vault_path

    session = SessionLocal()
    try:
        provider = OllamaEmbeddingProvider(base_url=settings.ollama_workstation_url)
        result = run_index(
            session,
            vault_path,
            provider,
            max_section_tokens=settings.chunk_max_section_tokens,
            embedding_model=settings.embedding_model,
        )
        print(
            f"status={result.status} scanned={result.files_scanned} "
            f"added={result.files_added} updated={result.files_updated} "
            f"deleted={result.files_deleted} errors={len(result.errors)}"
        )
        for error in result.errors:
            print(f"  error: {error.get('vault_path')}: {error.get('error')}")
    finally:
        session.close()


if __name__ == "__main__":
    main(sys.argv[1:])
