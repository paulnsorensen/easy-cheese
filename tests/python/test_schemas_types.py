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
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from easy_cheese_schemas import gates, io, load
from easy_cheese_schemas.curd import MAX_WAVE_SIZE, MIN_CURD_SURFACE, CurdBlock
from easy_cheese_schemas.decomposition import Decomposition
from easy_cheese_schemas.manifest import Phase, RunManifest
from easy_cheese_schemas.pr_plan import PrPlan

REPO_ROOT = Path(__file__).resolve().parents[2]


def _original(name: str) -> ModuleType:
    """Import shared/scripts/<name>.py under a private name, so the port is
    compared against the running implementation rather than a copy of it."""
    path = REPO_ROOT / "shared" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_original_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REVIEW_CONTEXT: dict[str, Any] = {
    "base_commit": "a" * 40,
    "reviewed_tree_oid": "b" * 40,
    "diff_hash": "sha256:" + "c" * 64,
    "scope": ["src/easy_cheese_schemas/"],
}

AGENT_RESOLUTION: dict[str, Any] = {
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

CURD_RECORD: dict[str, Any] = {
    "id": 1,
    "behavior": "adds the attrs types for the schemas package",
    "acceptance_criterion": "tests/python/test_schemas_types.py passes",
    "files": ["src/easy_cheese_schemas/manifest.py"],
    "test_target": "pytest tests/python/test_schemas_types.py",
    "status": "pending",
    "retry_count": 0,
}

WIRING_ROW: dict[str, Any] = {
    "id": "W1",
    "type": "barrel_export",
    "file": "src/easy_cheese_schemas/__init__.py",
    "depends_on": [],
    "status": "pending",
}

RUN_MANIFEST: dict[str, Any] = {
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

DECOMPOSITION: dict[str, Any] = {"curds": [CURD_RECORD], "wiring": [WIRING_ROW]}

CURD_BLOCK: dict[str, Any] = {
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

PR_PLAN: dict[str, Any] = {
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


def _without(payload: dict[str, Any], key: str) -> dict[str, Any]:
    stripped = deepcopy(payload)
    del stripped[key]
    return stripped


def _curd(slug: str, path: str) -> dict[str, Any]:
    entry = deepcopy(CURD_BLOCK["curds"][0])
    entry["slug"] = slug
    entry["files"] = [path]
    return entry


ARTIFACTS = [
    pytest.param(RUN_MANIFEST, RunManifest, "phase", id="run-manifest"),
    pytest.param(DECOMPOSITION, Decomposition, "curds", id="decomposition"),
    pytest.param(CURD_BLOCK, CurdBlock, "decomposer", id="curd-block"),
    pytest.param(PR_PLAN, PrPlan, "groups", id="pr-plan"),
]


class TestArtifactRoundTrip:
    @pytest.mark.parametrize(("payload", "cls", "required_key"), ARTIFACTS)
    def test_valid_payload_structures_without_problems(
        self, payload: dict[str, Any], cls: type, required_key: str
    ) -> None:
        result = load(deepcopy(payload), cls, strict=True)
        assert result.problems == []
        assert isinstance(result.value, cls)

    @pytest.mark.parametrize(("payload", "cls", "required_key"), ARTIFACTS)
    def test_missing_required_key_is_named_and_yields_no_value(
        self, payload: dict[str, Any], cls: type, required_key: str
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
        assert any("phase" in problem for problem in result.problems)

    def test_review_context_rejects_a_short_tree_oid(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["current_review"] = dict(REVIEW_CONTEXT, reviewed_tree_oid="abc123")
        result = load(payload, RunManifest, strict=True)
        assert result.value is None
        assert any("reviewed_tree_oid" in problem for problem in result.problems)

    def test_review_context_accepts_the_documented_shape(self) -> None:
        payload = deepcopy(RUN_MANIFEST)
        payload["current_review"] = deepcopy(REVIEW_CONTEXT)
        result = load(payload, RunManifest, strict=True)
        assert result.problems == []
        assert result.value is not None
        assert result.value.current_review is not None
        assert result.value.current_review.scope == ["src/easy_cheese_schemas/"]


class TestCurdBlockInvariants:
    def test_wave_over_the_cap_is_rejected(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        slugs = [f"curd-{index}" for index in range(MAX_WAVE_SIZE + 1)]
        payload["curds"] = [_curd(slug, f"src/{slug}.py") for slug in slugs]
        payload["waves"] = [slugs]
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert any(
            f"exceeding the max of {MAX_WAVE_SIZE}" in problem for problem in result.problems
        )

    def test_wave_at_the_cap_is_accepted(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        slugs = [f"curd-{index}" for index in range(MAX_WAVE_SIZE)]
        payload["curds"] = [_curd(slug, f"src/{slug}.py") for slug in slugs]
        payload["waves"] = [slugs]
        assert load(payload, CurdBlock, strict=True).problems == []

    def test_wave_referencing_an_unknown_slug_is_rejected(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        payload["waves"] = [["schema-types", "no-such-curd"]]
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert any("no-such-curd" in problem for problem in result.problems)

    def test_curd_below_the_surface_floor_is_a_merge_candidate(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        payload["curds"][0]["est_edit_lines"] = MIN_CURD_SURFACE - 1
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert any("MERGE CANDIDATE" in problem for problem in result.problems)

    def test_curd_at_the_surface_floor_is_accepted(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        payload["curds"][0]["est_edit_lines"] = MIN_CURD_SURFACE
        assert load(payload, CurdBlock, strict=True).problems == []

    def test_curds_sharing_a_file_are_rejected(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        shared = "src/easy_cheese_schemas/manifest.py"
        payload["curds"] = [_curd("first", shared), _curd("second", shared)]
        payload["waves"] = [["first", "second"]]
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None
        assert any("pairwise disjoint" in problem for problem in result.problems)

    def test_unknown_decomposer_source_is_rejected(self) -> None:
        payload = deepcopy(CURD_BLOCK)
        payload["decomposer"]["source"] = "vibes"
        result = load(payload, CurdBlock, strict=True)
        assert result.value is None


class TestDecompositionInvariants:
    def test_parallel_decomposition_rejects_overlapping_curd_files(self) -> None:
        shared = dict(CURD_RECORD, id=2, files=CURD_RECORD["files"])
        result = load(
            {"curds": [deepcopy(CURD_RECORD), shared], "wiring": []},
            Decomposition,
            strict=True,
        )
        assert result.value is None
        assert any("file-disjoint" in problem for problem in result.problems)

    def test_empty_curds_is_rejected(self) -> None:
        result = load({"curds": [], "wiring": []}, Decomposition, strict=True)
        assert result.value is None
        assert any("curds" in problem for problem in result.problems)


class TestPrPlanInvariants:
    def test_branch_with_a_newline_is_rejected(self) -> None:
        payload = deepcopy(PR_PLAN)
        payload["groups"][0]["branch"] = "claude/pypi\nrm -rf /"
        result = load(payload, PrPlan, strict=True)
        assert result.value is None
        assert any("branch" in problem for problem in result.problems)

    def test_commit_that_is_not_a_hex_sha_is_rejected(self) -> None:
        payload = deepcopy(PR_PLAN)
        payload["groups"][0]["commits"] = ["HEAD~1"]
        result = load(payload, PrPlan, strict=True)
        assert result.value is None
        assert any("commits" in problem for problem in result.problems)


class TestReadinessParity:
    """The port must agree with shared/scripts/gates.py on all 32 inputs."""

    def test_verdicts_match_the_original_on_every_combination(self) -> None:
        original = _original("gates")
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
        original = _original("gates")
        assert [member.value for member in gates.Readiness] == [
            member.value for member in original.Readiness
        ]


class TestParseMappingParity:
    ORIGINAL_ERROR_CASES = [
        pytest.param("[1, 2]", id="json-list-root"),
        pytest.param("- a\n- b\n", id="yaml-list-root"),
        pytest.param("{oops", id="invalid-both-ways"),
    ]

    def test_valid_json_parses_like_the_original(self) -> None:
        original = _original("manifest_io")
        text = '{"slug": "pypi", "curds": []}'
        assert io.parse_mapping(text) == original.parse_mapping(text)

    def test_invalid_json_falls_back_to_yaml_like_the_original(self) -> None:
        original = _original("manifest_io")
        text = "slug: pypi\ncurds: []\n"
        try:
            expected = original.parse_mapping(text)
        except original.ManifestLoadError as exc:  # PyYAML absent
            with pytest.raises(io.ManifestLoadError) as raised:
                io.parse_mapping(text)
            assert str(raised.value) == str(exc)
        else:
            assert io.parse_mapping(text) == expected

    @pytest.mark.parametrize("text", ORIGINAL_ERROR_CASES)
    def test_rejected_input_raises_the_same_message(self, text: str) -> None:
        original = _original("manifest_io")
        with pytest.raises(original.ManifestLoadError) as expected:
            original.parse_mapping(text)
        with pytest.raises(io.ManifestLoadError) as raised:
            io.parse_mapping(text)
        assert str(raised.value) == str(expected.value)

    def test_source_label_appears_in_the_message(self) -> None:
        with pytest.raises(io.ManifestLoadError) as raised:
            io.parse_mapping("[1]", "manifest.yaml")
        assert str(raised.value) == "manifest.yaml: expected a mapping at document root"


class TestPublicSurface:
    def test_new_names_are_exported(self) -> None:
        import easy_cheese_schemas

        for name in (
            "CurdBlock",
            "CurdRecord",
            "Decomposition",
            "ManifestLoadError",
            "PrPlan",
            "Readiness",
            "RunManifest",
            "WiringRow",
            "classify_readiness",
            "parse_mapping",
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
