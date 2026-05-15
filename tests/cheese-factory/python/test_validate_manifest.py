"""Tests for cheese-factory manifest and PR-plan validators."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import yaml


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


def _manifest() -> dict:
    return {
        "slug": "feature-name",
        "spec_path": ".cheese/specs/feature-name.md",
        "created": "2026-05-14T10:00:00Z",
        "phase": "gate_approved",
        "quality_gates": ["just check"],
        "host_capabilities": {"gh": True},
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
                "branch": "cheese-factory/feature-name/pr-1",
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


class TestPrPlanValidator:
    def test_valid_pr_plan_passes(self, validate_pr_plan: ModuleType) -> None:
        assert validate_pr_plan.validate_pr_plan(_pr_plan()) == []

    def test_single_shape_requires_one_group(self, validate_pr_plan: ModuleType) -> None:
        plan = _pr_plan()
        plan["groups"].append({**plan["groups"][0], "branch": "cheese-factory/feature-name/pr-2"})
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


class TestCLIs:
    def test_validate_manifest_cli_accepts_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(_manifest(), sort_keys=False), encoding="utf-8")
        script = (
            Path(__file__).resolve().parents[3]
            / "skills"
            / "cheese-factory"
            / "scripts"
            / "validate_manifest.py"
        )
        result = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "manifest valid" in result.stdout

    def test_validate_decomposition_cli_accepts_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(_manifest(), sort_keys=False), encoding="utf-8")
        script = (
            Path(__file__).resolve().parents[3]
            / "skills"
            / "cheese-factory"
            / "scripts"
            / "validate_decomposition.py"
        )
        result = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "decomposition valid" in result.stdout

    def test_validate_pr_plan_cli_accepts_json(self, tmp_path: Path) -> None:
        path = tmp_path / "pr-plan.json"
        path.write_text(json.dumps(_pr_plan()), encoding="utf-8")
        script = (
            Path(__file__).resolve().parents[3]
            / "skills"
            / "cheese-factory"
            / "scripts"
            / "validate_pr_plan.py"
        )
        result = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "plan valid" in result.stdout
