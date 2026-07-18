from __future__ import annotations

from app.core.config import settings
from app.db.base import SessionLocal
from app.ingestion.embeddings import OllamaEmbeddingProvider
from app.ingestion.indexer import run_index


def main() -> None:
    session = SessionLocal()
    try:
        provider = OllamaEmbeddingProvider(base_url=settings.ollama_workstation_url)
        result = run_index(
            session,
            settings.vault_path,
            provider,
            max_section_tokens=settings.chunk_max_section_tokens,
            embedding_model=settings.embedding_model,
        )
        print(
            f"status={result.status} scanned={result.files_scanned} "
            f"added={result.files_added} updated={result.files_updated} "
            f"deleted={result.files_deleted} errors={len(result.errors)}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
