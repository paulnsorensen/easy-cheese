"""Tests for src/fanout/review_surface.py -- the pure git-derived, code-
weighted review-surface scorer.

Spec: deterministic-fanout-sizing.md ` ### 1. review_surface` and
`## Validation evidence`. score = sum(weight * lines) + FILE_COST * sum(weight),
first-match-wins glob weighting, default weight 1.0 for anything unmatched.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

import review_surface  # noqa: E402

FIXTURE_PATH = REPO_ROOT / "tests" / "fanout" / "python" / "fixtures" / "numstat_30_commits.json"


class TestWeigh:
    def test_lockfile_zeroed(self) -> None:
        assert review_surface.weigh("Cargo.lock") == 0.0

        assert review_surface.weigh("pnpm-lock.yaml") == 0.0

    def test_readme_quarter_weight(self) -> None:
        assert review_surface.weigh("README.md") == 0.25

    def test_unmatched_extension_defaults_full_weight(self) -> None:
        assert review_surface.weigh("src/fanout/review_surface.py") == 1.0

    def test_first_match_wins_lock_before_default(self) -> None:
        # A path matching an earlier (zero-weight) pattern must not fall
        # through to the 1.0 default even though it also looks like normal
        # source -- first match in DEFAULT_WEIGHTS wins.
        weights = [("*.lock", 0.0), ("*", 1.0)]
        assert review_surface.weigh("foo.lock", weights=weights) == 0.0

    def test_fixtures_dir_zeroed(self) -> None:
        assert review_surface.weigh("fixtures/numstat_30_commits.json") == 0.0


class TestScore:
    def test_mixed_weights_matches_formula(self) -> None:
        rows = [
            ("Cargo.lock", 100, 50),  # weight 0.0
            ("README.md", 20, 10),  # weight 0.25
            ("src/main.py", 30, 5),  # weight 1.0
        ]
        result = review_surface.score(rows)
        weighted_lines = 0.0 * 150 + 0.25 * 30 + 1.0 * 35
        weighted_files = 0.0 + 0.25 + 1.0
        expected = weighted_lines + review_surface.FILE_COST * weighted_files
        assert result["score"] == pytest.approx(expected)
        assert result["weighted_lines"] == pytest.approx(weighted_lines)
        assert result["weighted_files"] == pytest.approx(weighted_files)

    def test_zeroed_contains_exactly_zero_weight_paths(self) -> None:
        rows = [
            ("Cargo.lock", 10, 0),
            ("pnpm-lock.yaml", 5, 5),
            ("README.md", 3, 0),
            ("src/main.py", 1, 1),
        ]
        result = review_surface.score(rows)
        assert result["zeroed"] == ["Cargo.lock", "pnpm-lock.yaml"]

    def test_empty_rows_scores_zero(self) -> None:
        result = review_surface.score([])
        assert result["score"] == 0.0
        assert result["weighted_files"] == 0.0
        assert result["weighted_lines"] == 0.0
        assert result["zeroed"] == []

    def test_all_lockfile_dependabot_commit_scores_low(self) -> None:
        # SPEC ACCEPTANCE 3: 676 raw lines, all lockfile -> score <= 20.
        rows = [("pnpm-lock.yaml", 400, 276)]
        result = review_surface.score(rows)
        assert result["score"] <= 20


class TestFrozenFixturePyramid:
    """SPEC ACCEPTANCE 1: the frozen 30-commit numstat fixture reproduces the
    measured 6 top / 4 mid / 8 low / 12 single pyramid at cut points
    60/250/900.
    """

    def test_pyramid_matches_measured_distribution(self) -> None:
        commits = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        assert len(commits) == 30

        tiers = {"top": 0, "mid": 0, "low": 0, "single": 0}
        for commit in commits:
            rows = [tuple(row) for row in commit["rows"]]
            result = review_surface.score(rows)
            s = result["score"]
            if s > 900:
                tiers["top"] += 1
            elif s > 250:
                tiers["mid"] += 1
            elif s > 60:
                tiers["low"] += 1
            else:
                tiers["single"] += 1

        assert tiers == {"top": 6, "mid": 4, "low": 8, "single": 12}


class TestPurity:
    """Mirrors test_age_route.py::TestPurity -- review_surface.py inherits
    age_route.py's AST-derived I/O import ban.
    """

    def test_module_has_no_io_imports(self) -> None:
        src = (REPO_ROOT / "src" / "fanout" / "review_surface.py").read_text(encoding="utf-8")
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
        src = (REPO_ROOT / "src" / "fanout" / "review_surface.py").read_text(encoding="utf-8")
        ast.parse(src)  # raises SyntaxError if invalid
