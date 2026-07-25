"""Tests for src/fanout/age_route.py -- the pure age/affinage sizing router.

Locks the spec's age-router seam (subagent-routing-overhaul.md `## Seam
schemas (locked)` + `## The four sizing functions` age-router row): N in
{1, 4, 10} from diff-stat size, hard risk-overrides forcing N=10/effort=high
regardless of size, and the verbatim N=4 lens grouping.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "fanout"))

import age_route  # noqa: E402


class TestSizeTiers:
    """No risk flags: N is decided purely by diff-stat magnitude."""

    def test_tiny_diff_routes_n1_medium(self) -> None:
        # Acceptance #3: the 3-line-diff fixture must land at n=1/effort=medium.
        result = age_route.route(files_changed=1, insertions=2, deletions=1, risk_flags=[])
        assert result["n"] == 1
        assert result["effort"] == "medium"
        assert result["overrides_hit"] == []
        assert result["lenses"] == [list(age_route.DIMENSIONS)]

    def test_medium_diff_routes_n4(self) -> None:
        result = age_route.route(files_changed=5, insertions=25, deletions=10, risk_flags=[])
        assert result["n"] == 4
        assert result["effort"] == "medium"
        assert result["overrides_hit"] == []
        assert result["lenses"] == [
            ["correctness", "spec", "assertions"],
            ["security"],
            ["complexity", "deslop", "nih"],
            ["efficiency", "telemetry", "encapsulation"],
        ]

    def test_large_diff_routes_n10_high(self) -> None:
        result = age_route.route(files_changed=20, insertions=500, deletions=400, risk_flags=[])
        assert result["n"] == 10
        assert result["effort"] == "high"
        assert result["overrides_hit"] == []
        assert result["lenses"] == [[dim] for dim in age_route.DIMENSIONS]
        assert len(result["lenses"]) == 10

    def test_large_line_count_alone_routes_n10(self) -> None:
        # A single-file diff can still be huge; lines alone must trigger N=10.
        result = age_route.route(files_changed=1, insertions=900, deletions=0, risk_flags=[])
        assert result["n"] == 10
        assert result["effort"] == "high"

    def test_boundary_just_under_n4_stays_n1(self) -> None:
        result = age_route.route(files_changed=3, insertions=40, deletions=40, risk_flags=[])
        assert result["n"] == 1

    def test_boundary_just_over_n4_files_moves_to_n4(self) -> None:
        result = age_route.route(files_changed=4, insertions=1, deletions=1, risk_flags=[])
        assert result["n"] == 4

    def test_boundary_just_under_n10_stays_n4(self) -> None:
        result = age_route.route(files_changed=15, insertions=400, deletions=400, risk_flags=[])
        assert result["n"] == 4

    def test_boundary_just_over_n10_files_moves_to_n10(self) -> None:
        result = age_route.route(files_changed=16, insertions=1, deletions=1, risk_flags=[])
        assert result["n"] == 10


class TestHardOverrides:
    """A hard risk-override forces N=10/effort=high even on a trivial diff."""

    def test_trivial_diff_with_auth_flag_forces_n10(self) -> None:
        result = age_route.route(
            files_changed=1, insertions=2, deletions=1, risk_flags=["auth"]
        )
        assert result["n"] == 10
        assert result["effort"] == "high"
        assert result["overrides_hit"] == ["auth"]
        assert len(result["lenses"]) == 10

    def test_multiple_overrides_all_recorded(self) -> None:
        result = age_route.route(
            files_changed=1,
            insertions=1,
            deletions=0,
            risk_flags=["schema-migration", "production-destructive", "not-an-override"],
        )
        assert result["n"] == 10
        assert result["effort"] == "high"
        assert result["overrides_hit"] == ["production-destructive", "schema-migration"]

    def test_unrecognized_flag_does_not_force_override(self) -> None:
        result = age_route.route(
            files_changed=1, insertions=2, deletions=1, risk_flags=["typo-fix"]
        )
        assert result["n"] == 1
        assert result["overrides_hit"] == []

    def test_every_documented_override_category_is_recognized(self) -> None:
        # Spec's hard-override paragraph names six categories; every flag we
        # advertise as canonical must independently force n=10.
        for flag in age_route.OVERRIDE_FLAGS:
            result = age_route.route(
                files_changed=1, insertions=1, deletions=0, risk_flags=[flag]
            )
            assert result["n"] == 10, f"{flag} did not force n=10"
            assert result["overrides_hit"] == [flag]


class TestAffinageEscalation:
    """affinage entries weight high comment count / risky ci_class upward."""

    def test_age_entry_ignores_comments_and_ci_class(self) -> None:
        result = age_route.route(
            files_changed=1,
            insertions=2,
            deletions=1,
            risk_flags=[],
            entry="age",
            comments=999,
            ci_class="failing",
        )
        assert result["n"] == 1

    def test_affinage_high_comment_count_bumps_tier(self) -> None:
        result = age_route.route(
            files_changed=1,
            insertions=2,
            deletions=1,
            risk_flags=[],
            entry="affinage",
            comments=15,
        )
        assert result["n"] == 4

    def test_affinage_low_comment_count_does_not_bump(self) -> None:
        result = age_route.route(
            files_changed=1,
            insertions=2,
            deletions=1,
            risk_flags=[],
            entry="affinage",
            comments=2,
        )
        assert result["n"] == 1

    def test_affinage_failing_ci_class_bumps_tier(self) -> None:
        result = age_route.route(
            files_changed=1,
            insertions=2,
            deletions=1,
            risk_flags=[],
            entry="affinage",
            ci_class="failing",
        )
        assert result["n"] == 4

    def test_affinage_bump_never_exceeds_n10(self) -> None:
        result = age_route.route(
            files_changed=20,
            insertions=500,
            deletions=400,
            risk_flags=[],
            entry="affinage",
            comments=50,
            ci_class="failing",
        )
        assert result["n"] == 10
        assert result["effort"] == "high"

    def test_affinage_comment_count_at_exact_threshold_bumps(self) -> None:
        # >= _AFFINAGE_COMMENT_BUMP (10) bumps; boundary itself must bump.
        result = age_route.route(
            files_changed=1, insertions=2, deletions=1, risk_flags=[],
            entry="affinage", comments=10,
        )
        assert result["n"] == 4

    def test_affinage_comment_count_just_under_threshold_does_not_bump(self) -> None:
        result = age_route.route(
            files_changed=1, insertions=2, deletions=1, risk_flags=[],
            entry="affinage", comments=9,
        )
        assert result["n"] == 1

    def test_affinage_red_ci_class_bumps_tier(self) -> None:
        result = age_route.route(
            files_changed=1, insertions=2, deletions=1, risk_flags=[],
            entry="affinage", ci_class="red",
        )
        assert result["n"] == 4

    def test_affinage_flaky_ci_class_bumps_tier(self) -> None:
        result = age_route.route(
            files_changed=1, insertions=2, deletions=1, risk_flags=[],
            entry="affinage", ci_class="flaky",
        )
        assert result["n"] == 4

    def test_affinage_healthy_ci_class_does_not_bump(self) -> None:
        result = age_route.route(
            files_changed=1, insertions=2, deletions=1, risk_flags=[],
            entry="affinage", ci_class="passing",
        )
        assert result["n"] == 1

    def test_affinage_comments_and_ci_class_both_bump_in_one_call(self) -> None:
        # A small diff (n=1) with both a high comment count and a risky
        # ci_class must bump twice: 1 -> 4 -> 10, one step per signal, and
        # the rationale must record both reasons in the combined form.
        result = age_route.route(
            files_changed=1, insertions=2, deletions=1, risk_flags=[],
            entry="affinage", comments=15, ci_class="failing",
        )
        assert result["n"] == 10
        assert result["effort"] == "high"
        assert "15 comments + ci_class=failing" in result["rationale"]


class TestInputValidation:
    def test_invalid_entry_raises(self) -> None:
        with pytest.raises(ValueError):
            age_route.route(files_changed=1, insertions=1, deletions=0, entry="bogus")


class TestRationale:
    def test_rationale_is_one_line_and_mentions_decision(self) -> None:
        result = age_route.route(files_changed=3, insertions=20, deletions=20, risk_flags=[])
        assert "\n" not in result["rationale"]
        assert "n=1" in result["rationale"]
        assert "effort=medium" in result["rationale"]


class TestPurity:
    """Acceptance #4: the module is a pure function -- no os/network/file I/O."""

    def test_module_has_no_io_imports(self) -> None:
        src = (REPO_ROOT / "src" / "fanout" / "age_route.py").read_text(encoding="utf-8")
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
        src = (REPO_ROOT / "src" / "fanout" / "age_route.py").read_text(encoding="utf-8")
        ast.parse(src)  # raises SyntaxError if invalid


class TestLensSlugsMatchAgeFanoutContract:
    """Cross-language contract: every lens age_route can emit must byte-match
    age-fanout.js's DIM_SLUG_RE, or fan-out silently degrades to one reviewer
    (correctness:blocker -- see age_route.py's DIMENSIONS/LENS_GROUPS_N4).
    """

    def _dim_slug_re(self) -> re.Pattern[str]:
        src = (REPO_ROOT / "workflows" / "age-fanout.js").read_text(encoding="utf-8")
        match = re.search(r"const DIM_SLUG_PATTERN = '([^']+)'", src)
        assert match, "could not find DIM_SLUG_PATTERN in workflows/age-fanout.js"
        return re.compile(match.group(1))

    def test_every_dimension_matches_dim_slug_re(self) -> None:
        pattern = self._dim_slug_re()
        for dim in age_route.DIMENSIONS:
            assert pattern.match(dim), f"{dim!r} does not match age-fanout's DIM_SLUG_RE"

    def test_every_n4_lens_group_member_matches_dim_slug_re(self) -> None:
        pattern = self._dim_slug_re()
        for group in age_route.LENS_GROUPS_N4:
            for dim in group:
                assert pattern.match(dim), f"{dim!r} does not match age-fanout's DIM_SLUG_RE"
