"""Tests for easy_cheese_review.severity: rubric severity and fix-cost-now."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pytest
from easy_cheese_schemas import ReviewDimension

if TYPE_CHECKING:
    from easy_cheese_review.severity import RubricError, Severity
    from easy_cheese_schemas.contracts import FixCostNow


class _SeverityModule(Protocol):
    RubricError: type[RubricError]
    Severity: type[Severity]
    FixCostNow: type[FixCostNow]
    LOCATION_SENSITIVITY: Mapping[ReviewDimension, bool]

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


DIMENSIONS_PROSE = Path(__file__).resolve().parents[3] / "skills/age/references/dimensions.md"
_TABLE_ROW = re.compile(r"^\|\s*(?P<dimension>[a-z]+)\s*\|\s*(?P<bump>yes|no)\s*\|", re.MULTILINE)


def _prose_location_sensitivity() -> dict[str, bool]:
    """Parse the "Location sensitivity" table of dimensions.md into dimension -> bump?."""
    text = DIMENSIONS_PROSE.read_text(encoding="utf-8")
    section = text.split("## Location sensitivity", 1)[1].split("\n## ", 1)[0]
    return {m["dimension"]: m["bump"] == "yes" for m in _TABLE_ROW.finditer(section)}


class TestLocationSensitivity:
    def test_every_dimension_is_classified(self, severity: _SeverityModule) -> None:
        classified = set(severity.LOCATION_SENSITIVITY)
        assert classified == set(ReviewDimension)
        assert all(isinstance(flag, bool) for flag in severity.LOCATION_SENSITIVITY.values())

    def test_code_map_matches_the_prose_table(self, severity: _SeverityModule) -> None:
        prose = _prose_location_sensitivity()
        code = {dim.value: flag for dim, flag in severity.LOCATION_SENSITIVITY.items()}
        assert prose, "no rows parsed from the Location sensitivity table"
        assert code == prose

    def test_contract_bump_matches_the_map_for_every_dimension(
        self, severity: _SeverityModule
    ) -> None:
        for dim, sensitive in severity.LOCATION_SENSITIVITY.items():
            got = severity.compute_severity(
                dimension=dim.value, base="low", location="contract", fix_cost_later="contained"
            )
            assert got is (severity.Severity.MEDIUM if sensitive else severity.Severity.LOW), dim


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