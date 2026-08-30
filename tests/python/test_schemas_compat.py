"""Tests for src/easy_cheese_schemas/compat.py — the version-compat layer.

Covers every Provenance branch (including PRIOR, unreachable through `load`
while MIN_READABLE == SCHEMA_VERSION, via the classifier directly), both
strictness modes, the FUTURE best-effort path, Loaded's immutability, and the
distribution floors declared in pyproject.toml.
"""

from __future__ import annotations

from copy import deepcopy
import re
import tomllib
from pathlib import Path
from typing import cast

import pytest
from attrs import define, field
from attrs.exceptions import FrozenInstanceError

from easy_cheese_schemas import (
    MIN_READABLE,
    SCHEMA_VERSION,
    EvidenceOrigin,
    GateMode,
    GateProducer,
    GateReceipt,
    Loaded,
    Provenance,
    compat,
    load,
)
from easy_cheese_schemas.compat import STAMP_KEY, classify_stamp


GATE_PAYLOAD: dict[str, object] = {
    STAMP_KEY: SCHEMA_VERSION,
    "work_id": "work-compat",
    "project_key": "easy-cheese",
    "producer": "press",
    "disposition": "red",
    "spec_ref": None,
    "spec_sha256": None,
    "guard_receipt_refs": [],
    "contracts": [
        {
            "acceptance_id": "AC-11",
            "interface": "GateReceipt",
            "seam": "press gate",
            "expected_failure": "unsafe shape is rejected",
            "mode": "tracer",
            "contract_source": "inferred",
        }
    ],
    "baseline_checks": [
        {
            "id": "baseline",
            "argv": ["python", "-m", "pytest"],
            "cwd": ".",
            "observed_exit_code": 0,
        }
    ],
    "cases": [
        {
            "id": "unsafe-shape",
            "acceptance_ids": ["AC-11"],
            "curd": None,
            "seam": "press gate",
            "argv": ["python", "-m", "pytest"],
            "cwd": ".",
            "kind": "behavior",
            "origin": "adopted",
            "expected_witness": ["shape rejected"],
            "observed_exit_code": 2,
            "observed_witness": "shape rejected",
        }
    ],
    "protected_files": [
        {"path": "src/easy_cheese_schemas/gates.py", "sha256": "b" * 64}
    ],
    "not_applicable_reason": None,
}


def _runtime_pins() -> dict[str, str]:
    text = (REPO_ROOT / "requirements" / "runtime.txt").read_text()
    return dict(re.findall(r"^([A-Za-z0-9_-]+)==([^ ]+)", text, re.MULTILINE))


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


class TestGateReceiptCompatibility:
    def test_strict_load_normalizes_problems_to_a_tuple(self) -> None:
        result = load(deepcopy(GATE_PAYLOAD), GateReceipt, strict=True)

        assert result.provenance is Provenance.CURRENT
        assert result.problems == ()
        assert isinstance(result.problems, tuple)
        assert result.value is not None
        assert result.value.producer is GateProducer.PRESS
        assert result.value.contracts[0].mode is GateMode.TRACER
        assert result.value.cases[0].origin is EvidenceOrigin.ADOPTED

    def test_future_receipt_keeps_value_and_ignores_additive_fields(self) -> None:
        payload = deepcopy(GATE_PAYLOAD)
        payload[STAMP_KEY] = SCHEMA_VERSION + 1
        payload["future_key"] = "ignored"

        result = load(payload, GateReceipt, strict=True)

        assert result.provenance is Provenance.FUTURE
        assert result.problems == ()
        assert result.value is not None
        assert not hasattr(result.value, "future_key")
        contracts = cast(list[dict[str, object]], result.value.to_dict()["contracts"])
        assert contracts[0]["mode"] == "tracer"

    def test_malformed_receipt_problems_are_deterministic_and_accumulated(self) -> None:
        payload = deepcopy(GATE_PAYLOAD)
        payload["work_id"] = 7
        cast(list[dict[str, object]], payload["contracts"])[0]["mode"] = "not-a-mode"
        payload["guard_receipt_refs"] = ("prior",)

        first = load(payload, GateReceipt, strict=True)
        second = load(payload, GateReceipt, strict=True)

        assert first.value is None
        assert first.problems == second.problems
        assert first.problems == (
            "GateReceipt.work_id must be a string, not int",
            "GateReceipt.guard_receipt_refs must be a list, not tuple",
            "GateReceipt.contracts[1].mode must be one of: tracer, contract-matrix",
        )


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
        result = load({"a": 1}, dict[str, object], strict=False)
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
            result.value = None  # pyright: ignore[reportAttributeAccessIssue]


class TestDistributionMetadata:
    def _pyproject(self) -> dict[str, object]:
        return cast(dict[str, object], tomllib.loads((REPO_ROOT / "pyproject.toml").read_text()))

    def _project(self) -> dict[str, object]:
        return cast(dict[str, object], self._pyproject()["project"])

    def test_python_floor_is_311(self) -> None:
        assert self._project()["requires-python"] == ">=3.11"

    def test_dependency_floors_match_the_locked_versions(self) -> None:
        # The floors are only meaningful if the suite exercises the locked
        # runtime versions used to assemble the private wheelhouse.
        # Declaring a lower floor would be an untested claim, so the two must
        # agree -- which is why a dependency bump lands here before it merges.
        import attrs

        pins = _runtime_pins()
        deps = cast(list[str], self._project()["dependencies"])
        assert pins["attrs"] == attrs.__version__
        assert f"attrs>={pins['attrs']}" in deps
        assert f"cattrs>={pins['cattrs']}" in deps

    def test_version_matches_package(self) -> None:
        import easy_cheese_schemas

        assert self._project()["version"] == easy_cheese_schemas.__version__
