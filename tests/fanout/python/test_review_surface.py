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
from typing import TypedDict, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

from easy_cheese.shared.fanout import age_route, review_surface  # noqa: E402

FIXTURE_PATH = REPO_ROOT / "tests" / "fanout" / "python" / "fixtures" / "numstat_30_commits.json"


class _CommitFixture(TypedDict):
    sha: str
    rows: list[tuple[str, int, int]]


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
        weights = (("*.lock", 0.0), ("*", 1.0))
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
        assert result["score"] == pytest.approx(expected)  # pyright: ignore[reportUnknownMemberType]
        assert result["weighted_lines"] == pytest.approx(  # pyright: ignore[reportUnknownMemberType]
            weighted_lines
        )
        assert result["weighted_files"] == pytest.approx(  # pyright: ignore[reportUnknownMemberType]
            weighted_files
        )

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

    def test_score_includes_weights_source_and_rows(self) -> None:
        rows = [("src/main.py", 10, 5)]

        default_result = review_surface.score(rows)
        assert default_result["weights_source"] == "defaults"
        assert default_result["rows"] == 1

        override_result = review_surface.score(
            rows, weights=(("*", 1.0),), weights_source="config:.review-weights.toml"
        )
        assert override_result["weights_source"] == "config:.review-weights.toml"
        assert override_result["rows"] == 1

    def test_score_rows_counts_input_rows_not_zeroed_rows(self) -> None:
        rows = [("Cargo.lock", 10, 0), ("src/main.py", 1, 1), ("README.md", 2, 0)]
        result = review_surface.score(rows)
        assert result["rows"] == 3


class TestFrozenFixturePyramid:
    """SPEC ACCEPTANCE 1: the frozen 30-commit numstat fixture reproduces the
    measured 6 top / 4 mid / 8 low / 12 single pyramid at cut points
    60/250/900.
    """

    def test_pyramid_matches_measured_distribution(self) -> None:
        commits = cast(
            list[_CommitFixture], json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        )
        assert len(commits) == 30

        n2_floor = age_route._SCORE_N2_FLOOR  # pyright: ignore[reportPrivateUsage]
        n5_floor = age_route._SCORE_N5_FLOOR  # pyright: ignore[reportPrivateUsage]
        high_effort = age_route._HIGH_EFFORT_SCORE  # pyright: ignore[reportPrivateUsage]

        tiers = {"top": 0, "mid": 0, "low": 0, "single": 0}
        for commit in commits:
            result = review_surface.score(commit["rows"])
            s = result["score"]
            # age_route._tier_for_score routes `score < n2_floor` to n=1 and
            # everything else to n=2+, so the "single" bucket boundary must
            # be an exclusive `<` (equivalently the low-tier floor is `>=`)
            # to match the router exactly -- a plain `> n2_floor` literal
            # would misfile score == n2_floor into "single" while the real
            # router sends it to n=2.
            if s > high_effort:
                tiers["top"] += 1
            elif s > n5_floor:
                tiers["mid"] += 1
            elif s >= n2_floor:
                tiers["low"] += 1
            else:
                tiers["single"] += 1

        assert tiers == {"top": 6, "mid": 4, "low": 8, "single": 12}


class TestPurity:
    """Mirrors test_age_route.py::TestPurity -- review_surface.py inherits
    age_route.py's AST-derived I/O import ban.
    """

    def test_module_has_no_io_imports(self) -> None:
        src = (REPO_ROOT / "src/easy_cheese/shared/fanout/review_surface.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        banned = {
            "os",
            "sys",
            "socket",
            "subprocess",
            "requests",
            "urllib",
            "pathlib",
            "shutil",
            "io",
            "tempfile",
            "http",
            "importlib",
            "pickle",
        }
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & banned), f"unexpected I/O-shaped imports: {imported & banned}"

    def test_module_parses_as_valid_python(self) -> None:
        src = (REPO_ROOT / "src/easy_cheese/shared/fanout/review_surface.py").read_text(encoding="utf-8")
        _ = ast.parse(src)  # raises SyntaxError if invalid


class TestDualGlobFirstMatchWinsRealTable:
    """SPEC ACCEPTANCE: DEFAULT_WEIGHTS entries are ordered so a zero-
    weight glob always wins over a later quarter-weight glob for paths
    that match both -- fnmatch lets `*` cross `/`, so these paths match
    two entries of the SHIPPED table.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "docs/notes/deps.lock",  # matches *.lock (0.0) and docs/** (0.25)
            "README.lock",  # matches *.lock (0.0) and README* (0.25)
            ".hallouminate/scripts/age.pyz",  # matches *.pyz (0.0) and .hallouminate/** (0.25)
        ],
    )
    def test_zero_weight_glob_wins_over_later_quarter_weight_glob(self, path: str) -> None:
        assert review_surface.weigh(path) == 0.0

    def test_zero_weight_entries_precede_quarter_weight_entries(self) -> None:
        # Structural invariant that makes first-match-wins produce the
        # zero-weight result above: every 0.0 entry must sit at a lower
        # index than every 0.25 entry.
        zero_indices = [i for i, (_, w) in enumerate(review_surface.DEFAULT_WEIGHTS) if w == 0.0]
        quarter_indices = [i for i, (_, w) in enumerate(review_surface.DEFAULT_WEIGHTS) if w == 0.25]
        assert zero_indices
        assert quarter_indices
        assert max(zero_indices) < min(quarter_indices)


class TestAnchoredOrNestedMatch:
    """CURE FIX (deterministic-fanout-sizing press finding): fnmatch anchors
    at the string start, so a bare table entry like `fixtures/**` matched
    only at repo root while `**/snapshots/**` matched only when nested --
    one table can't mean both. weigh() now tries a pattern both anchored
    and nested (`"**/" + pattern`), and DEFAULT_WEIGHTS is normalized to
    bare form throughout, so every entry means "anywhere in the tree."
    """

    @pytest.mark.parametrize(
        "path",
        [
            # Real fixture the spec cites as its motivating example: a
            # nested fixtures/ dir that must not inflate the review score.
            "tools/skill-overlap/fixtures/hallouminate-fastembed.json",
            "tests/fanout/python/fixtures/numstat_30_commits.json",
        ],
    )
    def test_nested_fixtures_path_zeroed(self, path: str) -> None:
        assert review_surface.weigh(path) == 0.0

    def test_top_level_snapshots_path_zeroed(self) -> None:
        # Before the fix, snapshots/** only matched nested (**/snapshots/**),
        # so a top-level snapshots/ dir wrongly scored as full-weight code.
        assert review_surface.weigh("snapshots/a.snap") == 0.0

    def test_nested_vendor_path_zeroed(self) -> None:
        # vendor/** was anchored-only; nested vendored code must not count
        # toward the reviewer's attention budget either.
        assert review_surface.weigh("src/vendor/x.go") == 0.0

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("fixtures/x.json", 0.0),
            ("vendor/x.go", 0.0),
            ("docs/a.md", 0.25),
        ],
    )
    def test_anchored_forms_still_match(self, path: str, expected: float) -> None:
        # The dual-match fix must not regress the original repo-root cases.
        assert review_surface.weigh(path) == expected

    def test_nested_prose_path_scores_as_prose_not_code(self) -> None:
        # Deliberate behaviour change: docs/** now matches nested too, so
        # nested documentation scores as low-stakes prose (0.25) instead of
        # silently inflating to full-weight code (1.0).
        assert review_surface.weigh("skills/age/docs/a.md") == 0.25


class TestGlobFixRegression:
    """CURE FIX (deterministic-fanout-sizing): weigh() now splits by
    pattern shape -- a pattern with no "/" is basename-anchored, one with
    "/" matches anchored-or-nested -- and DEFAULT_WEIGHTS uses hyphenated
    "*-lock.json"/"*-lock.yaml" plus a "go.sum" entry. Each parametrized
    case pins one direction of that fix:

    - real source whose basename merely CONTAINS "lock" or a nested
      README/CHANGELOG directory must stay at full weight (1.0) -- a
      zeroed weight makes the file invisible to sizing *and* lists it in
      `zeroed` as non-review, which is exactly the under-review outcome
      the inverted weights table exists to prevent;
    - a genuine lockfile (hyphen-before-"lock", or go.sum) must still
      zero, so dependency-bot diffs don't inflate the reviewer's budget;
    - tools/skill-overlap/fixtures/x.json is the exact case commit
      9089710 fixed (nested fixtures/ must match via the anchored-or-
      nested check) and must not regress back to full weight.
    """

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("src/unlock.json", 1.0),
            ("src/config/deadlock.json", 1.0),
            ("src/mylock.yaml", 1.0),
            ("src/READMEs/code.py", 1.0),
            ("CHANGELOGS/entry.py", 1.0),
            ("package-lock.json", 0.0),
            ("pnpm-lock.yaml", 0.0),
            ("Cargo.lock", 0.0),
            ("yarn.lock", 0.0),
            ("go.sum", 0.0),
            ("tools/skill-overlap/fixtures/x.json", 0.0),
        ],
    )
    def test_glob_shape_split_direction(self, path: str, expected: float) -> None:
        assert review_surface.weigh(path) == expected
