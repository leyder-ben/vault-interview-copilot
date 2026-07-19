from __future__ import annotations

from dataclasses import dataclass

import yaml
from sqlalchemy.orm import Session

from app.evaluation.metrics import exact_match, hit_at_k, percentile, reciprocal_rank
from app.ingestion.embeddings import EmbeddingProvider
from app.retrieval.search import search


@dataclass
class Fixture:
    id: str
    query: str
    interviewer_phrasing: str | None
    expected_notes: list[str]


@dataclass
class FixtureResult:
    fixture_id: str
    query_form: str
    query_text: str
    hit_at_5: bool
    hit_at_10: bool
    reciprocal_rank: float
    exact_match: bool
    latency_ms: float


@dataclass
class EvalGroupMetrics:
    recall_at_5: float
    recall_at_10: float
    mrr: float
    exact_match_rate: float
    latency_p50_ms: float
    latency_p95_ms: float


@dataclass
class EvalReport:
    shorthand: EvalGroupMetrics
    natural: EvalGroupMetrics
    results: list[FixtureResult]


def load_fixtures(path: str) -> list[Fixture]:
    with open(path, encoding="utf-8") as f:
        raw_fixtures = yaml.safe_load(f)

    return [
        Fixture(
            id=item["id"],
            query=item["query"],
            interviewer_phrasing=item.get("interviewer_phrasing"),
            expected_notes=item["expected_notes"],
        )
        for item in raw_fixtures
    ]


def _score_one(
    session: Session,
    embedding_provider: EmbeddingProvider,
    fixture: Fixture,
    query_form: str,
    query_text: str,
) -> FixtureResult:
    result = search(session, embedding_provider, query_text)
    return FixtureResult(
        fixture_id=fixture.id,
        query_form=query_form,
        query_text=query_text,
        hit_at_5=hit_at_k(result.fused_results, fixture.expected_notes, k=5),
        hit_at_10=hit_at_k(result.fused_results, fixture.expected_notes, k=10),
        reciprocal_rank=reciprocal_rank(result.fused_results, fixture.expected_notes),
        exact_match=exact_match(result.fused_results, fixture.expected_notes),
        latency_ms=result.timing_ms["total"],
    )


def _aggregate(results: list[FixtureResult]) -> EvalGroupMetrics:
    if not results:
        return EvalGroupMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    latencies = [r.latency_ms for r in results]
    return EvalGroupMetrics(
        recall_at_5=sum(r.hit_at_5 for r in results) / len(results),
        recall_at_10=sum(r.hit_at_10 for r in results) / len(results),
        mrr=sum(r.reciprocal_rank for r in results) / len(results),
        exact_match_rate=sum(r.exact_match for r in results) / len(results),
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
    )


def run_eval(
    session: Session, embedding_provider: EmbeddingProvider, fixtures: list[Fixture]
) -> EvalReport:
    results: list[FixtureResult] = []

    for fixture in fixtures:
        results.append(_score_one(session, embedding_provider, fixture, "shorthand", fixture.query))
        if fixture.interviewer_phrasing is not None:
            results.append(
                _score_one(
                    session, embedding_provider, fixture, "natural", fixture.interviewer_phrasing
                )
            )

    shorthand_results = [r for r in results if r.query_form == "shorthand"]
    natural_results = [r for r in results if r.query_form == "natural"]

    return EvalReport(
        shorthand=_aggregate(shorthand_results),
        natural=_aggregate(natural_results),
        results=results,
    )
