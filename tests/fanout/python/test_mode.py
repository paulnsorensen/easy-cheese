"""Tests for src/fanout/mode.py — canonical threshold + mode selector.

Locks acceptance #3: select_mode and every threshold consumer read a single
PARALLEL_THRESHOLD constant; no second hardcoded curd-count threshold remains.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BUNDLE = REPO_ROOT / "skills/cook/scripts/cook.pyz"

# Imported directly (not via the `mode` fixture) so DECOMPOSE_FIRST_THRESHOLD
# is available at collection time for parametrize -- fixtures only resolve
# during test execution.
from easy_cheese.shared.fanout import mode as _mode_module  # noqa: E402


class TestSelectMode:
    def test_zero_curds_linear(self, mode: ModuleType) -> None:
        assert mode.select_mode([]) == "linear"

    def test_one_curd_linear(self, mode: ModuleType) -> None:
        assert mode.select_mode([1]) == "linear"

    def test_two_curds_parallel(self, mode: ModuleType) -> None:
        assert mode.select_mode([1, 2]) == "parallel"

    def test_many_curds_parallel(self, mode: ModuleType) -> None:
        assert mode.select_mode(list(range(7))) == "parallel"

    def test_threshold_is_two(self, mode: ModuleType) -> None:
        assert mode.PARALLEL_THRESHOLD == 2

    def test_boundary_tracks_the_constant(self, mode: ModuleType) -> None:
        # The boundary must be PARALLEL_THRESHOLD itself, not a coincidental 2:
        # below it is linear, at it is parallel. Locks the selector to the
        # single constant so bumping the constant moves the boundary.
        below = mode.select_mode(range(mode.PARALLEL_THRESHOLD - 1))
        at = mode.select_mode(range(mode.PARALLEL_THRESHOLD))
        assert below == "linear"
        assert at == "parallel"


class TestCli:
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUNDLE), "mode", *args],
            capture_output=True,
            text=True,
        )

    def test_count_1_prints_linear(self) -> None:
        result = self._run("--count", "1")
        assert result.returncode == 0
        assert result.stdout.strip() == "linear"

    def test_count_2_prints_parallel(self) -> None:
        result = self._run("--count", "2")
        assert result.returncode == 0
        assert result.stdout.strip() == "parallel"

    def test_missing_count_exits_2(self) -> None:
        result = self._run()
        assert result.returncode == 2

    def test_json_mode(self) -> None:
        result = self._run("--count", "3", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout) == "parallel"

    def test_negative_count_fails_loud(self) -> None:
        # range(-1) is empty and would silently classify as "linear"; the guard
        # must reject a negative count with a loud non-zero error instead.
        result = self._run("--count", "-1")
        assert result.returncode != 0
        assert "linear" not in result.stdout
        assert "invalid --count" in result.stderr

    def test_score_below_threshold_prints_linear(self) -> None:
        result = self._run("--score", str(_mode_module.DECOMPOSE_FIRST_THRESHOLD - 1))
        assert result.returncode == 0
        assert result.stdout.strip() == "linear"

    def test_score_above_threshold_prints_decompose_first(self) -> None:
        result = self._run("--score", str(_mode_module.DECOMPOSE_FIRST_THRESHOLD + 1))
        assert result.returncode == 0
        assert result.stdout.strip() == "decompose-first"

    def test_score_at_threshold_prints_linear(self) -> None:
        # select_mode_from_score uses strict >, so the threshold itself is
        # still "linear" -- pin the boundary against the named constant.
        result = self._run("--score", str(_mode_module.DECOMPOSE_FIRST_THRESHOLD))
        assert result.returncode == 0
        assert result.stdout.strip() == "linear"

    def test_negative_score_fails_loud(self) -> None:
        result = self._run("--score", "-1")
        assert result.returncode != 0
        assert "invalid --score" in result.stderr

    def test_both_count_and_score_rejected(self) -> None:
        result = self._run("--count", "1", "--score", "1")
        assert result.returncode != 0

    def test_neither_count_nor_score_rejected(self) -> None:
        result = self._run()
        assert result.returncode != 0


class TestSingleSourceOfTruth:
    """Acceptance #3, grep-proof: the old five-curd gate is gone from both
    consumers, and neither carries a private threshold number."""

    def test_validate_decomposition_gates_on_no_curd_count(self) -> None:
        """The only count it rules on is "at least one" — file-shape checks now
        run at every count — so it reads no threshold, imported or private."""
        src = (REPO_ROOT / "src/easy_cheese/shared/fanout/validate_decomposition.py").read_text(
            encoding="utf-8"
        )
        assert "from mode import PARALLEL_THRESHOLD" not in src
        assert "CURD_THRESHOLD" not in src
        # Old five-curd hard gate and its message must be gone.
        assert "requires at least 5" not in src
        assert "< 5" not in src

    def test_curd_count_reads_the_constant(self) -> None:
        src = (REPO_ROOT / "src/easy_cheese/skills/mold/curd_count.py").read_text(encoding="utf-8")
        assert "PARALLEL_THRESHOLD" in src
        # No private threshold constant, no dead /cheese-factory target.
        assert "CURD_THRESHOLD = 5" not in src
        assert "/cheese-factory" not in src


class TestSelectModeFromScore:
    @pytest.mark.parametrize(
        "score, expected",
        [
            (0, "linear"),
            (_mode_module.DECOMPOSE_FIRST_THRESHOLD - 1, "linear"),
            (_mode_module.DECOMPOSE_FIRST_THRESHOLD, "linear"),
            (_mode_module.DECOMPOSE_FIRST_THRESHOLD + 1, "decompose-first"),
        ],
    )
    def test_boundary_tracks_the_constant(
        self, mode: ModuleType, score: float, expected: str
    ) -> None:
        assert mode.select_mode_from_score(score) == expected

    def test_never_returns_parallel(self, mode: ModuleType) -> None:
        scores = list(range(0, 2000, 10)) + [0, 10_000_000]
        for score in scores:
            assert mode.select_mode_from_score(score) != "parallel"

    def test_below_threshold_is_linear(self, mode: ModuleType) -> None:
        assert mode.select_mode_from_score(100) == "linear"

    def test_above_threshold_is_decompose_first(self, mode: ModuleType) -> None:
        assert mode.select_mode_from_score(251) == "decompose-first"
