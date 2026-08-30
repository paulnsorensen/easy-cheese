"""Tests for the easy-cheese-schemas v0.1 typed surface.

The types mirror contracts that today live in hand-rolled validators
(src/fanout/*, shared/scripts/*). Where a contract has an executable original
-- `gates.classify_readiness` and `io.parse_mapping` -- the test imports that
original by path and asserts the port agrees on every input, so drift is caught
mechanically instead of by a copied expectation table.
"""

from __future__ import annotations

import importlib.util
import itertools
import re
import sys
from copy import deepcopy
from pathlib import Path
from enum import Enum
from types import ModuleType
from typing import Protocol, cast, final

import pytest

from easy_cheese_schemas import gates, io, load
from easy_cheese_schemas.curd import MAX_WAVE_SIZE, MIN_CURD_SURFACE, CurdBlock
from easy_cheese_schemas.decomposition import Decomposition
from easy_cheese_schemas.manifest import Phase, RunManifest
from easy_cheese_schemas.pr_plan import PrPlan
from easy_cheese_schemas.gates import (
    BaselineCheck,
    EvidenceOrigin,
    GateDisposition,
    GateMode,
    GateProducer,
    GateReceipt,
    ProtectedFile,
    RedCase,
    RedKind,
    TestContract as GateTestContract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _runtime_pins() -> dict[str, str]:
    text = (REPO_ROOT / "requirements" / "runtime.txt").read_text()
    return dict(re.findall(r"^([A-Za-z0-9_-]+)==([^ ]+)", text, re.MULTILINE))


def _original(name: str) -> ModuleType:
    """Import shared/scripts/<name>.py under a private name, so the port is
    compared against the running implementation rather than a copy of it."""
    path = REPO_ROOT / "src" / "easy_cheese" / "shared" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_original_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _as_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _as_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


class _OriginalReadiness(str, Enum):
    READY = "ready for /age"
    FOLLOW_UP = "follow-up recommended"
    BLOCKED = "blocked"


class _GatesOriginal(Protocol):
    Readiness: type[_OriginalReadiness]

    def classify_readiness(
        self,
        *,
        hard_floor_met: bool,
        has_open_level_1_or_2: bool,
        has_open_level_3: bool,
        has_open_level_4_or_5: bool,
        any_spinning: bool,
    ) -> _OriginalReadiness: ...


class _ManifestIoOriginal(Protocol):
    ManifestLoadError: type[Exception]

    def parse_mapping(self, text: str, source: str = ...) -> dict[str, object]: ...


REVIEW_CONTEXT: dict[str, object] = {
    "base_commit": "a" * 40,
    "reviewed_tree_oid": "b" * 40,
    "diff_hash": "sha256:" + "c" * 64,
    "scope": ["src/easy_cheese_schemas/"],
}

AGENT_RESOLUTION: dict[str, object] = {
    "request": {
        "work": "implement one curd",
        "preferred_types": ["coder"],
        "required_tools": ["tilth_write"],
        "permissions": "write",
        "isolation": "isolated-worktree",
        "minimum_power": "default",
        "effort": "high",
    },
    "attempts": [
        {
            "type": "coder",
            "model": "claude-opus-5",
            "power": "powerful",
            "result": "accepted",
            "reason": "preferred type available",
        }
    ],
    "resolved": {
        "type": "coder",
        "model": "claude-opus-5",
        "power": "powerful",
        "effort": "high",
        "topology": "parallel",
    },
    "fallback_reason": None,
    "degraded": False,
    "permission_enforcement": "tool-restricted",
}

CURD_RECORD: dict[str, object] = {
    "id": 1,
    "behavior": "adds the attrs types for the schemas package",
    "acceptance_criterion": "tests/python/test_schemas_types.py passes",
    "files": ["src/easy_cheese_schemas/manifest.py"],
    "test_target": "pytest tests/python/test_schemas_types.py",
    "status": "pending",
    "retry_count": 0,
}

WIRING_ROW: dict[str, object] = {
    "id": "W1",
    "type": "barrel_export",
    "file": "src/easy_cheese_schemas/__init__.py",
    "depends_on": [],
    "status": "pending",
}

RUN_MANIFEST: dict[str, object] = {
    "slug": "pypi",
    "spec_path": ".cheese/specs/pypi.md",
    "created": "2026-08-01T00:00:00Z",
    "phase": "gate_approved",
    "quality_gates": ["just check"],
    "host_capabilities": {"gh": True, "melt": False},
    "agent_resolution": AGENT_RESOLUTION,
    "seed": {
        "items": [
            {
                "description": "freeze the compat surface",
                "files": ["src/easy_cheese_schemas/compat.py"],
                "status": "completed",
                "commit_sha": "abc1234",
            }
        ]
    },
    "curds": [CURD_RECORD],
    "wiring": [WIRING_ROW],
}

DECOMPOSITION: dict[str, object] = {"curds": [CURD_RECORD], "wiring": [WIRING_ROW]}

CURD_BLOCK: dict[str, object] = {
    "curds": [
        {
            "slug": "schema-types",
            "contract": "Add the attrs types for the v0.1 public surface.",
            "files": ["src/easy_cheese_schemas/manifest.py"],
            "test_target": "pytest tests/python/test_schemas_types.py",
            "acceptance": ["every gate is green"],
            "seed": ["easy_cheese_schemas.compat.load"],
            "est_edit_lines": 600,
        }
    ],
    "waves": [["schema-types"]],
    "decomposer": {"source": "cook", "model": "claude-opus-5", "prompt_version": "v1"},
}

PR_PLAN: dict[str, object] = {
    "shape": "single",
    "groups": [
        {
            "branch": "claude/pypi",
            "title": "feat(schemas): add the typed v0.1 surface",
            "base": "main",
            "commits": ["abc1234"],
        }
    ],
}


GATE_DIGEST = "a" * 64

GATE_RED: dict[str, object] = {
    "schema_version": 1,
    "work_id": "work-outer-tdd",
    "project_key": "easy-cheese",
    "producer": "cut",
    "disposition": "red",
    "spec_ref": ".cheese/specs/outer-tdd-gates.md",
    "spec_sha256": GATE_DIGEST,
    "guard_receipt_refs": [],
    "contracts": [
        {
            "acceptance_id": "AC-4",
            "interface": "GateReceipt",
            "seam": "red-gate validate --state red",
            "expected_failure": "the outer tracer assertion fails",
            "mode": "tracer",
            "contract_source": "approved",
        }
    ],
    "baseline_checks": [
        {
            "id": "baseline",
            "argv": ["python", "-m", "pytest", "tests/test_outer.py"],
            "cwd": ".",
            "observed_exit_code": 0,
        }
    ],
    "cases": [
        {
            "id": "AC-4-tracer",
            "acceptance_ids": ["AC-4"],
            "curd": "gate-receipt-schema",
            "seam": "red-gate validate --state red",
            "argv": ["python", "-m", "pytest", "tests/test_outer.py", "-k", "AC-4"],
            "cwd": ".",
            "kind": "behavior",
            "origin": "generated",
            "expected_witness": ["assertion failed: expected outer behavior"],
            "observed_exit_code": 1,
            "observed_witness": "assertion failed: expected outer behavior",
        }
    ],
    "protected_files": [
        {
            "path": "tests/test_outer.py",
            "sha256": GATE_DIGEST,
        }
    ],
    "phase_token_ref": None,
    "phase_token_sha256": None,
    "not_applicable_reason": None,
}

GATE_NOT_APPLICABLE: dict[str, object] = {
    **deepcopy(GATE_RED),
    "disposition": "not-applicable",
    "guard_receipt_refs": [],
    "contracts": [],
    "baseline_checks": [],
    "cases": [],
    "protected_files": [],
    "not_applicable_reason": "appearance-only change",
}


def _without(payload: dict[str, object], key: str) -> dict[str, object]:
    """Drop `key`; a dotted key reaches into a nested mapping."""
    stripped = deepcopy(payload)
    *parents, leaf = key.split(".")
    target = stripped
    for parent in parents:
        target = _as_dict(target[parent])
    del target[leaf]
    return stripped


def _curd(slug: str, path: str) -> dict[str, object]:
    entry = _as_dict(deepcopy(_as_list(CURD_BLOCK["curds"])[0]))
    entry["slug"] = slug
    entry["files"] = [path]
    return entry


ARTIFACTS = [
    pytest.param(RUN_MANIFEST, RunManifest, "phase", id="run-manifest"),
    pytest.param(
        RUN_MANIFEST,
        RunManifest,
        "agent_resolution.resolved",
        id="run-manifest-nested",
    ),
    pytest.param(DECOMPOSITION, Decomposition, "curds", id="decomposition"),
    pytest.param(CURD_BLOCK, CurdBlock, "decomposer", id="curd-block"),
    pytest.param(PR_PLAN, PrPlan, "groups", id="pr-plan"),
]


class TestArtifactRoundTrip:
    @pytest.mark.parametrize(("payload", "cls", "required_key"), ARTIFACTS)
    def test_valid_payload_structures_without_problems(
        self, payload: dict[str, object], cls: type[object], required_key: str
    ) -> None:
        _ = required_key
        result = load(deepcopy(payload), cls, strict=True)
        assert result.problems == ()
        assert isinstance(result.value, cls)

    @pytest.mark.parametrize(("payload", "cls", "required_key"), ARTIFACTS)
    def test_missing_required_key_is_named_and_yields_no_value(
        self, payload: dict[str, object], cls: type[object], required_key: str
    ) -> None:
        result = load(_without(payload, required_key), cls, strict=True)
        assert result.value is None
        assert f"{cls.__name__}.{required_key} is required" in result.problems


class TestRunManifestFields:
    def test_phase_structures_into_the_lifecycle_enum(self) -> None:
        manifest = load(deepcopy(RUN_MANIFEST), RunManifest, strict=True).value
        assert manifest is not None
        assert manifest.phase is Phase.GATE_APPROVED
        assert manifest.curds[0].id == 1
        assert manifest.wiring[0].id == "W1"
        assert manifest.seed.items[0].commit_sha == "abc1234"

    def test_unknown_phase_is_rejected(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["phase"] = "cheese_complete"
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.phase must be one of: gate_approved, seed_complete, "
            + "curds_complete, merge_complete, wiring_complete, final_merge_complete, "
            + "post_review_complete, pr_publish_complete",
        )

    def test_review_context_rejects_a_short_tree_oid(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["current_review"] = dict(REVIEW_CONTEXT, reviewed_tree_oid="abc123")
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.current_review.reviewed_tree_oid must be exactly 40 or 64 "
            + "hexadecimal characters",
        )

    def test_review_context_accepts_the_documented_shape(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["current_review"] = deepcopy(REVIEW_CONTEXT)
        result = load(payload, RunManifest, strict=True)
        assert result.problems == ()
        assert result.value is not None
        assert result.value.current_review is not None
        assert result.value.current_review.scope == ["src/easy_cheese_schemas/"]


class TestRunManifestCollectionRules:
    """Rules over the whole collection: a manifest whose every field is valid can
    still describe a run that cannot be dispatched."""

    def test_two_curds_claiming_one_file_are_rejected(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["curds"] = [deepcopy(CURD_RECORD), dict(deepcopy(CURD_RECORD), id=2)]
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.curds must be file-disjoint: file "
            + "'src/easy_cheese_schemas/manifest.py' appears in curd 1 and curd 2 "
            + "(move shared content to seed or wiring)",
        )

    def test_a_collection_rule_does_not_mask_a_field_problem(self) -> None:
        """Collection rules used to run in __attrs_post_init__, which raises
        inside __init__ and aborted the whole pass — so a manifest that broke a
        field rule AND a collection rule reported only the collection one. Both
        must surface, or the one-pass contract is a lie for exactly the
        documents that need it most."""
        payload = deepcopy(RUN_MANIFEST)
        payload["slug"] = ""
        payload["curds"] = [deepcopy(CURD_RECORD), dict(deepcopy(CURD_RECORD), id=2)]
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.slug must be a non-empty string",
            "RunManifest.curds must be file-disjoint: file "
            + "'src/easy_cheese_schemas/manifest.py' appears in curd 1 and curd 2 "
            + "(move shared content to seed or wiring)",
        )

    def test_wiring_cycle_is_rejected(self) -> None:
        """Wiring rows are applied in dependency order, so a cycle has no order."""
        payload = deepcopy(RUN_MANIFEST)
        payload["wiring"] = [
            dict(WIRING_ROW, id="W1", depends_on=["W2"]),
            dict(WIRING_ROW, id="W2", depends_on=["W1"]),
        ]
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.wiring must be schedulable: the dependency graph has cycle "
            + "W1 -> W2 -> W1",
        )

    def test_wiring_depending_on_an_unknown_row_is_rejected(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["wiring"] = [dict(WIRING_ROW, id="W1", depends_on=["W9"])]
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.wiring must be schedulable: W1 depends_on references "
            + "unknown id 'W9'",
        )

    def test_a_curd_id_dependency_is_not_a_wiring_dependency(self) -> None:
        """Only W<n> ids name wiring rows; a curd id dependency is legitimate."""
        payload = deepcopy(RUN_MANIFEST)
        payload["wiring"] = [dict(WIRING_ROW, id="W1", depends_on=["1"])]
        assert load(payload, RunManifest, strict=True).problems == ()

    def test_a_nested_gap_is_attributed_to_its_full_path(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        del _as_dict(payload["agent_resolution"])["resolved"]
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == ("RunManifest.agent_resolution.resolved is required",)

    def test_a_gap_inside_a_list_carries_its_1_based_index(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        second = {
            key: value
            for key, value in dict(deepcopy(CURD_RECORD), id=2).items()
            if key != "files"
        }
        payload["curds"] = [deepcopy(CURD_RECORD), second]
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == ("RunManifest.curds[2].files is required",)


class TestPrimitivesAreCheckedNotCoerced:
    """cattrs coerces primitives by calling the type -- str(v), int(v), list(v).
    A reader asking whether a document is trustworthy must not be handed a
    repaired copy of an untrustworthy one, so each of these must be reported."""

    def test_a_string_is_not_a_list_of_strings(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        _as_dict(_as_list(payload["curds"])[0])["files"] = "src/a.py"
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == ("RunManifest.curds[1].files must be a list, not str",)

    def test_a_boolean_is_not_an_integer(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        _as_dict(_as_list(payload["curds"])[0])["retry_count"] = True
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.curds[1].retry_count must be an integer, not bool",
        )

    def test_an_integer_is_not_a_string(self) -> None:
        payload = dict(deepcopy(RUN_MANIFEST), slug=7)
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == ("RunManifest.slug must be a string, not int",)

    def test_a_null_is_not_a_string(self) -> None:
        payload = dict(deepcopy(RUN_MANIFEST), created=None)
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == ("RunManifest.created must be a string, not NoneType",)

    def test_a_blank_string_is_not_a_behaviour(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        _as_dict(_as_list(payload["curds"])[0])["behavior"] = "   "
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.curds[1].behavior must be a non-empty string",
        )


class TestCurdBlockInvariants:
    def test_wave_over_the_cap_is_rejected(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        slugs = [f"curd-{index}" for index in range(MAX_WAVE_SIZE + 1)]
        payload["curds"] = [_curd(slug, f"src/{slug}.py") for slug in slugs]
        payload["waves"] = [slugs]
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert result.problems == (
            f"CurdBlock.waves[1] must be at most {MAX_WAVE_SIZE} slugs wide, not "
            + f"{MAX_WAVE_SIZE + 1}",
        )

    def test_wave_at_the_cap_is_accepted(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        slugs = [f"curd-{index}" for index in range(MAX_WAVE_SIZE)]
        payload["curds"] = [_curd(slug, f"src/{slug}.py") for slug in slugs]
        payload["waves"] = [slugs]
        assert load(payload, CurdBlock, strict=True).problems == ()

    def test_wave_referencing_an_unknown_slug_is_rejected(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        payload["waves"] = [["schema-types", "no-such-curd"]]
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert result.problems == (
            "CurdBlock.waves[1] must reference a declared curd slug, not "
            + "'no-such-curd'",
        )

    def test_curd_below_the_surface_floor_is_a_merge_candidate(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        _as_dict(_as_list(payload["curds"])[0])["est_edit_lines"] = MIN_CURD_SURFACE - 1
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert result.problems == (
            "CurdBlock.curds[1].est_edit_lines must be at least the surface floor "
            + f"of {MIN_CURD_SURFACE}, not {MIN_CURD_SURFACE - 1} -- this curd is a "
            + "MERGE CANDIDATE: merge it into a sibling curd rather than dispatch a "
            + "fresh coder for it",
        )

    def test_curd_at_the_surface_floor_is_accepted(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        _as_dict(_as_list(payload["curds"])[0])["est_edit_lines"] = MIN_CURD_SURFACE
        assert load(payload, CurdBlock, strict=True).problems == ()

    def test_curds_sharing_a_file_are_rejected(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        shared = "src/easy_cheese_schemas/manifest.py"
        payload["curds"] = [_curd("first", shared), _curd("second", shared)]
        payload["waves"] = [["first", "second"]]
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert result.problems == (
            f"CurdBlock.curds must be pairwise file-disjoint: file {shared!r} "
            + "appears in curd 'first' and curd 'second'",
        )

    def test_unknown_decomposer_source_is_rejected(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        _as_dict(payload["decomposer"])["source"] = "vibes"
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert result.problems == (
            "CurdBlock.decomposer.source must be one of: mold, cook",
        )


class TestDecompositionInvariants:
    def test_curds_need_no_run_lifecycle_fields(self) -> None:
        """A decomposition is written before any run exists, so it has no id,
        status, or retry_count to give -- demanding them would make the type
        unable to read the artifact src/fanout/validate_decomposition.py
        accepts."""
        pre_run = {
            key: value
            for key, value in deepcopy(CURD_RECORD).items()
            if key not in ("id", "status", "retry_count")
        }
        result = load({"curds": [pre_run], "wiring": []}, Decomposition, strict=True)
        assert result.problems == ()
        assert result.value is not None
        assert result.value.curds[0].behavior == CURD_RECORD["behavior"]

    def test_parallel_decomposition_rejects_overlapping_curd_files(self) -> None:
        shared = dict(CURD_RECORD, id=2, files=CURD_RECORD["files"])
        result = load(
            {"curds": [deepcopy(CURD_RECORD), shared], "wiring": []},
            Decomposition,
            strict=True,
        )
        assert result.value is None
        assert result.problems == (
            "Decomposition.curds must be file-disjoint: file "
            + "'src/easy_cheese_schemas/manifest.py' appears in curd 1 and curd 2 "
            + "(move shared content to seed or wiring)",
        )

    def test_empty_curds_is_rejected(self) -> None:
        result = load({"curds": [], "wiring": []}, Decomposition, strict=True)
        assert result.value is None
        assert result.problems == ("Decomposition.curds must be a non-empty list",)


class TestPrPlanInvariants:
    def test_branch_with_a_newline_is_rejected(self) -> None:
        payload = deepcopy(PR_PLAN)
        _as_dict(_as_list(payload["groups"])[0])["branch"] = "claude/pypi\nrm -rf /"
        result = load(payload, PrPlan, strict=True)
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups[1].branch contains characters unsafe for a git ref",
        )

    def test_commit_that_is_not_a_hex_sha_is_rejected(self) -> None:
        payload = deepcopy(PR_PLAN)
        _as_dict(_as_list(payload["groups"])[0])["commits"] = ["HEAD~1"]
        result = load(payload, PrPlan, strict=True)
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups[1].commits[1] must be a hex SHA (7-40 hex chars); "
            + "got 'HEAD~1'",
        )

    def test_two_groups_claiming_one_branch_are_rejected(self) -> None:
        """Two pull requests pushing the same ref would race each other."""
        group = deepcopy(_as_dict(_as_list(PR_PLAN["groups"])[0]))
        result = load(
            {"shape": "orthogonal_flat", "groups": [group, deepcopy(group)]},
            PrPlan,
            strict=True,
        )
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups must be branch-distinct: 'claude/pypi' is claimed by two "
            + "groups -- the two pull requests would race the same ref",
        )

    def test_single_shape_with_two_groups_is_rejected(self) -> None:
        group = deepcopy(_as_dict(_as_list(PR_PLAN["groups"])[0]))
        result = load(
            {"shape": "single", "groups": [group, dict(group, branch="claude/other")]},
            PrPlan,
            strict=True,
        )
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups must be exactly one group for the single shape, not 2",
        )

    def test_orthogonal_flat_group_off_main_is_rejected(self) -> None:
        """Orthogonal PRs are independent only while every one of them branches
        from main; a group based elsewhere is a stack in disguise."""
        group = dict(deepcopy(_as_dict(_as_list(PR_PLAN["groups"])[0])), base="develop")
        result = load(
            {"shape": "orthogonal_flat", "groups": [group]}, PrPlan, strict=True
        )
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups[1].base must be main for orthogonal_flat",
        )

    def test_distinct_branches_off_main_are_accepted(self) -> None:
        group = deepcopy(_as_dict(_as_list(PR_PLAN["groups"])[0]))
        result = load(
            {
                "shape": "orthogonal_flat",
                "groups": [group, dict(group, branch="claude/other")],
            },
            PrPlan,
            strict=True,
        )
        assert result.problems == ()
        assert result.value is not None


class TestGateReceiptShapes:
    def test_red_receipt_preserves_per_contract_modes_and_plain_dict_output(self) -> None:
        payload = deepcopy(GATE_RED)
        _as_list(payload["contracts"]).append(
            {
                "acceptance_id": "AC-4-matrix",
                "interface": "GateReceipt",
                "seam": "red-gate validate --state red",
                "expected_failure": "the contract matrix assertion fails",
                "mode": "contract-matrix",
                "contract_source": "approved",
            }
        )
        _as_list(payload["cases"]).append(
            {
                "id": "AC-4-matrix",
                "acceptance_ids": ["AC-4-matrix"],
                "curd": "gate-receipt-schema",
                "seam": "red-gate validate --state red",
                "argv": ["python", "-m", "pytest", "tests/test_outer.py", "-k", "matrix"],
                "cwd": ".",
                "kind": "contract",
                "origin": "generated",
                "expected_witness": ["assertion failed: contract matrix"],
                "observed_exit_code": 1,
                "observed_witness": "assertion failed: contract matrix",
            }
        )

        result = load(payload, GateReceipt, strict=True)

        assert result.problems == ()
        assert result.value is not None
        assert [contract.mode for contract in result.value.contracts] == [
            GateMode.TRACER,
            GateMode.CONTRACT_MATRIX,
        ]
        assert not hasattr(result.value, "mode")
        assert result.value.to_dict() == payload

    def test_not_applicable_receipt_is_a_closed_shape(self) -> None:
        result = load(deepcopy(GATE_NOT_APPLICABLE), GateReceipt, strict=True)

        assert result.problems == ()
        assert result.value is not None
        assert result.value.disposition is GateDisposition.NOT_APPLICABLE
        assert result.value.not_applicable_reason == "appearance-only change"
        assert result.value.contracts == []
        assert result.value.baseline_checks == []
        assert result.value.cases == []
        assert result.value.protected_files == []
        assert result.value.guard_receipt_refs == []

    @pytest.mark.parametrize(
        ("field_name", "replacement"),
        [
            ("guard_receipt_refs", ["prior-receipt"]),
            ("contracts", [deepcopy(_as_list(GATE_RED["contracts"])[0])]),
            ("baseline_checks", [deepcopy(_as_list(GATE_RED["baseline_checks"])[0])]),
            ("cases", [deepcopy(_as_list(GATE_RED["cases"])[0])]),
            ("protected_files", [deepcopy(_as_list(GATE_RED["protected_files"])[0])]),
            ("not_applicable_reason", ""),
        ],
    )
    def test_not_applicable_rejects_open_red_evidence(
        self, field_name: str, replacement: object
    ) -> None:
        payload = deepcopy(GATE_NOT_APPLICABLE)
        payload[field_name] = replacement

        result = load(payload, GateReceipt, strict=True)

        assert result.value is None
        assert any(field_name in problem for problem in result.problems)

    @pytest.mark.parametrize(
        ("field_name", "replacement"),
        [
            ("phase_token_ref", ".cheese/cut/work.phase.json"),
            ("phase_token_sha256", GATE_DIGEST),
        ],
    )
    def test_phase_token_ref_and_digest_must_travel_together(
        self, field_name: str, replacement: str
    ) -> None:
        payload = deepcopy(GATE_RED)
        payload[field_name] = replacement

        result = load(payload, GateReceipt, strict=True)

        assert result.value is None
        assert any("must be provided together" in problem for problem in result.problems)


    @pytest.mark.parametrize(
        ("field_name", "expected_problem"),
        [
            ("contracts", "GateReceipt.contracts must be a non-empty list for RED"),
            (
                "baseline_checks",
                "GateReceipt.baseline_checks must be a non-empty list for RED",
            ),
            ("cases", "GateReceipt.cases must be a non-empty list for RED"),
            (
                "protected_files",
                "GateReceipt.protected_files must be a non-empty list for RED",
            ),
        ],
    )
    def test_red_receipt_requires_each_evidence_collection(
        self, field_name: str, expected_problem: str
    ) -> None:
        payload = deepcopy(GATE_RED)
        payload[field_name] = []

        result = load(payload, GateReceipt, strict=True)

        assert result.value is None
        assert result.problems == (expected_problem,)

    @pytest.mark.parametrize(
        ("mutation", "expected_problem"),
        [
            (
                "schema_version",
                "GateReceipt.schema_version must be an integer, not bool",
            ),
            ("work_id", "GateReceipt.work_id must be a string, not int"),
            (
                "baseline_argv",
                "GateReceipt.baseline_checks[1].argv must be a list, not str",
            ),
            (
                "guard_refs",
                "GateReceipt.guard_receipt_refs must be a list, not tuple",
            ),
            (
                "case_cwd",
                "GateReceipt.cases[1].cwd must be a project-relative path",
            ),
            (
                "protected_digest",
                "GateReceipt.protected_files[1].sha256 must be a 64-character "
                + "hexadecimal digest",
            ),
            (
                "receipt_mode",
                "GateReceipt.mode is not supported; mode belongs to each TestContract",
            ),
        ],
    )
    def test_strict_loading_rejects_unsafe_shapes_without_coercion(
        self, mutation: str, expected_problem: str
    ) -> None:
        payload = deepcopy(GATE_RED)
        if mutation == "schema_version":
            payload["schema_version"] = True
        elif mutation == "work_id":
            payload["work_id"] = 7
        elif mutation == "baseline_argv":
            _as_dict(_as_list(payload["baseline_checks"])[0])["argv"] = "python -m pytest"
        elif mutation == "guard_refs":
            payload["guard_receipt_refs"] = ("prior-receipt",)
        elif mutation == "case_cwd":
            _as_dict(_as_list(payload["cases"])[0])["cwd"] = "../outside"
        elif mutation == "receipt_mode":
            payload["mode"] = "tracer"
        else:
            _as_dict(_as_list(payload["protected_files"])[0])["sha256"] = "not-a-digest"

        result = load(payload, GateReceipt, strict=True)

        assert result.value is None
        assert expected_problem in result.problems


class TestGateReceiptTypes:
    def test_nested_types_and_enum_values_are_public(self) -> None:
        contract = GateTestContract(
            acceptance_id="AC-4",
            interface="GateReceipt",
            seam="red-gate validate --state red",
            expected_failure="outer witness",
            mode=GateMode.TRACER,
            contract_source="approved",
        )
        baseline = BaselineCheck(
            id="baseline",
            argv=["python", "-m", "pytest"],
            cwd=".",
            observed_exit_code=0,
        )
        case = RedCase(
            id="case",
            acceptance_ids=["AC-4"],
            curd=None,
            seam="red-gate validate --state red",
            argv=["python", "-m", "pytest"],
            cwd=".",
            kind=RedKind.BEHAVIOR,
            origin=EvidenceOrigin.ADOPTED,
            expected_witness=["outer witness"],
            observed_exit_code=1,
            observed_witness="outer witness",
        )
        protected = ProtectedFile(path="tests/test_outer.py", sha256=GATE_DIGEST)

        assert contract.mode is GateMode.TRACER
        assert baseline.observed_exit_code == 0
        assert case.origin is EvidenceOrigin.ADOPTED
        assert protected.sha256 == GATE_DIGEST
        assert GateProducer.PRESS.value == "press"


class TestReadinessParity:
    """The port must agree with shared/scripts/gates.py on all 32 inputs."""

    def test_verdicts_match_the_original_on_every_combination(self) -> None:
        original = cast(_GatesOriginal, cast(object, _original("gates")))
        keys = (
            "hard_floor_met",
            "has_open_level_1_or_2",
            "has_open_level_3",
            "has_open_level_4_or_5",
            "any_spinning",
        )
        combinations = list(itertools.product((True, False), repeat=len(keys)))
        assert len(combinations) == 32
        for combination in combinations:
            inputs = dict(zip(keys, combination, strict=True))
            assert gates.classify_readiness(**inputs).value == (
                original.classify_readiness(**inputs).value
            ), inputs

    def test_readiness_values_match_the_original_enum(self) -> None:
        original = cast(_GatesOriginal, cast(object, _original("gates")))
        assert [member.value for member in gates.Readiness] == [
            member.value for member in original.Readiness
        ]


@final
class TestParseMappingParity:
    ORIGINAL_ERROR_CASES = [
        pytest.param("[1, 2]", id="json-list-root"),
        pytest.param("- a\n- b\n", id="yaml-list-root"),
        pytest.param("{oops", id="invalid-both-ways"),
    ]

    def test_valid_json_parses_like_the_original(self) -> None:
        original = cast(_ManifestIoOriginal, cast(object, _original("manifest_io")))
        text = '{"slug": "pypi", "curds": []}'
        assert io.parse_mapping(text) == original.parse_mapping(text)

    def test_invalid_json_falls_back_to_yaml_like_the_original(self) -> None:
        original = cast(_ManifestIoOriginal, cast(object, _original("manifest_io")))
        text = "slug: pypi\ncurds: []\n"
        try:
            expected = original.parse_mapping(text)
        except original.ManifestLoadError as exc:  # PyYAML absent
            with pytest.raises(io.ManifestLoadError) as raised:
                _ = io.parse_mapping(text)
            assert str(raised.value) == str(exc)
        else:
            assert io.parse_mapping(text) == expected

    @pytest.mark.parametrize("text", ORIGINAL_ERROR_CASES)
    def test_rejected_input_raises_the_same_message(self, text: str) -> None:
        original = cast(_ManifestIoOriginal, cast(object, _original("manifest_io")))
        with pytest.raises(original.ManifestLoadError) as expected:
            _ = original.parse_mapping(text)
        with pytest.raises(io.ManifestLoadError) as raised:
            _ = io.parse_mapping(text)
        assert str(raised.value) == str(expected.value)

    def test_source_label_appears_in_the_message(self) -> None:
        with pytest.raises(io.ManifestLoadError) as raised:
            _ = io.parse_mapping("[1]", "manifest.yaml")
        assert str(raised.value) == "manifest.yaml: expected a mapping at document root"


class TestPublicSurface:
    def test_new_names_are_exported(self) -> None:
        import easy_cheese_schemas

        for name in (
            "BaselineCheck",
            "EvidenceOrigin",
            "GateDisposition",
            "GateMode",
            "GateProducer",
            "GateReceipt",
            "ProtectedFile",
            "RedCase",
            "RedKind",
            "TestContract",
            "CurdBlock",
            "CurdRecord",
            "DecomposedCurd",
            "Decomposition",
            "ManifestLoadError",
            "PrPlan",
            "Readiness",
            "RunManifest",
            "STAMP_KEY",
            "WiringRow",
            "classify_readiness",
            "classify_stamp",
            "parse_mapping",
            "AcceptedArtifact",
            "HandoffPointer",
            "IngressKind",
            "NormalizationAction",
            "NormalizationActionKind",
            "NormalizationReceipt",
            "PublishedArtifact",
        ):
            assert name in easy_cheese_schemas.__all__
            assert getattr(easy_cheese_schemas, name) is not None

    def test_the_original_compat_exports_are_kept(self) -> None:
        import easy_cheese_schemas

        for name in (
            "MIN_READABLE",
            "SCHEMA_VERSION",
            "Loaded",
            "Provenance",
            "__version__",
            "load",
        ):
            assert name in easy_cheese_schemas.__all__


class TestLockedDependencyProvenance:
    """The source suite exercises the runtime versions locked for bundles."""

    def test_attrs_stack_does_not_resolve_from_a_repo_vendor_tree(self) -> None:
        import attr
        import attrs
        import cattrs

        for module in (attr, attrs, cattrs):
            assert module.__file__ is not None
            assert not module.__file__.startswith(str(REPO_ROOT / "vendor"))

    def test_attrs_matches_the_locked_version(self) -> None:
        import attrs

        assert _runtime_pins()["attrs"] == attrs.__version__
