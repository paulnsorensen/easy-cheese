"""Contract and unit checks for two-objective scoring and the graduation gate."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from agent_lab_scoring import (
    GUARD_TOKEN_PENALTY,
    ScoringError,
    dominates,
    graduate,
    pareto_front,
    paired_comparison,
    score_vector,
    side_info_scores,
    token_total,
)


def _row(task: str, correct: bool, *, input_tokens: int = 0, output_tokens: int = 0,
         cache_creation_tokens: int = 0, cache_read_tokens: int = 0, guard: str = "") -> dict[str, object]:
    row: dict[str, object] = {
        "task": task,
        "correct": correct,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
    }
    if guard:
        row["guard"] = guard
    return row


class TestTokenTotal:
    def test_sums_all_four_fields(self) -> None:
        row = _row("t1", True, input_tokens=10, output_tokens=20, cache_creation_tokens=3, cache_read_tokens=4)
        assert token_total(row) == 37


class TestScoreVector:
    def test_correct_and_negative_tokens(self) -> None:
        row = _row("t1", True, input_tokens=100, output_tokens=50)
        assert score_vector(row) == (1.0, -150.0)

    def test_incorrect_row(self) -> None:
        row = _row("t1", False, input_tokens=10, output_tokens=10)
        assert score_vector(row) == (0.0, -20.0)

    def test_guard_row_is_dominated(self) -> None:
        row = _row("t1", True, input_tokens=1, output_tokens=1, guard="token-budget")
        assert score_vector(row) == (0.0, -GUARD_TOKEN_PENALTY)

    def test_missing_correct_raises(self) -> None:
        with pytest.raises(ScoringError):
            _ = score_vector({"task": "t1"})


class TestSideInfoScores:
    def test_builds_scores_dict(self) -> None:
        row = _row("t1", True, input_tokens=10, output_tokens=5)
        assert side_info_scores(row) == {"correct": 1.0, "neg_tokens": -15.0}


class TestDominates:
    def test_strictly_better_on_both_axes(self) -> None:
        assert dominates((1.0, -100.0), (0.5, -200.0))

    def test_equal_is_not_dominating(self) -> None:
        assert not dominates((1.0, -100.0), (1.0, -100.0))

    def test_worse_on_one_axis_is_not_dominating(self) -> None:
        assert not dominates((1.0, -300.0), (0.5, -100.0))


class TestParetoFront:
    """AC-6 matrix agent-lab-score-1: A correct 1.0 tokens high, B correct 0.5
    tokens low, C correct 0.5 tokens high dominated (by B)."""

    def test_matrix_agent_lab_score_1(self) -> None:
        points = [
            ("A", (1.0, -900.0)),
            ("B", (0.5, -100.0)),
            ("C", (0.5, -900.0)),
        ]
        assert pareto_front(points) == ["A", "B"]

    def test_all_equal_all_survive(self) -> None:
        points = [("A", (1.0, -100.0)), ("B", (1.0, -100.0))]
        assert pareto_front(points) == ["A", "B"]


class TestPairedComparison:
    def test_means_over_shared_task_ids_only(self) -> None:
        seed_rows = [_row("t1", True, input_tokens=100), _row("t2", False, input_tokens=100), _row("t3", True, input_tokens=50)]
        candidate_rows = [_row("t1", True, input_tokens=50), _row("t2", True, input_tokens=50)]
        seed_vec, candidate_vec = paired_comparison(seed_rows, candidate_rows)
        # t3 is seed-only and must not affect the seed mean.
        assert seed_vec == (0.5, -100.0)
        assert candidate_vec == (1.0, -50.0)

    def test_no_shared_ids_raises(self) -> None:
        with pytest.raises(ScoringError):
            _ = paired_comparison([_row("t1", True)], [_row("t2", True)])


def _evaluate_from(rows_by_model_and_component: dict[tuple[str, str], list[dict[str, object]]]):
    def evaluate(components: Mapping[str, str], model: str) -> list[dict[str, object]]:
        key = ("seed" if any("seed-marker" in text for text in components.values()) else "candidate", model)
        return rows_by_model_and_component[key]

    return evaluate


SEED = {"skills/cook/SKILL.md": "seed-marker seed prompt"}
CANDIDATE = {"skills/cook/SKILL.md": "candidate prompt"}


class TestGraduate:
    """AC-7 matrix agent-lab-graduate-1."""

    def test_non_dominated_on_all_three_promotes(self, tmp_path: Path) -> None:
        rows = {
            ("seed", "sonnet"): [_row("t1", False, input_tokens=200), _row("t2", True, input_tokens=200)],
            ("candidate", "sonnet"): [_row("t1", True, input_tokens=100), _row("t2", True, input_tokens=100)],
            ("seed", "opus"): [_row("t1", True, input_tokens=200)],
            ("candidate", "opus"): [_row("t1", True, input_tokens=100)],
            ("seed", "fable"): [_row("t1", True, input_tokens=200)],
            ("candidate", "fable"): [_row("t1", True, input_tokens=100)],
        }
        result = graduate(
            SEED,
            CANDIDATE,
            evaluate=_evaluate_from(rows),
            models=("sonnet", "opus", "fable"),
            output_dir=tmp_path,
        )
        assert result["verdict"] == "promote"
        assert (tmp_path / "best_candidate" / "skills/cook/SKILL.md").read_text() == "candidate prompt"
        assert (tmp_path / "graduation.json").exists()

    def test_dominated_on_one_model_holds(self, tmp_path: Path) -> None:
        rows = {
            ("seed", "sonnet"): [_row("t1", True, input_tokens=100), _row("t2", True, input_tokens=100)],
            ("candidate", "sonnet"): [_row("t1", True, input_tokens=50), _row("t2", True, input_tokens=50)],
            ("seed", "opus"): [_row("t1", True, input_tokens=100)],
            ("candidate", "opus"): [_row("t1", True, input_tokens=100)],
            ("seed", "fable"): [_row("t1", True, input_tokens=100)],
            # Fable candidate is strictly worse on both axes: seed dominates it.
            ("candidate", "fable"): [_row("t1", False, input_tokens=500)],
        }
        result = graduate(
            SEED,
            CANDIDATE,
            evaluate=_evaluate_from(rows),
            models=("sonnet", "opus", "fable"),
            output_dir=tmp_path,
        )
        assert result["verdict"] == "hold"
        assert not (tmp_path / "best_candidate").exists()
        assert not (tmp_path / "graduation.json").exists()

    def test_equal_on_both_axes_everywhere_holds(self, tmp_path: Path) -> None:
        rows = {
            ("seed", "sonnet"): [_row("t1", True, input_tokens=100)],
            ("candidate", "sonnet"): [_row("t1", True, input_tokens=100)],
            ("seed", "opus"): [_row("t1", True, input_tokens=100)],
            ("candidate", "opus"): [_row("t1", True, input_tokens=100)],
            ("seed", "fable"): [_row("t1", True, input_tokens=100)],
            ("candidate", "fable"): [_row("t1", True, input_tokens=100)],
        }
        result = graduate(
            SEED,
            CANDIDATE,
            evaluate=_evaluate_from(rows),
            models=("sonnet", "opus", "fable"),
            output_dir=tmp_path,
        )
        assert result["verdict"] == "hold"
        assert not (tmp_path / "best_candidate").exists()

    def test_rejects_absolute_component_path(self, tmp_path: Path) -> None:
        with pytest.raises(ScoringError):
            _ = graduate(
                SEED,
                {"/etc/passwd": "x"},
                evaluate=_evaluate_from({}),
                models=("sonnet",),
                output_dir=tmp_path,
            )

    def test_rejects_dotdot_component_path(self, tmp_path: Path) -> None:
        with pytest.raises(ScoringError):
            _ = graduate(
                SEED,
                {"../outside": "x"},
                evaluate=_evaluate_from({}),
                models=("sonnet",),
                output_dir=tmp_path,
            )

    def test_promotion_writes_only_under_output_dir(self, tmp_path: Path) -> None:
        """AC-8: promotion writes only under output_dir.

        `graduate` is pure and never receives a checkout path -- it only
        ever sees `seed`/`candidate` component text and `output_dir`, so the
        one in-module invariant it can prove is that a promote never writes
        outside `output_dir`. (The CLI-level guarantee that a real
        checkout's `skills/cook/SKILL.md` is untouched belongs in
        `test_agent_lab_graduate.py`, where `graduate` actually receives
        checkout-derived components; see the cure-g3 handback for that
        follow-up.)
        """
        sibling = tmp_path / "unrelated"
        sibling.mkdir()
        marker = sibling / "marker.txt"
        _ = marker.write_text("untouched", encoding="utf-8")
        before_bytes = marker.read_bytes()
        before_mtime = marker.stat().st_mtime_ns

        output_dir = tmp_path / "out"
        output_dir.mkdir()
        rows = {
            ("seed", "sonnet"): [_row("t1", False, input_tokens=200)],
            ("candidate", "sonnet"): [_row("t1", True, input_tokens=100)],
        }
        result = graduate(
            SEED,
            CANDIDATE,
            evaluate=_evaluate_from(rows),
            models=("sonnet",),
            output_dir=output_dir,
        )
        assert result["verdict"] == "promote"
        assert marker.read_bytes() == before_bytes
        assert marker.stat().st_mtime_ns == before_mtime
        assert (output_dir / "best_candidate" / "skills/cook/SKILL.md").read_text() == "candidate prompt"
