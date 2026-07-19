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

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

BUNDLE = build_pyz.cached_bundle("ultracook")


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


class TestSingleSourceOfTruth:
    """Acceptance #3, grep-proof: the old five-curd gate is gone from both
    consumers, and each reads PARALLEL_THRESHOLD rather than a private number."""

    def test_validate_decomposition_reads_the_constant(self) -> None:
        src = (REPO_ROOT / "src" / "fanout" / "validate_decomposition.py").read_text(
            encoding="utf-8"
        )
        assert "from mode import PARALLEL_THRESHOLD" in src
        assert "PARALLEL_THRESHOLD" in src
        # Old five-curd hard gate and its message must be gone.
        assert "requires at least 5" not in src
        assert "< 5" not in src

    def test_curd_count_reads_the_constant(self) -> None:
        src = (REPO_ROOT / "src" / "mold" / "curd-count.py").read_text(encoding="utf-8")
        assert "PARALLEL_THRESHOLD" in src
        # No private threshold constant, no dead /cheese-factory target.
        assert "CURD_THRESHOLD = 5" not in src
        assert "/cheese-factory" not in src
