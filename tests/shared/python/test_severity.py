"""Tests for shared/scripts/severity.py — rubric severity + fix-cost-now."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from easy_cheese.shared import severity

REPO_ROOT = Path(__file__).resolve().parents[3]
SEVERITY_CLI = REPO_ROOT / "src" / "easy_cheese" / "shared" / "severity.py"


class TestBump:
    def test_low_to_medium(self) -> None:
        assert severity.bump("low") == "medium"

    def test_medium_to_high(self) -> None:
        assert severity.bump("medium") == "high"

    def test_high_to_blocker(self) -> None:
        assert severity.bump("high") == "blocker"

    def test_blocker_caps(self) -> None:
        assert severity.bump("blocker") == "blocker"

    def test_unknown_raises(self) -> None:
        with pytest.raises(severity.RubricError, match="unknown severity"):
            _ = severity.bump("critical")


class TestComputeSeverity:
    def test_no_bumps(self) -> None:
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

    def test_contract_bump_on_sensitive_dim(self) -> None:
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

    def test_contract_does_not_bump_complexity(self) -> None:
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

    def test_contract_does_not_bump_deslop(self) -> None:
        assert (
            severity.compute_severity(
                dimension="deslop",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            == "medium"
        )

    def test_contract_does_not_bump_assertions(self) -> None:
        assert (
            severity.compute_severity(
                dimension="assertions",
                base="medium",
                location="contract",
                fix_cost_later="contained",
            )
            == "medium"
        )

    def test_structural_bump(self) -> None:
        assert (
            severity.compute_severity(
                dimension="complexity",  # not location-sensitive — isolate structural bump
                base="low",
                location="class",
                fix_cost_later="structural",
            )
            == "medium"
        )

    def test_both_bumps_canonical_example(self) -> None:
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

    def test_cap_at_blocker(self) -> None:
        assert (
            severity.compute_severity(
                dimension="security",
                base="blocker",
                location="contract",
                fix_cost_later="structural",
            )
            == "blocker"
        )

    def test_unknown_dimension(self) -> None:
        with pytest.raises(severity.RubricError, match="unknown dimension"):
            _ = severity.compute_severity(
                dimension="vibes",
                base="low",
                location="class",
                fix_cost_later="contained",
            )

    def test_unknown_base(self) -> None:
        with pytest.raises(severity.RubricError, match="unknown base"):
            _ = severity.compute_severity(
                dimension="security",
                base="critical",
                location="class",
                fix_cost_later="contained",
            )

    def test_unknown_location(self) -> None:
        with pytest.raises(severity.RubricError, match="unknown location"):
            _ = severity.compute_severity(
                dimension="security",
                base="low",
                location="galaxy",
                fix_cost_later="contained",
            )

    def test_unknown_fix_cost_later(self) -> None:
        with pytest.raises(severity.RubricError, match="unknown fix-cost-later"):
            _ = severity.compute_severity(
                dimension="security",
                base="low",
                location="class",
                fix_cost_later="explosive",
            )


class TestBucketFixCostNow:
    def test_contained_one_file(self) -> None:
        assert severity.bucket_fix_cost_now(file_count=1) == "contained"

    def test_contained_two_files(self) -> None:
        assert severity.bucket_fix_cost_now(file_count=2) == "contained"

    def test_moderate_lower_bound(self) -> None:
        assert severity.bucket_fix_cost_now(file_count=3) == "moderate"

    def test_moderate_upper_bound(self) -> None:
        assert severity.bucket_fix_cost_now(file_count=10) == "moderate"

    def test_sprawling_by_file_count(self) -> None:
        assert severity.bucket_fix_cost_now(file_count=11) == "sprawling"

    def test_sprawling_by_modules_overrides_low_files(self) -> None:
        # Two files but two modules — multi-module is sprawling regardless of count.
        assert severity.bucket_fix_cost_now(file_count=2, module_count=2) == "sprawling"

    def test_negative_files_rejected(self) -> None:
        with pytest.raises(severity.RubricError, match="file_count must be"):
            _ = severity.bucket_fix_cost_now(file_count=-1)

    def test_zero_modules_rejected(self) -> None:
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
