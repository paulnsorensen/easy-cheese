"""Tests for shared/scripts/severity.py — rubric severity + fix-cost-now."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SEVERITY_CLI = REPO_ROOT / "shared" / "scripts" / "severity.py"


class TestBump:
    def test_low_to_medium(self, severity: ModuleType) -> None:
        assert severity.bump("low") == "medium"

    def test_medium_to_high(self, severity: ModuleType) -> None:
        assert severity.bump("medium") == "high"

    def test_high_to_blocker(self, severity: ModuleType) -> None:
        assert severity.bump("high") == "blocker"

    def test_blocker_caps(self, severity: ModuleType) -> None:
        assert severity.bump("blocker") == "blocker"

    def test_unknown_raises(self, severity: ModuleType) -> None:
        with pytest.raises(severity.RubricError, match="unknown severity"):
            severity.bump("critical")


class TestComputeSeverity:
    def test_no_bumps(self, severity: ModuleType) -> None:
        # Class-private encapsulation leak example from dimensions.md.
        assert (
            severity.compute_severity(
                dimension="encapsulation",
                base="low",
                location="class",
                fix_cost_later="contained",
            )
            == "low"
        )

    def test_contract_bump_on_sensitive_dim(self, severity: ModuleType) -> None:
        # security at the contract boundary: medium base → high.
        assert (
            severity.compute_severity(
                dimension="security",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            == "high"
        )

    def test_contract_does_not_bump_complexity(self, severity: ModuleType) -> None:
        # complexity is NOT location-sensitive per the rubric table.
        assert (
            severity.compute_severity(
                dimension="complexity",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            == "medium"
        )

    def test_contract_does_not_bump_deslop(self, severity: ModuleType) -> None:
        assert (
            severity.compute_severity(
                dimension="deslop",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            == "medium"
        )

    def test_contract_does_not_bump_assertions(self, severity: ModuleType) -> None:
        assert (
            severity.compute_severity(
                dimension="assertions",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            == "medium"
        )

    def test_structural_bump(self, severity: ModuleType) -> None:
        assert (
            severity.compute_severity(
                dimension="complexity",  # not location-sensitive — isolate structural bump
                base="low",
                location="class",
                fix_cost_later="structural",
            )
            == "medium"
        )

    def test_both_bumps_canonical_example(self, severity: ModuleType) -> None:
        # The dimensions.md "mental shortcut": encapsulation leak at slice index.
        # base high → contract bump (high→blocker) → structural bump (capped) = blocker.
        assert (
            severity.compute_severity(
                dimension="encapsulation",
                base="high",
                location="contract",
                fix_cost_later="structural",
            )
            == "blocker"
        )

    def test_cap_at_blocker(self, severity: ModuleType) -> None:
        assert (
            severity.compute_severity(
                dimension="security",
                base="blocker",
                location="contract",
                fix_cost_later="structural",
            )
            == "blocker"
        )

    def test_unknown_dimension(self, severity: ModuleType) -> None:
        with pytest.raises(severity.RubricError, match="unknown dimension"):
            severity.compute_severity(
                dimension="vibes",
                base="low",
                location="class",
                fix_cost_later="contained",
            )

    def test_unknown_base(self, severity: ModuleType) -> None:
        with pytest.raises(severity.RubricError, match="unknown base"):
            severity.compute_severity(
                dimension="security",
                base="critical",
                location="class",
                fix_cost_later="contained",
            )

    def test_unknown_location(self, severity: ModuleType) -> None:
        with pytest.raises(severity.RubricError, match="unknown location"):
            severity.compute_severity(
                dimension="security",
                base="low",
                location="galaxy",
                fix_cost_later="contained",
            )

    def test_unknown_fix_cost_later(self, severity: ModuleType) -> None:
        with pytest.raises(severity.RubricError, match="unknown fix-cost-later"):
            severity.compute_severity(
                dimension="security",
                base="low",
                location="class",
                fix_cost_later="explosive",
            )


class TestBucketFixCostNow:
    def test_contained_one_file(self, severity: ModuleType) -> None:
        assert severity.bucket_fix_cost_now(file_count=1) == "contained"

    def test_contained_two_files(self, severity: ModuleType) -> None:
        assert severity.bucket_fix_cost_now(file_count=2) == "contained"

    def test_moderate_lower_bound(self, severity: ModuleType) -> None:
        assert severity.bucket_fix_cost_now(file_count=3) == "moderate"

    def test_moderate_upper_bound(self, severity: ModuleType) -> None:
        assert severity.bucket_fix_cost_now(file_count=10) == "moderate"

    def test_sprawling_by_file_count(self, severity: ModuleType) -> None:
        assert severity.bucket_fix_cost_now(file_count=11) == "sprawling"

    def test_sprawling_by_modules_overrides_low_files(self, severity: ModuleType) -> None:
        # Two files but two modules — multi-module is sprawling regardless of count.
        assert severity.bucket_fix_cost_now(file_count=2, module_count=2) == "sprawling"

    def test_negative_files_rejected(self, severity: ModuleType) -> None:
        with pytest.raises(severity.RubricError, match="file_count must be"):
            severity.bucket_fix_cost_now(file_count=-1)

    def test_zero_modules_rejected(self, severity: ModuleType) -> None:
        with pytest.raises(severity.RubricError, match="module_count must be"):
            severity.bucket_fix_cost_now(file_count=1, module_count=0)


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
