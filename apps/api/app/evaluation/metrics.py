from __future__ import annotations

import math

from app.retrieval.fusion import FusedResult


def hit_at_k(fused_results: list[FusedResult], expected_paths: list[str], k: int) -> bool:
    top_k_paths = {r.vault_path for r in fused_results if r.fused_rank <= k}
    return bool(top_k_paths & set(expected_paths))


def reciprocal_rank(fused_results: list[FusedResult], expected_paths: list[str]) -> float:
    for result in fused_results:
        if result.vault_path in expected_paths:
            return 1.0 / result.fused_rank
    return 0.0


def exact_match(fused_results: list[FusedResult], expected_paths: list[str]) -> bool:
    if not fused_results:
        return False
    return fused_results[0].vault_path in expected_paths


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (p / 100) * (len(sorted_values) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[int(index)]
    fraction = index - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction
