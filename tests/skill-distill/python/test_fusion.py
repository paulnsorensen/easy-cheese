from __future__ import annotations

import pytest

from skill_distill.fusion import (
    FusionExample,
    RetrievalCandidate,
    select_fusion,
    split_and_fold,
    validate_weights,
    weight_grid,
)
from skill_distill.retrieval import BgeM3Evidence


def _example(index: int, relation: str = "equivalent", graph: str = "connected") -> FusionExample:
    return FusionExample(
        pair_id=f"pair-{index:02}",
        relation=relation,
        graph_class=graph,
        candidates=(
            RetrievalCandidate("a", BgeM3Evidence(0.5, 0.5, 0.5), False),
            RetrievalCandidate("z", BgeM3Evidence(0.5, 0.5, 0.5), True),
        ),
    )


def test_split_is_stable_80_20_with_five_development_folds() -> None:
    examples = tuple(_example(index) for index in range(25))
    first = split_and_fold(examples, "split-seed", "fold-seed")
    second = split_and_fold(reversed(examples), "split-seed", "fold-seed")

    assert first == second
    assert sum(item.held_out for item in first) == 5
    assert {item.fold for item in first if not item.held_out} == {0, 1, 2, 3, 4}


def test_small_strata_merge_by_relation_before_sparse_fallback() -> None:
    examples = (
        tuple(_example(index, "equivalent", "connected") for index in range(10))
        + tuple(_example(index, "shared-shell", "connected") for index in range(10, 16))
        + tuple(_example(index, "shared-shell", "disconnected") for index in range(16, 22))
    )

    assignments = split_and_fold(examples, "split-seed", "fold-seed")

    assert {item.stratum for item in assignments} == {"equivalent|connected", "shared-shell|*"}


def test_fusion_uses_smallest_qualifying_k_then_lexicographic_weights() -> None:
    profile, assignments = select_fusion(
        tuple(_example(index) for index in range(25)), "split-seed", "fold-seed"
    )

    assert profile.candidate_cutoff == 2
    assert profile.weights == (0.0, 0.0, 1.0)
    assert profile.training_digest
    assert profile.held_out_identity
    assert sum(item.held_out for item in assignments) == 5


def test_weight_grid_is_nonnegative_and_fixed_at_five_percent() -> None:
    assert len(weight_grid()) == 231
    assert all(sum(weights) == pytest.approx(1) for weights in weight_grid())
    validate_weights((0.0, 0.5, 0.5))
    with pytest.raises(ValueError, match="0.05"):
        validate_weights((0.1, 0.1, 0.81))
