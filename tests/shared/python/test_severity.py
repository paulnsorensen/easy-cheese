"""Tests for shared/scripts/severity.py — rubric severity + fix-cost-now."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pytest

if TYPE_CHECKING:
    from easy_cheese.shared.severity import FixCostNow, RubricError, Severity

REPO_ROOT = Path(__file__).resolve().parents[3]
SEVERITY_CLI = REPO_ROOT / "src" / "easy_cheese" / "shared" / "severity.py"


class _SeverityModule(Protocol):
    RubricError: type[RubricError]
    Severity: type[Severity]
    FixCostNow: type[FixCostNow]

    def bump(self, sev: Severity) -> Severity: ...

    def compute_severity(
        self, *, dimension: str, base: str, location: str, fix_cost_later: str
    ) -> Severity: ...

    def bucket_fix_cost_now(self, *, file_count: int, module_count: int = 1) -> FixCostNow: ...


class TestSeverityLadder:
    def test_members_ascend_low_to_blocker(self, severity: _SeverityModule) -> None:
        sev = severity.Severity
        assert sev.LOW < sev.MEDIUM < sev.HIGH < sev.BLOCKER

    def test_str_is_the_report_spelling(self, severity: _SeverityModule) -> None:
        assert [str(tier) for tier in severity.Severity] == ["low", "medium", "high", "blocker"]

    def test_parse_accepts_report_spelling(self, severity: _SeverityModule) -> None:
        assert severity.Severity.parse("blocker", field="base") is severity.Severity.BLOCKER

    def test_parse_rejects_unknown_with_field_name_and_vocabulary(
        self, severity: _SeverityModule
    ) -> None:
        with pytest.raises(
            severity.RubricError,
            match=r"unknown base 'critical'; expected one of low, medium, high, blocker",
        ):
            _ = severity.Severity.parse("critical", field="base")

    def test_fix_cost_now_members_ascend(self, severity: _SeverityModule) -> None:
        cost = severity.FixCostNow
        assert cost.CONTAINED < cost.MODERATE < cost.SPRAWLING

    def test_fix_cost_now_str_is_the_report_spelling(self, severity: _SeverityModule) -> None:
        assert [str(tier) for tier in severity.FixCostNow] == [
            "contained",
            "moderate",
            "sprawling",
        ]


class TestBump:
    def test_low_to_medium(self, severity: _SeverityModule) -> None:
        assert severity.bump(severity.Severity.LOW) is severity.Severity.MEDIUM

    def test_medium_to_high(self, severity: _SeverityModule) -> None:
        assert severity.bump(severity.Severity.MEDIUM) is severity.Severity.HIGH

    def test_high_to_blocker(self, severity: _SeverityModule) -> None:
        assert severity.bump(severity.Severity.HIGH) is severity.Severity.BLOCKER

    def test_blocker_caps(self, severity: _SeverityModule) -> None:
        assert severity.bump(severity.Severity.BLOCKER) is severity.Severity.BLOCKER


class TestComputeSeverity:
    def test_no_bumps(self, severity: _SeverityModule) -> None:
        # Class-private encapsulation leak example from dimensions.md.
        assert (
            severity.compute_severity(
                dimension="encapsulation",
                base="low",
                location="class",
                fix_cost_later="contained",
            )
            is severity.Severity.LOW
        )

    def test_contract_bump_on_sensitive_dim(self, severity: _SeverityModule) -> None:
        # security at the contract boundary: medium base → high.
        assert (
            severity.compute_severity(
                dimension="security",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            is severity.Severity.HIGH
        )

    def test_contract_does_not_bump_complexity(self, severity: _SeverityModule) -> None:
        # complexity is NOT location-sensitive per the rubric table.
        assert (
            severity.compute_severity(
                dimension="complexity",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            is severity.Severity.MEDIUM
        )

    def test_contract_does_not_bump_deslop(self, severity: _SeverityModule) -> None:
        assert (
            severity.compute_severity(
                dimension="deslop",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            is severity.Severity.MEDIUM
        )

    def test_contract_does_not_bump_assertions(self, severity: _SeverityModule) -> None:
        assert (
            severity.compute_severity(
                dimension="assertions",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            is severity.Severity.MEDIUM
        )

    def test_structural_bump(self, severity: _SeverityModule) -> None:
        assert (
            severity.compute_severity(
                dimension="complexity",  # not location-sensitive — isolate structural bump
                base="low",
                location="class",
                fix_cost_later="structural",
            )
            is severity.Severity.MEDIUM
        )

    def test_both_bumps_canonical_example(self, severity: _SeverityModule) -> None:
        # The dimensions.md "mental shortcut": encapsulation leak at slice index.
        # base high → contract bump (high→blocker) → structural bump (capped) = blocker.
        assert (
            severity.compute_severity(
                dimension="encapsulation",
                base="high",
                location="contract",
                fix_cost_later="structural",
            )
            is severity.Severity.BLOCKER
        )

    def test_cap_at_blocker(self, severity: _SeverityModule) -> None:
        assert (
            severity.compute_severity(
                dimension="security",
                base="blocker",
                location="contract",
                fix_cost_later="structural",
            )
            is severity.Severity.BLOCKER
        )

    def test_unknown_dimension(self, severity: _SeverityModule) -> None:
        with pytest.raises(severity.RubricError, match="unknown dimension"):
            _ = severity.compute_severity(
                dimension="vibes",
                base="low",
                location="class",
                fix_cost_later="contained",
            )

    def test_unknown_base(self, severity: _SeverityModule) -> None:
        with pytest.raises(severity.RubricError, match="unknown base"):
            _ = severity.compute_severity(
                dimension="security",
                base="critical",
                location="class",
                fix_cost_later="contained",
            )

    def test_unknown_location(self, severity: _SeverityModule) -> None:
        with pytest.raises(severity.RubricError, match="unknown location"):
            _ = severity.compute_severity(
                dimension="security",
                base="low",
                location="galaxy",
                fix_cost_later="contained",
            )

    def test_unknown_fix_cost_later(self, severity: _SeverityModule) -> None:
        with pytest.raises(severity.RubricError, match="unknown fix-cost-later"):
            _ = severity.compute_severity(
                dimension="security",
                base="low",
                location="class",
                fix_cost_later="explosive",
            )


class TestBucketFixCostNow:
    def test_contained_one_file(self, severity: _SeverityModule) -> None:
        assert severity.bucket_fix_cost_now(file_count=1) is severity.FixCostNow.CONTAINED

    def test_contained_two_files(self, severity: _SeverityModule) -> None:
        assert severity.bucket_fix_cost_now(file_count=2) is severity.FixCostNow.CONTAINED

    def test_moderate_lower_bound(self, severity: _SeverityModule) -> None:
        assert severity.bucket_fix_cost_now(file_count=3) is severity.FixCostNow.MODERATE

    def test_moderate_upper_bound(self, severity: _SeverityModule) -> None:
        assert severity.bucket_fix_cost_now(file_count=10) is severity.FixCostNow.MODERATE

    def test_sprawling_by_file_count(self, severity: _SeverityModule) -> None:
        assert severity.bucket_fix_cost_now(file_count=11) is severity.FixCostNow.SPRAWLING

    def test_sprawling_by_modules_overrides_low_files(self, severity: _SeverityModule) -> None:
        # Two files but two modules — multi-module is sprawling regardless of count.
        assert severity.bucket_fix_cost_now(file_count=2, module_count=2) is severity.FixCostNow.SPRAWLING

    def test_negative_files_rejected(self, severity: _SeverityModule) -> None:
        with pytest.raises(severity.RubricError, match="file_count must be"):
            _ = severity.bucket_fix_cost_now(file_count=-1)

    def test_zero_modules_rejected(self, severity: _SeverityModule) -> None:
        with pytest.raises(severity.RubricError, match="module_count must be"):
            _ = severity.bucket_fix_cost_now(file_count=1, module_count=0)


class TestCli:
    def test_compute_subcommand(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SEVERITY_CLI),
                "compute",
                "--dimension",
                "encapsulation",
                "--base",
                "high",
                "--location",
                "contract",
                "--fix-cost-later",
                "structural",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "blocker"

    def test_bucket_subcommand(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SEVERITY_CLI), "bucket", "--files", "7"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "moderate"

    def test_bucket_multi_module(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SEVERITY_CLI),
                "bucket",
                "--files",
                "2",
                "--modules",
                "2",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "sprawling"

    def test_invalid_input_exits_nonzero(self) -> None:
        # --fix-cost-later "explosive" is rejected by RubricError → cli.CliError → exit 2
        result = subprocess.run(
            [
                sys.executable,
                str(SEVERITY_CLI),
                "compute",
                "--dimension",
                "encapsulation",
                "--base",
                "high",
                "--location",
                "contract",
                "--fix-cost-later",
                "explosive",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:")
        assert "fix-cost-later" in result.stderr

    def test_invalid_dimension_exits_two_with_error_prefix(self) -> None:
        # --dimension "vibes" is not in DIMENSIONS; cli.CliError emits "ERROR: ..."
        result = subprocess.run(
            [
                sys.executable,
                str(SEVERITY_CLI),
                "compute",
                "--dimension",
                "vibes",
                "--base",
                "high",
                "--location",
                "contract",
                "--fix-cost-later",
                "contained",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:")
        assert "dimension" in result.stderr
