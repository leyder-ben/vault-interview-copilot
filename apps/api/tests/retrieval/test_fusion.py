from app.retrieval.fulltext import ScoredChunk
from app.retrieval.fusion import reciprocal_rank_fusion


def test_chunk_in_both_lists_ranks_above_chunk_in_one_list():
    fulltext = [
        ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=1, score=0.9),
        ScoredChunk(chunk_id=2, vault_path="B.md", heading_path=None, rank=2, score=0.5),
    ]
    vector = [
        ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=1, score=0.95),
    ]

    fused = reciprocal_rank_fusion(fulltext, vector, k=60)

    assert fused[0].chunk_id == 1
    assert fused[0].fulltext_rank == 1
    assert fused[0].vector_rank == 1
    assert fused[1].chunk_id == 2
    assert fused[1].fulltext_rank == 2
    assert fused[1].vector_rank is None


def test_rrf_score_matches_formula():
    fulltext = [ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=1, score=0.9)]
    vector = [ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=3, score=0.7)]

    fused = reciprocal_rank_fusion(fulltext, vector, k=60)

    expected_score = 1 / (60 + 1) + 1 / (60 + 3)
    assert fused[0].rrf_score == expected_score


def test_fused_rank_is_sequential_starting_at_one():
    fulltext = [
        ScoredChunk(chunk_id=1, vault_path="A.md", heading_path=None, rank=1, score=0.9),
        ScoredChunk(chunk_id=2, vault_path="B.md", heading_path=None, rank=2, score=0.5),
    ]
    fused = reciprocal_rank_fusion(fulltext, [], k=60)

    assert [r.fused_rank for r in fused] == [1, 2]


def test_empty_inputs_produce_empty_output():
    assert reciprocal_rank_fusion([], [], k=60) == []
