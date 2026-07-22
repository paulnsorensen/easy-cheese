"""Tests for ultracook manifest and PR-plan validators."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import yaml
import pytest

import build_pyz

BUNDLE = build_pyz.cached_bundle("ultracook")


def _curds(n: int = 5) -> list[dict]:
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


def _review_context() -> dict:
    return {
        "base_commit": "a" * 40,
        "reviewed_tree_oid": "B" * 64,
        "diff_hash": "sha256:" + "c" * 64,
        "scope": ["src/feature.ts"],
    }

def _baseline() -> dict:
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

def _manifest() -> dict:
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


def _pr_plan() -> dict:
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
        assert validate_manifest.validate_run_manifest(_manifest()) == []

    def test_valid_baseline_block_passes(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["baseline"] = _baseline()
        assert validate_manifest.validate_run_manifest(manifest) == []

    def test_absent_baseline_block_stays_valid(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        assert "baseline" not in manifest
        assert validate_manifest.validate_run_manifest(manifest) == []

    def test_baseline_missing_captured_at_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        del baseline["captured_at"]
        manifest["baseline"] = baseline
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("baseline.captured_at is required" in error for error in errors)

    def test_baseline_gate_missing_cmd_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        del baseline["gates"][0]["cmd"]
        manifest["baseline"] = baseline
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("baseline.gates[1].cmd is required" in error for error in errors)

    def test_baseline_failure_missing_signature_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        del baseline["gates"][0]["failures"][0]["signature"]
        manifest["baseline"] = baseline
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any(
            "baseline.gates[1].failures[1].signature is required" in error for error in errors
        )

    def test_baseline_non_dict_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["baseline"] = "not-an-object"
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("baseline must be an object" in error for error in errors)

    def test_baseline_gates_non_list_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["gates"] = "not-a-list"
        manifest["baseline"] = baseline
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("baseline.gates must be a list" in error for error in errors)

    def test_baseline_gate_entry_non_dict_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["gates"] = ["not-an-object"]
        manifest["baseline"] = baseline
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any(
            "baseline.gates[1] must be an object, got str" in error for error in errors
        )

    def test_baseline_failures_non_list_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["gates"][0]["failures"] = "not-a-list"
        manifest["baseline"] = baseline
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("baseline.gates[1].failures must be a list" in error for error in errors)

    def test_baseline_failure_entry_non_dict_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["gates"][0]["failures"] = ["not-an-object"]
        manifest["baseline"] = baseline
        errors = validate_manifest.validate_run_manifest(manifest)
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
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("baseline.captured_at must be a non-empty string" in error for error in errors)
        assert not any("baseline.captured_at is required" in error for error in errors)

    def test_baseline_captured_at_non_string_is_reported(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        baseline = _baseline()
        baseline["captured_at"] = 20260514
        manifest["baseline"] = baseline
        errors = validate_manifest.validate_run_manifest(manifest)
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
        assert validate_manifest.validate_run_manifest(manifest) == []

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
        errors = validate_manifest.validate_run_manifest(manifest)
        for gate_index in (1, 2):
            for failure_index in (1, 2):
                where = f"baseline.gates[{gate_index}].failures[{failure_index}]"
                assert any(f"{where}.test_id is required" in error for error in errors)
                assert any(f"{where}.signature is required" in error for error in errors)

    def test_baseline_schema_required_keys_match_validator(
        self, manifest_schema_path
    ) -> None:
        # Schema/validator agreement: the JSON schema's required-key lists for
        # baseline, gates, and failures must mirror what _validate_baseline
        # actually enforces, or the two would silently diverge.
        schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
        baseline_schema = schema["properties"]["baseline"]
        assert "baseline" not in schema.get("required", [])
        assert set(baseline_schema["required"]) == {"captured_at", "gates"}
        gate_schema = baseline_schema["properties"]["gates"]["items"]
        assert set(gate_schema["required"]) == {"cmd", "failures"}
        failure_schema = gate_schema["properties"]["failures"]["items"]
        assert set(failure_schema["required"]) == {"suite", "test_id", "signature"}

    def test_missing_top_level_section_fails(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        del manifest["curds"]
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("manifest.curds is required" in error for error in errors)

    def test_non_dict_wiring_entry_is_reported(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["wiring"] = [None]
        errors = validate_manifest.validate_run_manifest(manifest)
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
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("wiring[1].id is required" in error for error in errors)

    def test_embedded_pr_plan_is_validated(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["pr_plan"] = {"shape": "single", "groups": []}
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("manifest.pr_plan.groups must be a non-empty list" in error for error in errors)

    def test_empty_behavior_reported_exactly_once(
        self, validate_manifest: ModuleType
    ) -> None:
        # Acceptance #3: a run manifest with one curd whose behavior is empty
        # must produce exactly ONE error mentioning that curd's behavior.
        # Before the entity-module refactor, validate_manifest reported it twice:
        # once via lifecycle's non_empty_string and once via validate_decomposition.
        manifest = _manifest()
        manifest["curds"][0]["behavior"] = ""
        errors = validate_manifest.validate_run_manifest(manifest)
        behavior_errors = [e for e in errors if "behavior" in e and "1" in e]
        assert len(behavior_errors) == 1, (
            f"expected exactly 1 behavior error, got {len(behavior_errors)}: {behavior_errors}"
        )

    def test_current_review_requires_reproducibility_fields(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        manifest["current_review"] = {"base_commit": "a" * 40}
        errors = validate_manifest.validate_run_manifest(manifest)
        for field in ("reviewed_tree_oid", "diff_hash", "scope"):
            assert any(f"current_review.{field} is required" in error for error in errors)

    def test_post_review_requires_review_context(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["post_review"] = {"press_slug": ".cheese/press/feature.md"}
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("post_review.review_context is required" in error for error in errors)

    def test_completed_curd_requires_review_context(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["curds"][0]["status"] = "completed"
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("curds[1].review_context is required" in error for error in errors)

    @pytest.mark.parametrize("phase", ["post_review_complete", "pr_publish_complete"])
    def test_completed_review_phases_require_provenance(
        self, validate_manifest: ModuleType, phase: str
    ) -> None:
        manifest = _manifest()
        manifest["phase"] = phase
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("manifest.current_review is required" in error for error in errors)
        assert any("manifest.post_review is required" in error for error in errors)

    def test_completed_review_provenance_passes(self, validate_manifest: ModuleType) -> None:
        manifest = _manifest()
        manifest["curds"][0].update(status="completed", review_context=_review_context())
        manifest["phase"] = "post_review_complete"
        manifest["current_review"] = _review_context()
        manifest["post_review"] = {"review_context": _review_context()}
        assert validate_manifest.validate_run_manifest(manifest) == []

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
        manifest["current_review"][field] = value
        errors = validate_manifest.validate_run_manifest(manifest)
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
            target = target[key]  # type: ignore[index]
        target[path[-1]] = value  # type: ignore[index]
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any(expected in error for error in errors)

    def test_agent_resolution_requires_nested_fields(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        del manifest["agent_resolution"]["request"]["effort"]
        del manifest["agent_resolution"]["attempts"][0]["reason"]
        del manifest["agent_resolution"]["resolved"]["model"]
        errors = validate_manifest.validate_run_manifest(manifest)
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
        resolution = manifest["agent_resolution"]
        for path, value in mutations.items():
            target = resolution
            parts = path.split(".")
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any(expected in error for error in errors)

    def test_agent_resolution_rejects_accepted_power_below_minimum(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = manifest["agent_resolution"]
        resolution["attempts"][0]["power"] = "cheap"
        resolution["resolved"]["power"] = "cheap"
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("below request minimum" in error for error in errors)

    def test_agent_resolution_requires_reason_for_nonpreferred_fallback(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = manifest["agent_resolution"]
        resolution["attempts"][0].update(type="general", model="general-test")
        resolution["resolved"].update(type="general", model="general-test")
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("fallback_reason" in error for error in errors)

    def test_agent_resolution_requires_resolved_to_match_accepted_attempt(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        manifest["agent_resolution"]["resolved"]["model"] = "different-model"
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("must match the accepted attempt" in error for error in errors)

    def test_agent_resolution_requires_exactly_one_accepted_attempt(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        manifest["agent_resolution"]["attempts"].append(
            {
                "type": "general",
                "model": "fallback",
                "power": "powerful",
                "result": "accepted",
                "reason": "fallback",
            }
        )
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("exactly one accepted attempt" in error for error in errors)

    def test_agent_resolution_unknown_acceptance_must_be_final(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        resolution = manifest["agent_resolution"]
        resolution["attempts"][0]["power"] = "unknown"
        resolution["attempts"].append(
            {
                "type": "general",
                "model": "fallback",
                "power": "powerful",
                "result": "rejected",
                "reason": "not selected",
            }
        )
        resolution["resolved"]["power"] = "unknown"
        resolution["degraded"] = True
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("unknown-power accepted attempt must be final" in error for error in errors)

    def test_agent_resolution_preferred_exact_acceptance_requires_null_reason(
        self, validate_manifest: ModuleType
    ) -> None:
        manifest = _manifest()
        manifest["agent_resolution"]["fallback_reason"] = "not a fallback"
        errors = validate_manifest.validate_run_manifest(manifest)
        assert any("preferred exact acceptance requires fallback_reason=null" in error for error in errors)


class TestPrPlanValidator:
    def test_valid_pr_plan_passes(self, validate_pr_plan: ModuleType) -> None:
        assert validate_pr_plan.validate_pr_plan(_pr_plan()) == []

    def test_single_shape_requires_one_group(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["groups"].append({**plan["groups"][0], "branch": "ultracook/feature-name/pr-2"})
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("single shape must contain exactly one group" in error for error in errors)

    def test_orthogonal_flat_requires_main_base(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["shape"] = "orthogonal_flat"
        plan["groups"][0]["base"] = "feature-base"
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("base must be main" in error for error in errors)

    def test_duplicate_branch_fails(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["shape"] = "stacked_linear"
        plan["groups"].append(dict(plan["groups"][0]))
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("duplicates" in error for error in errors)

    def test_commit_must_be_hex_sha(self, validate_pr_plan: ModuleType) -> None:
        # An option-shaped string would reach `git cherry-pick` as a flag even
        # after single-quoting (single quotes do not stop git from parsing
        # option-shaped tokens). Reject those at the plan boundary.
        plan = _pr_plan()
        plan["groups"][0]["commits"] = ["--abort"]
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("must be a hex SHA" in error for error in errors)

    def test_base_with_newline_rejected(self, validate_pr_plan: ModuleType) -> None:
        # `base` is emitted raw into a `# comment` line by pr_plan_to_branches
        # and piped to `bash -s`; a newline would escape the comment and run
        # arbitrary shell. It must be charset-gated like `branch`.
        plan = _pr_plan()
        plan["groups"][0]["base"] = "main\nrm -rf /tmp/pwned"
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("base contains characters unsafe for a git ref" in error for error in errors)

    def test_commit_rejects_non_hex_alphabetics(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["groups"][0]["commits"] = ["HEAD~1"]
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("must be a hex SHA" in error for error in errors)

    def test_commit_accepts_full_sha1(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["groups"][0]["commits"] = ["a" * 40]
        assert validate_pr_plan.validate_pr_plan(plan) == []

    def test_commit_rejects_too_short(self, validate_pr_plan: ModuleType) -> None:
        # 7 hex chars is git's default short-SHA floor — shorter values risk
        # colliding with branch / tag names of the same shape (e.g. `feed`).
        plan = _pr_plan()
        plan["groups"][0]["commits"] = ["abcdef"]
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("must be a hex SHA" in error for error in errors)

    def test_body_when_present_must_be_string(self, validate_pr_plan: ModuleType) -> None:
        # Schema declares body as a string; the emitter calls `.replace()` on it,
        # so a non-string body would crash pr_plan_to_branches. Reject at the
        # plan boundary so malformed planner output surfaces as a validation
        # error rather than a traceback downstream.
        plan = _pr_plan()
        plan["groups"][0]["body"] = 123
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("body must be a string when present" in error for error in errors)

    def test_body_empty_string_is_allowed(self, validate_pr_plan: ModuleType) -> None:
        # `gh pr create --body ''` is valid, so empty body must pass.
        plan = _pr_plan()
        plan["groups"][0]["body"] = ""
        assert validate_pr_plan.validate_pr_plan(plan) == []

    def test_body_omitted_is_allowed(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["groups"][0].pop("body", None)
        assert validate_pr_plan.validate_pr_plan(plan) == []

    def test_depends_on_omitted_is_allowed(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["groups"][0].pop("depends_on", None)
        assert validate_pr_plan.validate_pr_plan(plan) == []

    def test_depends_on_none_is_allowed(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["groups"][0]["depends_on"] = None
        assert validate_pr_plan.validate_pr_plan(plan) == []

    def test_depends_on_string_is_rejected(self, validate_pr_plan: ModuleType) -> None:
        # Regression: `depends_on or []` silently accepted falsy non-lists.
        plan = _pr_plan()
        plan["groups"][0]["depends_on"] = ""
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("depends_on must be a list" in error for error in errors)

    def test_depends_on_non_list_is_rejected(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["groups"][0]["depends_on"] = "main"
        errors = validate_pr_plan.validate_pr_plan(plan)
        assert any("depends_on must be a list" in error for error in errors)


class TestCLIs:
    def test_validate_manifest_cli_accepts_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(_manifest(), sort_keys=False), encoding="utf-8")
        result = subprocess.run([sys.executable, str(BUNDLE), "validate_manifest", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "manifest valid" in result.stdout

    def test_validate_decomposition_cli_accepts_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(_manifest(), sort_keys=False), encoding="utf-8")
        result = subprocess.run([sys.executable, str(BUNDLE), "validate_decomposition", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "decomposition valid" in result.stdout

    def test_validate_pr_plan_cli_accepts_json(self, tmp_path: Path) -> None:
        path = tmp_path / "pr-plan.json"
        path.write_text(json.dumps(_pr_plan()), encoding="utf-8")
        result = subprocess.run([sys.executable, str(BUNDLE), "validate_pr_plan", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "plan valid" in result.stdout
