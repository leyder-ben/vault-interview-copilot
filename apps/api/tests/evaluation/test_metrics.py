from app.evaluation.metrics import exact_match, hit_at_k, percentile, reciprocal_rank
from app.retrieval.fusion import FusedResult


def _fused(vault_path: str, fused_rank: int) -> FusedResult:
    return FusedResult(
        chunk_id=fused_rank,
        vault_path=vault_path,
        heading_path=None,
        fused_rank=fused_rank,
        rrf_score=1.0 / fused_rank,
        fulltext_rank=fused_rank,
        vector_rank=fused_rank,
    )


def test_hit_at_k_true_when_expected_path_within_k():
    results = [_fused("A.md", 1), _fused("B.md", 2), _fused("Expected.md", 3)]
    assert hit_at_k(results, ["Expected.md"], k=5) is True


def test_hit_at_k_false_when_expected_path_beyond_k():
    results = [_fused("A.md", 1), _fused("Expected.md", 6)]
    assert hit_at_k(results, ["Expected.md"], k=5) is False


def test_hit_at_k_true_if_any_expected_path_matches():
    results = [_fused("A.md", 1), _fused("Expected-2.md", 2)]
    assert hit_at_k(results, ["Expected-1.md", "Expected-2.md"], k=5) is True


def test_reciprocal_rank_of_first_match():
    results = [_fused("A.md", 1), _fused("Expected.md", 3)]
    assert reciprocal_rank(results, ["Expected.md"]) == 1 / 3


def test_reciprocal_rank_zero_when_no_match():
    results = [_fused("A.md", 1)]
    assert reciprocal_rank(results, ["Expected.md"]) == 0.0


def test_exact_match_true_when_top_result_is_expected():
    results = [_fused("Expected.md", 1), _fused("A.md", 2)]
    assert exact_match(results, ["Expected.md"]) is True


def test_exact_match_false_when_top_result_is_not_expected():
    results = [_fused("A.md", 1), _fused("Expected.md", 2)]
    assert exact_match(results, ["Expected.md"]) is False


def test_exact_match_false_on_empty_results():
    assert exact_match([], ["Expected.md"]) is False


def test_percentile_p50_of_sorted_values():
    assert percentile([10.0, 20.0, 30.0, 40.0], 50) == 25.0


def test_percentile_p95_of_sorted_values():
    # Linear interpolation (matches numpy.percentile's default method):
    # index = 0.95 * 99 = 94.05, interpolates between sorted_values[94]=95
    # and sorted_values[95]=96 -> 95 + (96-95)*0.05 = 95.05, not a round 95.0.
    assert percentile(list(range(1, 101)), 95) == 95.05
