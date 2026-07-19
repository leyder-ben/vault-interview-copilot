from __future__ import annotations

import argparse

from app.core.config import settings
from app.db.base import SessionLocal
from app.evaluation.runner import EvalGroupMetrics, load_fixtures, run_eval
from app.providers.embeddings import OllamaEmbeddingProvider

DATASET_PATHS = {
    "sample-vault": "../../evaluation/datasets/sample-vault/meridian-fixtures.yaml",
    "private": "../../evaluation/datasets/private/mock-interview-fixtures.yaml",
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.evaluation.cli",
        description="Score retrieval against a fixture dataset.",
    )
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASET_PATHS.keys()),
        required=True,
        help="Which fixture dataset to evaluate against.",
    )
    return parser.parse_args(argv if argv is not None else [])


def _print_group(label: str, group: EvalGroupMetrics) -> None:
    print(
        f"{label}: Recall@5: {group.recall_at_5:.0%}  Recall@10: {group.recall_at_10:.0%}  "
        f"MRR: {group.mrr:.2f}  Exact match: {group.exact_match_rate:.0%}"
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    fixtures = load_fixtures(DATASET_PATHS[args.dataset])

    session = SessionLocal()
    try:
        provider = OllamaEmbeddingProvider(
            base_url=settings.ollama_workstation_url, model=settings.embedding_model
        )
        report = run_eval(session, provider, fixtures)

        _print_group("Shorthand", report.shorthand)
        _print_group("Natural phrasing", report.natural)
        print(
            f"Shorthand latency: p50 {report.shorthand.latency_p50_ms:.0f}ms, "
            f"p95 {report.shorthand.latency_p95_ms:.0f}ms"
        )
        print(
            f"Natural phrasing latency: p50 {report.natural.latency_p50_ms:.0f}ms, "
            f"p95 {report.natural.latency_p95_ms:.0f}ms"
        )
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
