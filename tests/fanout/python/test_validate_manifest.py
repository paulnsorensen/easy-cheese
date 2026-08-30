"""Tests for ultracook manifest and PR-plan validators."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable, cast

import yaml
import pytest

BUNDLE = Path(__file__).resolve().parents[3] / "skills/cook/scripts/cook.pyz"


def _d(value: object) -> dict[str, object]:
    return cast(dict[str, object], value)


def _l(value: object) -> list[object]:
    return cast(list[object], value)


def _nav(container: object, key: str | int) -> object:
    if isinstance(key, str):
        return _d(container)[key]
    return _l(container)[key]


def _nav_set(container: object, key: str | int, value: object) -> None:
    if isinstance(key, str):
        _d(container)[key] = value
    else:
        _l(container)[key] = value


def _validate_run_manifest(module: ModuleType, manifest: dict[str, object]) -> list[str]:
    fn = cast(Callable[[dict[str, object]], list[str]], module.validate_run_manifest)
    return fn(manifest)


def _validate_pr_plan(module: ModuleType, plan: dict[str, object]) -> list[str]:
    fn = cast(Callable[[dict[str, object]], list[str]], module.validate_pr_plan)
    return fn(plan)


def _curds(n: int = 5) -> list[dict[str, object]]:
    return [
        {
            "id": i + 1,
            "behavior": f"Implement feature {i + 1}",
            "acceptance_criterion": f"AC {i + 1}",
            "files": [f"src/feature_{i}.ts"],
            "test_target": f"pytest src/feature_{i}.ts",
            "status": "pending",
            "retry_count": 0,
        }
        for i in range(n)
    ]


def _review_context() -> dict[str, object]:
    return {
        "base_commit": "a" * 40,
        "reviewed_tree_oid": "B" * 64,
        "diff_hash": "sha256:" + "c" * 64,
        "scope": ["src/feature.ts"],
    }

def _baseline() -> dict[str, object]:
    return {
        "captured_at": "2026-05-14T10:00:00Z",
        "gates": [
            {
                "cmd": "just check",
                "failures": [
                    {
                        "suite": "pytest",
                        "test_id": "tests/test_foo.py::test_bar",
                        "signature": "AssertionError: expected 1 got 2",
                    }
                ],
            }
        ],
    }

def _manifest() -> dict[str, object]:
    return {
        "slug": "feature-name",
        "spec_path": ".cheese/specs/feature-name.md",
        "created": "2026-05-14T10:00:00Z",
        "phase": "gate_approved",
        "quality_gates": ["just check"],
        "host_capabilities": {"gh": True},
        "agent_resolution": {
            "request": {
                "work": "test",
                "preferred_types": ["planner"],
                "required_tools": ["read"],
                "permissions": "read-only",
                "isolation": "fresh-context",
                "minimum_power": "powerful",
                "effort": "high",
            },
            "attempts": [{"type": "planner", "model": "test", "power": "powerful", "result": "accepted", "reason": "exact"}],
            "resolved": {"type": "planner", "model": "test", "power": "powerful", "effort": "high", "topology": "sequential"},
            "fallback_reason": None,
            "degraded": False,
            "permission_enforcement": "tool-restricted",
        },
        "seed": {"items": []},
        "curds": _curds(),
        "wiring": [
            {
                "id": "W1",
                "type": "barrel_export",
                "file": "src/index.ts",
                "depends_on": [],
                "status": "pending",
            }
        ],
    }


def _pr_plan() -> dict[str, object]:
    return {
        "shape": "single",
        "groups": [
            {
                "branch": "ultracook/feature-name/pr-1",
                "title": "feat(feature): ship",
                "base": "main",
                "commits": ["abc1234"],
                "depends_on": [],
            }
        ],
    }


class TestRunManifestValidator:
    def test_valid_manifest_passes(self, validate_manifest: ModuleType) -> None:
        assert _validate_run_manifest(validate_manifest, _manifest()) == []

    def test_valid_baseline_block_passes(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["baseline"] = _baseline()
        assert _validate_run_manifest(validate_manifest, manifest) == []

    def test_absent_baseline_block_stays_valid(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        assert "baseline" not in manifest
        assert _validate_run_manifest(validate_manifest, manifest) == []

    def test_baseline_missing_captured_at_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        del baseline["captured_at"]
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.captured_at is required" in error for error in errors)

    def test_baseline_gate_missing_cmd_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        gate = _d(_l(baseline["gates"])[0])
        del gate["cmd"]
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.gates[1].cmd is required" in error for error in errors)

    def test_baseline_failure_missing_signature_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        gate = _d(_l(baseline["gates"])[0])
        failure = _d(_l(gate["failures"])[0])
        del failure["signature"]
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any(
            "baseline.gates[1].failures[1].signature is required" in error for error in errors
        )

    def test_baseline_non_dict_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["baseline"] = "not-an-object"
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline must be an object" in error for error in errors)

    def test_baseline_gates_non_list_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["gates"] = "not-a-list"
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.gates must be a list" in error for error in errors)

    def test_baseline_gate_entry_non_dict_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["gates"] = ["not-an-object"]
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any(
            "baseline.gates[1] must be an object, got str" in error for error in errors
        )

    def test_baseline_failures_non_list_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        gate = _d(_l(baseline["gates"])[0])
        gate["failures"] = "not-a-list"
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.gates[1].failures must be a list" in error for error in errors)

    def test_baseline_failure_entry_non_dict_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        gate = _d(_l(baseline["gates"])[0])
        gate["failures"] = ["not-an-object"]
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any(
            "baseline.gates[1].failures[1] must be an object, got str" in error
            for error in errors
        )

    def test_baseline_captured_at_empty_string_is_reported_not_as_missing(
        self, validate_manifest: ModuleType
    ) -> None:
        # An empty/whitespace captured_at is a present-but-invalid value, distinct
        # from an absent key -- it must fail non_empty_string, not required_keys.
        manifest = _manifest()
        baseline = _baseline()
        baseline["captured_at"] = "   "
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.captured_at must be a non-empty string" in error for error in errors)
        assert not any("baseline.captured_at is required" in error for error in errors)

    def test_baseline_captured_at_non_string_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["captured_at"] = 20260514
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.captured_at must be a non-empty string" in error for error in errors)

    def test_baseline_extra_keys_are_ignored_like_sibling_blocks(
        self, validate_manifest: ModuleType
    ) -> None:
        # Matches post_review's posture: unknown keys aren't rejected by the
        # validator, and the schema has no additionalProperties:false on
        # sibling optional blocks either (checked below).
        manifest = _manifest()
        baseline = _baseline()
        baseline["future_field"] = "reserved-for-later"
        manifest["baseline"] = baseline
        assert _validate_run_manifest(validate_manifest, manifest) == []

    def test_repair_dispatch_valid_passes(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["repair_dispatch"] = {
            "slug": "repair-feature-name",
            "branch": "worktree-agent-repair-feature-name",
        }
        manifest["baseline"] = baseline
        assert _validate_run_manifest(validate_manifest, manifest) == []

    def test_repair_dispatch_with_pr_passes(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["repair_dispatch"] = {
            "slug": "repair-feature-name",
            "branch": "worktree-agent-repair-feature-name",
            "pr": "https://github.com/example/repo/pull/42",
        }
        manifest["baseline"] = baseline
        assert _validate_run_manifest(validate_manifest, manifest) == []

    def test_repair_dispatch_missing_branch_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["repair_dispatch"] = {"slug": "repair-feature-name"}
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.repair_dispatch.branch is required" in error for error in errors)

    def test_repair_dispatch_non_dict_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["repair_dispatch"] = "not-an-object"
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.repair_dispatch must be an object" in error for error in errors)

    def test_baseline_without_repair_dispatch_stays_valid(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["baseline"] = _baseline()
        assert "repair_dispatch" not in _d(manifest["baseline"])
        assert _validate_run_manifest(validate_manifest, manifest) == []

    def test_repair_dispatch_empty_slug_is_reported_not_as_missing(
        self, validate_manifest: ModuleType
    ) -> None:
        # A present-but-empty slug is a present-but-invalid value, distinct
        # from an absent key -- matches captured_at's boundary posture above.
        manifest = _manifest()
        baseline = _baseline()
        baseline["repair_dispatch"] = {"slug": "   ", "branch": "worktree-agent-repair-x"}
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.repair_dispatch.slug must be a non-empty string" in error for error in errors)
        assert not any("baseline.repair_dispatch.slug is required" in error for error in errors)

    def test_repair_dispatch_pr_non_string_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["repair_dispatch"] = {
            "slug": "repair-feature-name",
            "branch": "worktree-agent-repair-feature-name",
            "pr": 42,
        }
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("baseline.repair_dispatch.pr must be a non-empty string" in error for error in errors)

    def test_repair_dispatch_extra_keys_are_ignored_like_sibling_blocks(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["repair_dispatch"] = {
            "slug": "repair-feature-name",
            "branch": "worktree-agent-repair-feature-name",
            "future_field": "reserved-for-later",
        }
        manifest["baseline"] = baseline
        assert _validate_run_manifest(validate_manifest, manifest) == []

    def test_baseline_multiple_gates_and_failures_all_errors_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        # Aggregation, not first-error-wins: two gates each with two broken
        # failures must surface all four distinct locations.
        manifest = _manifest()
        baseline = _baseline()
        broken_failure = {"suite": "pytest"}  # missing test_id and signature
        baseline["gates"] = [
            {"cmd": "just check", "failures": [broken_failure, dict(broken_failure)]},
            {"cmd": "just lint", "failures": [broken_failure, dict(broken_failure)]},
        ]
        manifest["baseline"] = baseline
        errors = _validate_run_manifest(validate_manifest, manifest)
        for gate_index in (1, 2):
            for failure_index in (1, 2):
                where = f"baseline.gates[{gate_index}].failures[{failure_index}]"
                assert any(f"{where}.test_id is required" in error for error in errors)
                assert any(f"{where}.signature is required" in error for error in errors)

    def test_baseline_schema_required_keys_match_validator(
        self, manifest_schema_path: Path
    ) -> None:
        # Schema/validator agreement: the JSON schema's required-key lists for
        # baseline, gates, and failures must mirror what _validate_baseline
        # actually enforces, or the two would silently diverge.
        schema = cast(
            "dict[str, object]",
            json.loads(manifest_schema_path.read_text(encoding="utf-8")),
        )
        properties = _d(schema["properties"])
        baseline_schema = _d(properties["baseline"])
        assert "baseline" not in _l(schema.get("required", []))
        assert set(_l(baseline_schema["required"])) == {"captured_at", "gates"}
        baseline_properties = _d(baseline_schema["properties"])
        gates_schema = _d(baseline_properties["gates"])
        gate_schema = _d(gates_schema["items"])
        assert set(_l(gate_schema["required"])) == {"cmd", "failures"}
        gate_properties = _d(gate_schema["properties"])
        failures_schema = _d(gate_properties["failures"])
        failure_schema = _d(failures_schema["items"])
        assert set(_l(failure_schema["required"])) == {"suite", "test_id", "signature"}
        repair_dispatch_schema = _d(baseline_properties["repair_dispatch"])
        assert set(_l(repair_dispatch_schema["required"])) == {"slug", "branch"}

    def test_missing_top_level_section_fails(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        del manifest["curds"]
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("manifest.curds is required" in error for error in errors)

    def test_non_dict_wiring_entry_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["wiring"] = [None]
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("wiring[1] must be an object" in error for error in errors)

    def test_wiring_missing_id_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["wiring"] = [
            {
                "type": "barrel_export",
                "file": "src/index.ts",
                "depends_on": [],
                "status": "pending",
            }
        ]
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("wiring[1].id is required" in error for error in errors)

    def test_embedded_pr_plan_is_validated(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["pr_plan"] = {"shape": "single", "groups": []}
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("manifest.pr_plan.groups must be a non-empty list" in error for error in errors)

    def test_empty_behavior_reported_exactly_once(
        self, validate_manifest: ModuleType
    ) -> None:
        # Acceptance #3: a run manifest with one curd whose behavior is empty
        # must produce exactly ONE error mentioning that curd's behavior.
        # Before the entity-module refactor, validate_manifest reported it twice:
        # once via lifecycle's non_empty_string and once via validate_decomposition.
        manifest = _manifest()
        curd = _d(_l(manifest["curds"])[0])
        curd["behavior"] = ""
        errors = _validate_run_manifest(validate_manifest, manifest)
        behavior_errors = [e for e in errors if "behavior" in e]
        assert len(behavior_errors) == 1, (
            f"expected exactly 1 behavior error, got {len(behavior_errors)}: {behavior_errors}"
        )

    def test_current_review_requires_reproducibility_fields(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        manifest["current_review"] = {"base_commit": "a" * 40}
        errors = _validate_run_manifest(validate_manifest, manifest)
        for field in ("reviewed_tree_oid", "diff_hash", "scope"):
            assert any(f"current_review.{field} is required" in error for error in errors)

    def test_post_review_requires_review_context(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["post_review"] = {"press_slug": ".cheese/press/feature.md"}
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("post_review.review_context is required" in error for error in errors)

    def test_completed_curd_requires_review_context(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        curd = _d(_l(manifest["curds"])[0])
        curd["status"] = "completed"
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("curds[1].review_context is required" in error for error in errors)

    @pytest.mark.parametrize("phase", ["post_review_complete", "pr_publish_complete"])
    def test_completed_review_phases_require_provenance(
        self, validate_manifest: ModuleType, phase: str
    ) -> None:
        manifest = _manifest()
        manifest["phase"] = phase
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("manifest.current_review is required" in error for error in errors)
        assert any("manifest.post_review is required" in error for error in errors)

    def test_completed_review_provenance_passes(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        curd = _d(_l(manifest["curds"])[0])
        curd.update(status="completed", review_context=_review_context())
        manifest["phase"] = "post_review_complete"
        manifest["current_review"] = _review_context()
        manifest["post_review"] = {"review_context": _review_context()}
        assert _validate_run_manifest(validate_manifest, manifest) == []

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("base_commit", "g" * 40),
            ("base_commit", "a" * 39),
            ("base_commit", "a" * 41),
            ("reviewed_tree_oid", "abc"),
            ("reviewed_tree_oid", "B" * 41),
            ("diff_hash", "sha256:" + "a" * 63),
            ("diff_hash", "md5:" + "a" * 64),
        ],
    )
    def test_review_context_rejects_malformed_identity(
        self, validate_manifest: ModuleType, field: str, value: str
    ) -> None:
        manifest = _manifest()
        manifest["current_review"] = _review_context()
        review_context = _d(manifest["current_review"])
        review_context[field] = value
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any(f"current_review.{field}" in error for error in errors)

    @pytest.mark.parametrize(
        ("path", "value", "expected"),
        [
            (("request", "required_tools"), [], "required_tools"),
            (("request", "preferred_types"), [], "preferred_types"),
            (("request", "minimum_power"), "turbo", "minimum_power"),
            (("attempts", 0, "result"), "maybe", "attempts[1].result"),
            (("resolved", "topology"), "nested", "resolved.topology"),
            (("fallback_reason",), "", "fallback_reason"),
            (("degraded",), "yes", "degraded"),
        ],
    )
    def test_agent_resolution_rejects_invalid_nested_fields(
        self,
        validate_manifest: ModuleType,
        path: tuple[str | int, ...],
        value: object,
        expected: str,
    ) -> None:
        manifest = _manifest()
        target: object = manifest["agent_resolution"]
        for key in path[:-1]:
            target = _nav(target, key)
        _nav_set(target, path[-1], value)
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any(expected in error for error in errors)

    def test_agent_resolution_requires_nested_fields(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = _d(manifest["agent_resolution"])
        del _d(resolution["request"])["effort"]
        del _d(_l(resolution["attempts"])[0])["reason"]
        del _d(resolution["resolved"])["model"]
        errors = _validate_run_manifest(validate_manifest, manifest)
        for path in ("request.effort", "attempts[1].reason", "resolved.model"):
            assert any(path in error and "required" in error for error in errors)

    @pytest.mark.parametrize(
        ("mutations", "expected"),
        [
            ({"permission_enforcement": "prompt-only"}, "degraded=true"),
            ({"resolved.power": "unknown"}, "unknown power"),
            ({"request.permissions": "write", "permission_enforcement": "prompt-only"}, "write request"),
        ],
    )
    def test_agent_resolution_enforces_degradation_consistency(
        self, validate_manifest: ModuleType, mutations: dict[str, object], expected: str
    ) -> None:
        manifest = _manifest()
        resolution = _d(manifest["agent_resolution"])
        for path, value in mutations.items():
            target = resolution
            parts = path.split(".")
            for part in parts[:-1]:
                target = _d(target[part])
            target[parts[-1]] = value
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any(expected in error for error in errors)

    def test_agent_resolution_rejects_accepted_power_below_minimum(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = _d(manifest["agent_resolution"])
        _d(_l(resolution["attempts"])[0])["power"] = "cheap"
        _d(resolution["resolved"])["power"] = "cheap"
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("below request minimum" in error for error in errors)

    def test_agent_resolution_requires_reason_for_nonpreferred_fallback(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = _d(manifest["agent_resolution"])
        _d(_l(resolution["attempts"])[0]).update(type="general", model="general-test")
        _d(resolution["resolved"]).update(type="general", model="general-test")
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("fallback_reason" in error for error in errors)

    def test_agent_resolution_requires_resolved_to_match_accepted_attempt(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = _d(manifest["agent_resolution"])
        _d(resolution["resolved"])["model"] = "different-model"
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("must match the accepted attempt" in error for error in errors)

    def test_agent_resolution_requires_exactly_one_accepted_attempt(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = _d(manifest["agent_resolution"])
        _l(resolution["attempts"]).append(
            {
                "type": "general",
                "model": "fallback",
                "power": "powerful",
                "result": "accepted",
                "reason": "fallback",
            }
        )
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("exactly one accepted attempt" in error for error in errors)

    def test_agent_resolution_unknown_acceptance_must_be_final(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = _d(manifest["agent_resolution"])
        _d(_l(resolution["attempts"])[0])["power"] = "unknown"
        _l(resolution["attempts"]).append(
            {
                "type": "general",
                "model": "fallback",
                "power": "powerful",
                "result": "rejected",
                "reason": "not selected",
            }
        )
        _d(resolution["resolved"])["power"] = "unknown"
        resolution["degraded"] = True
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("unknown-power accepted attempt must be final" in error for error in errors)

    def test_agent_resolution_preferred_exact_acceptance_requires_null_reason(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = _d(manifest["agent_resolution"])
        resolution["fallback_reason"] = "not a fallback"
        errors = _validate_run_manifest(validate_manifest, manifest)
        assert any("preferred exact acceptance requires fallback_reason=null" in error for error in errors)


class TestPrPlanValidator:
    def test_valid_pr_plan_passes(self, validate_pr_plan: ModuleType) -> None:
        assert _validate_pr_plan(validate_pr_plan, _pr_plan()) == []

    def test_single_shape_requires_one_group(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        groups = _l(plan["groups"])
        groups.append({**_d(groups[0]), "branch": "ultracook/feature-name/pr-2"})
        assert _validate_pr_plan(validate_pr_plan, plan) == [
            "PrPlan.groups must be exactly one group for the single shape, not 2"
        ]

    def test_orthogonal_flat_requires_main_base(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["shape"] = "orthogonal_flat"
        _d(_l(plan["groups"])[0])["base"] = "feature-base"
        errors = _validate_pr_plan(validate_pr_plan, plan)
        assert any("base must be main" in error for error in errors)

    def test_duplicate_branch_fails(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["shape"] = "stacked_linear"
        groups = _l(plan["groups"])
        groups.append(dict(_d(groups[0])))
        assert _validate_pr_plan(validate_pr_plan, plan) == [
            "PrPlan.groups must be branch-distinct: 'ultracook/feature-name/pr-1' "
            + "is claimed by two groups -- the two pull requests would race the same ref"
        ]

    def test_commit_must_be_hex_sha(self, validate_pr_plan: ModuleType) -> None:
        # An option-shaped string would reach `git cherry-pick` as a flag even
        # after single-quoting (single quotes do not stop git from parsing
        # option-shaped tokens). Reject those at the plan boundary.
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["commits"] = ["--abort"]
        errors = _validate_pr_plan(validate_pr_plan, plan)
        assert any("must be a hex SHA" in error for error in errors)

    def test_base_with_newline_rejected(self, validate_pr_plan: ModuleType) -> None:
        # `base` is emitted raw into a `# comment` line by pr_plan_to_branches
        # and piped to `bash -s`; a newline would escape the comment and run
        # arbitrary shell. It must be charset-gated like `branch`.
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["base"] = "main\nrm -rf /tmp/pwned"
        errors = _validate_pr_plan(validate_pr_plan, plan)
        assert any("base contains characters unsafe for a git ref" in error for error in errors)

    def test_commit_rejects_non_hex_alphabetics(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["commits"] = ["HEAD~1"]
        errors = _validate_pr_plan(validate_pr_plan, plan)
        assert any("must be a hex SHA" in error for error in errors)

    def test_commit_accepts_full_sha1(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["commits"] = ["a" * 40]
        assert _validate_pr_plan(validate_pr_plan, plan) == []

    def test_commit_rejects_too_short(self, validate_pr_plan: ModuleType) -> None:
        # 7 hex chars is git's default short-SHA floor — shorter values risk
        # colliding with branch / tag names of the same shape (e.g. `feed`).
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["commits"] = ["abcdef"]
        errors = _validate_pr_plan(validate_pr_plan, plan)
        assert any("must be a hex SHA" in error for error in errors)

    def test_body_when_present_must_be_string(self, validate_pr_plan: ModuleType) -> None:
        # Schema declares body as a string; the emitter calls `.replace()` on it,
        # so a non-string body would crash pr_plan_to_branches. Reject at the
        # plan boundary so malformed planner output surfaces as a validation
        # error rather than a traceback downstream.
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["body"] = 123
        errors = _validate_pr_plan(validate_pr_plan, plan)
        assert any("body must be a string" in error for error in errors)

    def test_body_empty_string_is_allowed(self, validate_pr_plan: ModuleType) -> None:
        # `gh pr create --body ''` is valid, so empty body must pass.
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["body"] = ""
        assert _validate_pr_plan(validate_pr_plan, plan) == []

    def test_body_omitted_is_allowed(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        _ = _d(_l(plan["groups"])[0]).pop("body", None)
        assert _validate_pr_plan(validate_pr_plan, plan) == []

    def test_depends_on_omitted_is_allowed(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        _ = _d(_l(plan["groups"])[0]).pop("depends_on", None)
        assert _validate_pr_plan(validate_pr_plan, plan) == []

    def test_depends_on_none_is_allowed(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["depends_on"] = None
        assert _validate_pr_plan(validate_pr_plan, plan) == []

    def test_depends_on_string_is_rejected(self, validate_pr_plan: ModuleType) -> None:
        # Regression: `depends_on or []` silently accepted falsy non-lists.
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["depends_on"] = ""
        errors = _validate_pr_plan(validate_pr_plan, plan)
        assert any("depends_on must be a list" in error for error in errors)

    def test_depends_on_non_list_is_rejected(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        _d(_l(plan["groups"])[0])["depends_on"] = "main"
        errors = _validate_pr_plan(validate_pr_plan, plan)
        assert any("depends_on must be a list" in error for error in errors)


class TestCLIs:
    def test_validate_manifest_cli_accepts_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.yaml"
        _ = path.write_text(yaml.safe_dump(_manifest(), sort_keys=False), encoding="utf-8")
        result = subprocess.run([sys.executable, str(BUNDLE), "validate_manifest", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "manifest valid" in result.stdout

    def test_validate_decomposition_cli_accepts_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.yaml"
        _ = path.write_text(yaml.safe_dump(_manifest(), sort_keys=False), encoding="utf-8")
        result = subprocess.run([sys.executable, str(BUNDLE), "validate_decomposition", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "decomposition valid" in result.stdout

    def test_validate_pr_plan_cli_accepts_json(self, tmp_path: Path) -> None:
        path = tmp_path / "pr-plan.json"
        _ = path.write_text(json.dumps(_pr_plan()), encoding="utf-8")
        result = subprocess.run([sys.executable, str(BUNDLE), "validate_pr_plan", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "plan valid" in result.stdout