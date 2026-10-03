"""Tests for the easy-cheese-schemas v0.1 typed surface.

The types mirror contracts that today live in hand-rolled validators
(src/easy_cheese/shared/fanout/*, src/easy_cheese/shared/*). Where a contract has an executable original
-- `gates.classify_readiness` and `io.parse_mapping` -- the test imports that
original by path and asserts the port agrees on every input, so drift is caught
mechanically instead of by a copied expectation table.
"""

from __future__ import annotations

import importlib.util
import itertools
import re
import sys
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from enum import Enum
from types import ModuleType
from typing import Protocol, cast, final

import attrs
import pytest

from easy_cheese_schemas import contracts as wc
from easy_cheese_schemas import gates, io, load
from easy_cheese_schemas.manifest import Phase, RunManifest
from easy_cheese_schemas.pr_plan import PrPlan

REPO_ROOT = Path(__file__).resolve().parents[2]


def _runtime_pins() -> dict[str, str]:
    text = (REPO_ROOT / "requirements" / "runtime.txt").read_text()
    return dict(re.findall(r"^([A-Za-z0-9_-]+)==([^ ]+)", text, re.MULTILINE))


def _original(name: str) -> ModuleType:
    """Import src/easy_cheese/shared/<name>.py under a private name, so the port is
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

PR_PLAN: dict[str, object] = {
    "contract_version": {
        "schema_uri": "https://schemas.easy-cheese.dev/pr-plan",
        "major": "1",
        "minor": "0",
    },
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



def _without(payload: dict[str, object], key: str) -> dict[str, object]:
    """Drop `key`; a dotted key reaches into a nested mapping."""
    stripped = deepcopy(payload)
    *parents, leaf = key.split(".")
    target = stripped
    for parent in parents:
        target = _as_dict(target[parent])
    del target[leaf]
    return stripped


ARTIFACTS = [
    pytest.param(RUN_MANIFEST, RunManifest, "phase", id="run-manifest"),
    pytest.param(
        RUN_MANIFEST,
        RunManifest,
        "agent_resolution.resolved",
        id="run-manifest-nested",
    ),
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
            "RunManifest.phase must be valid: unknown value 'cheese_complete' "
            + "(allowed: gate_approved, seed_complete, curds_complete, "
            + "merge_complete, wiring_complete, final_merge_complete, "
            + "post_review_complete, pr_publish_complete)",
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


class TestPrPlanInvariants:
    def test_branch_with_a_newline_is_rejected(self) -> None:
        payload = deepcopy(PR_PLAN)
        _as_dict(_as_list(payload["groups"])[0])["branch"] = "claude/pypi\nrm -rf /"
        result = load(payload, PrPlan, strict=True)
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups[1].branch contains characters unsafe for a git ref",
        )

    @pytest.mark.parametrize(
        "ref",
        [
            "/topic",
            "topic/",
            "a//b",
            "a..b",
            "x.lock",
            "a.lock/b",
            "a.b.lock/c",
            ".topic",
            "a/.hidden",
            "topic.",
            "-flag",
        ],
    )
    def test_branch_forms_git_check_ref_format_rejects_are_rejected(
        self, ref: str
    ) -> None:
        payload = deepcopy(PR_PLAN)
        _as_dict(_as_list(payload["groups"])[0])["branch"] = ref
        result = load(payload, PrPlan, strict=True)
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups[1].branch contains characters unsafe for a git ref",
        )

    def test_base_form_git_check_ref_format_reject_is_rejected(self) -> None:
        payload = deepcopy(PR_PLAN)
        _as_dict(_as_list(payload["groups"])[0])["base"] = "topic.lock"
        result = load(payload, PrPlan, strict=True)
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups[1].base contains characters unsafe for a git ref",
        )

    @pytest.mark.parametrize("ref", ["feat/x.y", "release-1.2", "a/b/c"])
    def test_branch_forms_git_check_ref_format_accepts_are_accepted(
        self, ref: str
    ) -> None:
        payload = deepcopy(PR_PLAN)
        _as_dict(_as_list(payload["groups"])[0])["branch"] = ref
        result = load(payload, PrPlan, strict=True)
        assert result.value is not None

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
            {
                "contract_version": PR_PLAN["contract_version"],
                "shape": "orthogonal_flat",
                "groups": [group, deepcopy(group)],
            },
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
            {
                "contract_version": PR_PLAN["contract_version"],
                "shape": "single",
                "groups": [group, dict(group, branch="claude/other")],
            },
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
            {
                "contract_version": PR_PLAN["contract_version"],
                "shape": "orthogonal_flat",
                "groups": [group],
            },
            PrPlan,
            strict=True,
        )
        assert result.value is None
        assert result.problems == (
            "PrPlan.groups[1].base must be main for orthogonal_flat",
        )

    def test_distinct_branches_off_main_are_accepted(self) -> None:
        group = deepcopy(_as_dict(_as_list(PR_PLAN["groups"])[0]))
        result = load(
            {
                "contract_version": PR_PLAN["contract_version"],
                "shape": "orthogonal_flat",
                "groups": [group, dict(group, branch="claude/other")],
            },
            PrPlan,
            strict=True,
        )
        assert result.problems == ()
        assert result.value is not None


class TestRunManifestPrPlanLayout:
    """AC-6: a stored plate_layout must equal the layout the plan shape projects to."""

    def test_layout_that_disagrees_with_plan_shape_is_rejected(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["plate_layout"] = "single"
        payload["pr_plan"] = dict(deepcopy(PR_PLAN), shape="stacked_linear")
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert result.problems == (
            "RunManifest.pr_plan must be valid: pr_plan: plate_layout_for(shape "
            + "'stacked_linear') is 'stacked' but plate_layout is 'single'",
        )

    def test_layout_matching_plan_shape_is_accepted(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["plate_layout"] = "single"
        payload["pr_plan"] = deepcopy(PR_PLAN)
        assert load(payload, RunManifest, strict=True).problems == ()


class TestReadinessParity:
    """The port must agree with src/easy_cheese/shared/gates.py on all 32 inputs."""

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
            "CurdRecord",
            "DecomposedCurd",
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


class TestLandingShapeMirrorsPrShape:
    """LandingShape duplicates PrShape on purpose: contracts.py is exec'd
    standalone and cannot import the package. Pin the two value lists."""

    def test_landing_shape_values_match_pr_shape(self) -> None:
        from easy_cheese_schemas.contracts import LandingShape
        from easy_cheese_schemas.pr_plan import PrShape

        assert LandingShape is not PrShape
        assert [m.value for m in LandingShape] == [m.value for m in PrShape]
        assert [m.name for m in LandingShape] == [m.name for m in PrShape]


_WHEYPOINT_DIGEST = "sha256:" + "0" * 64


def _wheypoint_record(
    *,
    questions: tuple[wc.ProtectedEntry, ...] = (),
    dossier: tuple[wc.DecisionFork, ...] = (),
    notes: str | None = None,
    edges: tuple[wc.WorkEdge, ...] = (),
) -> wc.WheypointRecord:
    return wc.WheypointRecord(
        schema_version=4,
        work_id="parent",
        slug="parent",
        title="Parent",
        created="2026-09-27",
        project_key="project",
        revision_id="rev-0001",
        revision_number=1,
        revision_digest=_WHEYPOINT_DIGEST,
        orientation="Continue the parent.",
        working_context=[],
        next_action=wc.NextAction(move=wc.NextMove.COOK, orientation="Cook it."),
        decisions=[],
        questions=list(questions),
        blockers=[],
        artifact_links=[],
        decision_dossier=list(dossier),
        notes=notes,
        edges=edges,
    )


def _gating_question(state: wc.EntryState) -> wc.ProtectedEntry:
    return wc.ProtectedEntry(
        entry_id="q-1",
        kind=wc.EntryKind.QUESTION,
        summary="Which store owns the edge?",
        state=state,
        blocks_continuation=True,
        rationale=None if state is wc.EntryState.ACTIVE else "Moved to the child.",
        successor="wheypoint:project/child#q-1"
        if state is wc.EntryState.FORKED
        else None,
    )


_EDGE_KEY = wc.WorkEdgeKey(to="repo:docs/spec.md", kind=wc.EdgeKind.INFORMS)
_INTENT = wc.CheckpointIntent(work_id="parent")
_DELTA = wc.WheypointDelta(work_id="parent", expected_revision_id="rev-0001")


def _fork_transition() -> wc.EntryTransition:
    return wc.EntryTransition(
        entry_id="q-1",
        action=wc.TransitionAction.FORK,
        rationale="Moved to the child.",
        successor="wheypoint:project/child#q-1",
    )


def _entry(
    *,
    state: wc.EntryState = wc.EntryState.ACTIVE,
    rationale: str | None = None,
    origin: str | None = None,
    successor: str | None = None,
    copies: tuple[str, ...] = (),
) -> wc.ProtectedEntry:
    return wc.ProtectedEntry(
        entry_id="d-1",
        kind=wc.EntryKind.DECISION,
        summary="s",
        state=state,
        blocks_continuation=False,
        rationale=rationale,
        origin=origin,
        successor=successor,
        copies=copies,
    )


def _open_fork() -> wc.DecisionFork:
    option = wc.DossierOption(option="child", evidence=["spec F-2"], breaks="none")
    return wc.DecisionFork(fork="Which store owns the edge?", options=[option])


def _notes_holders(notes: str) -> tuple[object, ...]:
    return (
        _wheypoint_record(notes=notes),
        wc.WheypointDelta(
            work_id="parent", expected_revision_id="rev-0001", notes=notes
        ),
        wc.CheckpointIntent(work_id="parent", notes=notes),
    )


# Every since-4 reference field, keyed by case id: (field name, builder).
_REF_HOLDERS: dict[str, tuple[str, Callable[[str], object]]] = {
    "edge": ("to", lambda ref: wc.WorkEdge(to=ref, kind=wc.EdgeKind.INFORMS)),
    "edge-key": ("to", lambda ref: wc.WorkEdgeKey(to=ref, kind=wc.EdgeKind.INFORMS)),
    "artifact": ("ref", lambda ref: wc.ArtifactLink(path="p.md", ref=ref)),
    "origin": ("origin", lambda ref: _entry(origin=ref)),
    "copies": ("copies", lambda ref: _entry(copies=(ref,))),
    "entry": (
        "successor",
        lambda ref: _entry(
            state=wc.EntryState.FORKED, rationale="Moved.", successor=ref
        ),
    ),
    "transition": (
        "successor",
        lambda ref: wc.EntryTransition(
            entry_id="q-1",
            action=wc.TransitionAction.FORK,
            rationale="Moved.",
            successor=ref,
        ),
    ),
}


class TestWheypointSchemaFour:
    def test_ac7_forked_gating_question_derives_ok(self) -> None:
        record = _wheypoint_record(
            questions=(_gating_question(wc.EntryState.FORKED),)
        )

        assert record.gating_entry_ids == ()
        assert record.status is wc.WheypointStatus.OK

    def test_ac7_same_question_active_still_gates(self) -> None:
        record = _wheypoint_record(
            questions=(_gating_question(wc.EntryState.ACTIVE),),
            dossier=(_open_fork(),),
        )

        assert record.gating_entry_ids == ("q-1",)
        assert record.status is wc.WheypointStatus.GATED

    def test_ac7_fork_transition_lands_in_forked_state(self) -> None:
        transition = wc.EntryTransition(
            entry_id="q-1",
            action=wc.TransitionAction.FORK,
            rationale="Moved.",
            successor="wheypoint:project/child#q-1",
        )

        assert transition.resulting_state is wc.EntryState.FORKED

    def test_intent_refuses_a_fork_transition(self) -> None:
        with pytest.raises(ValueError, match="host derives fork transitions"):
            _ = wc.CheckpointIntent(work_id="parent", transitions=[_fork_transition()])

    def test_delta_accepts_a_host_fork_transition(self) -> None:
        delta = wc.WheypointDelta(
            work_id="parent",
            expected_revision_id="rev-0001",
            transitions=[_fork_transition()],
        )

        assert delta.transitions == [_fork_transition()]

    def test_intent_refuses_a_forked_from_add_edge(self) -> None:
        with pytest.raises(ValueError, match="host derives fork edges"):
            _ = wc.CheckpointIntent(
                work_id="parent",
                add_edges=[
                    wc.WorkEdge(to="wheypoint:project/child", kind=wc.EdgeKind.FORKED_FROM)
                ],
            )

    def test_intent_refuses_a_forked_to_remove_edge(self) -> None:
        with pytest.raises(ValueError, match="host derives fork edges"):
            _ = wc.CheckpointIntent(
                work_id="parent",
                remove_edges=[
                    wc.WorkEdgeKey(to="wheypoint:project/child", kind=wc.EdgeKind.FORKED_TO)
                ],
            )

    def test_intent_refuses_a_host_reciprocal_rationale(self) -> None:
        with pytest.raises(ValueError, match="reciprocal rationale is written by the host"):
            _ = wc.CheckpointIntent(
                work_id="parent",
                add_edges=[
                    wc.WorkEdge(
                        to="wheypoint:project/child",
                        kind=wc.EdgeKind.INFORMS,
                        rationale="reciprocal of informs from parent@rev-0001",
                    )
                ],
            )

    def test_intent_refuses_a_pinned_revision_id_on_add_edges(self) -> None:
        with pytest.raises(ValueError, match="revision_id is host-stamped"):
            _ = wc.CheckpointIntent(
                work_id="parent",
                add_edges=[
                    wc.WorkEdge(
                        to="wheypoint:project/child",
                        kind=wc.EdgeKind.INFORMS,
                        revision_id="rev-0001",
                    )
                ],
            )

    def test_fork_transition_must_name_its_successor(self) -> None:
        with pytest.raises(ValueError, match="successor must name the entry"):
            _ = wc.EntryTransition(
                entry_id="q-1", action=wc.TransitionAction.FORK, rationale="Moved."
            )

    def test_non_fork_transition_refuses_a_successor(self) -> None:
        with pytest.raises(ValueError, match="successor must be null for a resolve"):
            _ = wc.EntryTransition(
                entry_id="q-1",
                action=wc.TransitionAction.RESOLVE,
                rationale="Done.",
                successor="wheypoint:project/child#q-1",
            )

    def test_forked_entry_must_name_its_successor(self) -> None:
        with pytest.raises(ValueError, match="successor must name the entry"):
            _ = wc.ProtectedEntry(
                entry_id="q-1",
                kind=wc.EntryKind.QUESTION,
                summary="s",
                state=wc.EntryState.FORKED,
                blocks_continuation=True,
                rationale="Moved.",
            )

    def test_unforked_entry_refuses_a_successor(self) -> None:
        with pytest.raises(ValueError, match="successor must be null unless"):
            _ = wc.ProtectedEntry(
                entry_id="q-1",
                kind=wc.EntryKind.QUESTION,
                summary="s",
                state=wc.EntryState.ACTIVE,
                blocks_continuation=True,
                successor="wheypoint:project/child#q-1",
            )

    def test_ac7_forked_entry_must_say_why_it_left_active(self) -> None:
        with pytest.raises(ValueError, match="rationale"):
            _ = wc.ProtectedEntry(
                entry_id="q-1",
                kind=wc.EntryKind.QUESTION,
                summary="s",
                state=wc.EntryState.FORKED,
                blocks_continuation=True,
            )

    @pytest.mark.parametrize("index", [0, 1, 2], ids=["record", "delta", "intent"])
    def test_ac16_notes_accept_6000_characters(self, index: int) -> None:
        assert getattr(_notes_holders("n" * 6000)[index], "notes") == "n" * 6000

    @pytest.mark.parametrize("index", [0, 1, 2], ids=["record", "delta", "intent"])
    def test_ac16_notes_refuse_6001_characters(self, index: int) -> None:
        with pytest.raises(ValueError, match="notes must be at most 6000"):
            _ = _notes_holders("n" * 6001)[index]

    def test_ac16_other_text_keeps_the_2000_bound(self) -> None:
        with pytest.raises(ValueError, match="orientation must be at most 2000"):
            _ = wc.CheckpointIntent(work_id="parent", orientation="o" * 2001)

    @pytest.mark.parametrize("case", sorted(_REF_HOLDERS))
    def test_references_keep_the_2000_bound(self, case: str) -> None:
        field, build = _REF_HOLDERS[case]
        prefix = "repo:"
        _ = build(prefix + "r" * (2000 - len(prefix)))

        with pytest.raises(ValueError, match=rf"{field}.*at most 2000"):
            _ = build(prefix + "r" * (2001 - len(prefix)))

    def test_edges_refuse_a_repeated_target_and_kind(self) -> None:
        edge = wc.WorkEdge(
            to="wheypoint:project/child",
            kind=wc.EdgeKind.FORKED_TO,
            revision_id="rev-0001",
        )

        with pytest.raises(ValueError, match="edges must not repeat"):
            _ = _wheypoint_record(edges=(edge, edge))

    def test_edges_allow_one_target_under_two_kinds(self) -> None:
        edges = tuple(
            wc.WorkEdge(to="repo:docs/spec.md", kind=kind, revision_id="rev-0001")
            for kind in (wc.EdgeKind.IMPLEMENTS, wc.EdgeKind.INFORMS)
        )

        assert _wheypoint_record(edges=edges).edges == edges

    def test_work_edge_revision_is_host_stamped(self) -> None:
        edge = wc.WorkEdge(to="repo:docs/spec.md", kind=wc.EdgeKind.INFORMS)

        assert edge.revision_id is None

    @pytest.mark.parametrize(
        ("build", "message"),
        [
            (
                lambda: wc.WorkEdgeKey(to="docs/spec.md", kind=wc.EdgeKind.INFORMS),
                "to must be an absolute URI",
            ),
            (
                lambda: wc.WorkEdge(to="docs/spec.md", kind=wc.EdgeKind.INFORMS),
                "to must be an absolute URI",
            ),
            (
                lambda: wc.ArtifactLink(path="docs/spec.md", ref="docs/spec.md"),
                "ref must be an absolute URI",
            ),
            (lambda: _entry(copies=("child",)), r"copies\[1\] must be an absolute URI"),
            (lambda: _entry(origin="parent#d-1"), "origin must be an absolute URI"),
            (
                lambda: _entry(
                    state=wc.EntryState.FORKED, rationale="Moved.", successor="child"
                ),
                "successor must be an absolute URI",
            ),
            (
                lambda: wc.EntryTransition(
                    entry_id="d-1",
                    action=wc.TransitionAction.FORK,
                    rationale="Moved.",
                    successor="child",
                ),
                "successor must be an absolute URI",
            ),
        ],
        ids=[
            "edge-key-to",
            "edge-to",
            "link-ref",
            "copies",
            "origin",
            "successor",
            "transition-successor",
        ],
    )
    def test_refs_must_be_absolute_uris(
        self, build: Callable[[], object], message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            _ = build()

    @pytest.mark.parametrize(
        ("name", "value", "message"),
        [
            ("add_edges", (), "add_edges must be a non-empty list"),
            ("remove_edges", (), "remove_edges must be a non-empty list"),
            (
                "remove_dossier_forks",
                (),
                "remove_dossier_forks must be a non-empty list",
            ),
            ("remove_dossier_forks", ("f", "f"), "must not contain duplicate 'f'"),
            (
                "remove_dossier_forks",
                ("f" * 2001,),
                r"remove_dossier_forks\[1\] must be at most 2000",
            ),
            ("remove_edges", (_EDGE_KEY, _EDGE_KEY), "remove_edges must not repeat"),
        ],
        ids=[
            "add-edges-empty",
            "remove-edges-empty",
            "forks-empty",
            "forks-duplicate",
            "forks-over-bound",
            "remove-edges-duplicate",
        ],
    )
    def test_intent_refuses_a_bad_edge_or_fork_request(
        self, name: str, value: tuple[object, ...], message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            _ = attrs.evolve(_INTENT, **{name: value})

    @pytest.mark.parametrize(
        ("name", "value", "message"),
        [
            ("remove_dossier_forks", ("f", "f"), "must not contain duplicate 'f'"),
            (
                "remove_dossier_forks",
                ("f" * 2001,),
                r"remove_dossier_forks\[1\] must be at most 2000",
            ),
            ("remove_edges", (_EDGE_KEY, _EDGE_KEY), "remove_edges must not repeat"),
        ],
        ids=["forks-duplicate", "forks-over-bound", "remove-edges-duplicate"],
    )
    def test_delta_refuses_a_bad_edge_or_fork_request(
        self, name: str, value: tuple[object, ...], message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            _ = attrs.evolve(_DELTA, **{name: value})

    @pytest.mark.parametrize(
        "name", ["add_edges", "remove_edges", "remove_dossier_forks"]
    )
    def test_delta_accepts_an_explicit_empty_collection(self, name: str) -> None:
        delta = attrs.evolve(_DELTA, **{name: ()})

        assert getattr(delta, name) == ()

    def test_every_schema_four_field_is_marked_and_defaulted(self) -> None:
        added = {
            wc.WheypointRecord: ("edges",),
            wc.ProtectedEntry: ("origin", "successor", "copies"),
            wc.EntryTransition: ("successor",),
            wc.ArtifactLink: ("ref",),
            wc.WheypointDelta: ("add_edges", "remove_edges", "remove_dossier_forks"),
            wc.CheckpointIntent: ("add_edges", "remove_edges", "remove_dossier_forks"),
            wc.WheypointRevision: ("applied_edges", "removed_edges"),
        }
        for cls, names in added.items():
            fields = attrs.fields_dict(cls)
            for name in names:
                assert fields[name].metadata == {"since": 4}, (cls, name)
                assert fields[name].default is not attrs.NOTHING, (cls, name)

    def test_work_edge_is_a_registered_contract(self) -> None:
        assert ("work-edge", wc.WorkEdge) in wc.registered_contracts()
