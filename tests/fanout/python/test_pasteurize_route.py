"""Tests for src/fanout/pasteurize_route.py -- the pure /pasteurize fan-out
sizing policy.

Spec: deterministic-fanout-sizing.md `### 5. /pasteurize -- the signal is
inverted`. Unlike age_route.route, /pasteurize reads review_surface
descending over the suspect range: less evidence -> more agents.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

import pasteurize_route  # noqa: E402


class TestRegression:
    def test_tight_range_deterministic_repro_routes_1(self) -> None:
        # Acceptance: regression, score=100, deterministic repro -> 1
        assert pasteurize_route.size_pasteurize_fanout("regression", 100, True) == 1

    def test_wide_range_deterministic_repro_routes_2(self) -> None:
        # Acceptance: regression, score=300, deterministic repro -> 2
        assert pasteurize_route.size_pasteurize_fanout("regression", 300, True) == 2


class TestHeisenbug:
    def test_low_score_routes_3(self) -> None:
        assert pasteurize_route.size_pasteurize_fanout("heisenbug", 50, True) == 3

    def test_high_score_routes_3(self) -> None:
        assert pasteurize_route.size_pasteurize_fanout("heisenbug", 500, True) == 3


class TestColdBug:
    def test_no_diff_to_anchor_to_routes_within_range(self) -> None:
        result = pasteurize_route.size_pasteurize_fanout("cold", None, False)
        assert result in {3, 4, 5}


class TestColdBugPinnedValues:
    """The existing TestColdBug test only asserts a range membership --
    tautological once the branch always returns 3, 4, or 5. Pin the exact
    values to the named constants (src/fanout/pasteurize_route.py:53-54), the
    same pattern TestBoundaryIsNamedConstant uses for WIDE_RANGE_THRESHOLD."""

    def test_cold_shape_non_deterministic_routes_max(self) -> None:
        result = pasteurize_route.size_pasteurize_fanout("cold", None, False)
        assert result == pasteurize_route._COLD_BUG_MAX_N

    def test_cold_shape_deterministic_repro_routes_min(self) -> None:
        result = pasteurize_route.size_pasteurize_fanout("cold", None, True)
        assert result == pasteurize_route._COLD_BUG_MIN_N

    def test_cold_shape_ignores_score(self) -> None:
        # A cold shape routes on bug_shape alone -- the score is irrelevant.
        result = pasteurize_route.size_pasteurize_fanout("cold", 1000.0, False)
        assert result == pasteurize_route._COLD_BUG_MAX_N

    def test_score_is_none_routes_cold_branch_even_for_regression_shape(self) -> None:
        # The `score is None` half of the `or` on line 53 also routes here,
        # even for a non-cold bug shape.
        result = pasteurize_route.size_pasteurize_fanout("regression", None, True)
        assert result == pasteurize_route._COLD_BUG_MIN_N

    def test_min_below_max_and_both_ints(self) -> None:
        assert pasteurize_route._COLD_BUG_MIN_N < pasteurize_route._COLD_BUG_MAX_N
        assert isinstance(pasteurize_route._COLD_BUG_MIN_N, int)
        assert isinstance(pasteurize_route._COLD_BUG_MAX_N, int)


class TestBoundaryIsNamedConstant:
    """Acceptance: the tight/wide boundary is the named constant, not a
    coincidental 250 -- parameterize off the constant so changing it moves
    the boundary."""

    def test_at_boundary_routes_wide(self) -> None:
        threshold = pasteurize_route.WIDE_RANGE_THRESHOLD
        assert pasteurize_route.size_pasteurize_fanout("regression", threshold + 1, True) == 2

    def test_just_below_boundary_routes_tight(self) -> None:
        threshold = pasteurize_route.WIDE_RANGE_THRESHOLD
        assert pasteurize_route.size_pasteurize_fanout("regression", threshold - 1, True) == 1


class TestInvalidBugShape:
    def test_invalid_bug_shape_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            pasteurize_route.size_pasteurize_fanout("not-a-shape", 100, True)


class TestPurity:
    """Mirrors test_age_route.py::TestPurity -- no os/network/file I/O."""

    def test_module_has_no_io_imports(self) -> None:
        src = (REPO_ROOT / "src" / "fanout" / "pasteurize_route.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        banned = {"os", "sys", "socket", "subprocess", "requests", "urllib", "pathlib", "shutil"}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & banned), f"unexpected I/O-shaped imports: {imported & banned}"

    def test_module_parses_as_valid_python(self) -> None:
        src = (REPO_ROOT / "src" / "fanout" / "pasteurize_route.py").read_text(encoding="utf-8")
        ast.parse(src)  # raises SyntaxError if invalid
