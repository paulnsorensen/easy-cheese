"""Tests for src/easy_cheese_schemas/compat.py — the version-compat layer.

Covers every Provenance branch (including PRIOR, unreachable through `load`
while MIN_READABLE == SCHEMA_VERSION, via the classifier directly), both
strictness modes, the FUTURE best-effort path, Loaded's immutability, and the
distribution floors declared in pyproject.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from attrs import define, field
from attrs.exceptions import FrozenInstanceError

from easy_cheese_schemas import (
    MIN_READABLE,
    SCHEMA_VERSION,
    Loaded,
    Provenance,
    compat,
    load,
)
from easy_cheese_schemas.compat import STAMP_KEY, classify_stamp

REPO_ROOT = Path(__file__).resolve().parents[2]


@define
class Widget:
    name: str
    count: int = 3
    tags: list[str] = field(factory=list)


class TestClassifyStamp:
    def test_matching_stamp_is_current(self) -> None:
        assert classify_stamp(SCHEMA_VERSION) is Provenance.CURRENT

    def test_no_stamp_is_unstamped(self) -> None:
        assert classify_stamp(None) is Provenance.UNSTAMPED

    def test_stamp_below_floor_is_stale(self) -> None:
        assert classify_stamp(MIN_READABLE - 1) is Provenance.STALE

    def test_stamp_above_current_is_future(self) -> None:
        assert classify_stamp(SCHEMA_VERSION + 1) is Provenance.FUTURE

    def test_readable_older_stamp_is_prior(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # PRIOR is unreachable while MIN_READABLE == SCHEMA_VERSION, so widen
        # the window the way a real schema bump will: the N-1 branch must
        # classify the previous version as readable, not stale.
        monkeypatch.setattr(compat, "SCHEMA_VERSION", SCHEMA_VERSION + 1)
        monkeypatch.setattr(compat, "MIN_READABLE", SCHEMA_VERSION)
        assert classify_stamp(SCHEMA_VERSION) is Provenance.PRIOR


class TestProvenanceThroughLoad:
    def test_current_stamp(self) -> None:
        result = load({STAMP_KEY: SCHEMA_VERSION, "name": "a"}, Widget, strict=True)
        assert result.provenance is Provenance.CURRENT

    def test_missing_stamp_is_unstamped(self) -> None:
        result = load({"name": "a"}, Widget, strict=True)
        assert result.provenance is Provenance.UNSTAMPED

    def test_stale_stamp(self) -> None:
        result = load({STAMP_KEY: MIN_READABLE - 1, "name": "a"}, Widget, strict=True)
        assert result.provenance is Provenance.STALE

    def test_future_stamp(self) -> None:
        result = load({STAMP_KEY: SCHEMA_VERSION + 1, "name": "a"}, Widget, strict=True)
        assert result.provenance is Provenance.FUTURE


class TestStrictMode:
    def test_valid_payload_structures_cleanly(self) -> None:
        result = load(
            {STAMP_KEY: SCHEMA_VERSION, "name": "gouda", "count": 2, "tags": ["aged"]},
            Widget,
            strict=True,
        )
        assert result.value == Widget(name="gouda", count=2, tags=["aged"])
        assert result.problems == ()

    def test_malformed_payload_reports_every_problem_without_raising(self) -> None:
        # Accumulates every problem in one pass rather than stopping at the
        # first, and names each one exactly — the format is the contract.
        result = load({"count": "not-a-number"}, Widget, strict=True)
        assert result.value is None
        assert result.problems == (
            "Widget.name is required",
            "Widget.count must be an integer, not str",
        )

    def test_missing_optional_field_is_not_a_problem(self) -> None:
        result = load({"name": "gouda"}, Widget, strict=True)
        assert result.value == Widget(name="gouda")
        assert result.problems == ()


class TestLenientMode:
    def test_gaps_are_defaulted_and_recorded_one_per_field(self) -> None:
        result = load({"name": "gouda"}, Widget, strict=False)
        assert result.value == Widget(name="gouda", count=3, tags=[])
        assert result.problems == (
            "Widget.count must be present; using default",
            "Widget.tags must be present; using default",
        )

    def test_unstructurable_field_falls_back_to_its_default(self) -> None:
        result = load({"name": "gouda", "count": "not-a-number"}, Widget, strict=False)
        assert result.value == Widget(name="gouda", count=3, tags=[])
        assert result.problems == (
            "Widget.tags must be present; using default",
            "Widget.count must be an integer, not str",
        )

    def test_missing_required_field_reports_and_yields_no_value(self) -> None:
        result = load({}, Widget, strict=False)
        assert result.value is None
        assert "Widget.name is required" in result.problems


class TestFutureStamp:
    def test_unknown_field_is_ignored_and_flagged_future(self) -> None:
        result = load(
            {
                STAMP_KEY: SCHEMA_VERSION + 1,
                "name": "gouda",
                "count": 2,
                "tags": [],
                "rennet": "vegetarian",
            },
            Widget,
            strict=False,
        )
        assert result.provenance is Provenance.FUTURE
        assert result.value == Widget(name="gouda", count=2, tags=[])
        assert not hasattr(result.value, "rennet")
        assert result.problems == ()


class TestLoadNeverRaises:
    """`load` states the invariant unconditionally, so the hostile inputs that
    reach it from a corpus document must come back as problems, not tracebacks."""

    def test_non_attrs_class_is_reported_not_raised(self) -> None:
        result = load({"a": 1}, dict, strict=False)
        assert result.value is None
        assert result.problems == ("dict is not a schema type",)

    def test_non_mapping_payload_is_reported_not_raised(self) -> None:
        result = load([1], Widget, strict=True)
        assert result.value is None
        assert result.problems == ("Widget must be a mapping, not list",)

    def test_non_integer_stamp_keeps_the_value_and_records_the_problem(self) -> None:
        # A stamp you cannot trust is not a reason to discard a readable
        # document, so the value survives and provenance degrades to UNSTAMPED.
        result = load({STAMP_KEY: "one", "name": "gouda"}, Widget, strict=True)
        assert result.value == Widget(name="gouda")
        assert result.provenance is Provenance.UNSTAMPED
        assert result.problems == ("Widget.schema_version must be an integer",)

    def test_bool_stamp_is_not_mistaken_for_version_one(self) -> None:
        assert classify_stamp(True) is not Provenance.CURRENT


class TestLoadedShape:
    def test_loaded_is_frozen(self) -> None:
        result = Loaded(value=Widget(name="gouda"), provenance=Provenance.CURRENT, problems=[])
        with pytest.raises(FrozenInstanceError):
            result.value = None  # type: ignore[misc]


class TestDistributionMetadata:
    def _pyproject(self) -> dict:
        return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())

    def test_python_floor_is_311(self) -> None:
        assert self._pyproject()["project"]["requires-python"] == ">=3.11"

    def test_dependency_floors_match_the_vendored_versions(self) -> None:
        # The floors are only meaningful if something exercises them, and the
        # suite runs against vendor/. Declaring a lower floor would be an
        # untested claim, so the two must agree.
        import attrs

        deps = self._pyproject()["project"]["dependencies"]
        assert f"attrs>={attrs.__version__}" in deps
        assert "cattrs>=26.1.0" in deps

        readme = (REPO_ROOT / "vendor" / "README.md").read_text(encoding="utf-8")
        assert "| cattrs | 26.1.0 |" in readme

    def test_version_matches_package(self) -> None:
        import easy_cheese_schemas

        assert self._pyproject()["project"]["version"] == easy_cheese_schemas.__version__
