"""Contracts for the machine-readable Just recipe graph."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

_needs_just = pytest.mark.skipif(shutil.which("just") is None, reason="just is not installed")


@_needs_just
def test_check_and_ci_recipes_depend_on_lint_py_dead_code() -> None:
    result = subprocess.run(
        ["just", "--dump", "--dump-format", "json"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    recipes = json.loads(result.stdout)["recipes"]

    for recipe_name in ("check", "ci"):
        dependencies = {
            dependency["recipe"] for dependency in recipes[recipe_name]["dependencies"]
        }
        assert "lint-py-dead-code" in dependencies, dependencies


@_needs_just
def test_ci_jobs_install_just_and_uv() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]

    for job_name in ("test", "lint"):
        steps = jobs[job_name]["steps"]
        uses = {
            step["uses"].split("@")[0]: step.get("with", {})
            for step in steps
            if isinstance(step, dict) and "uses" in step
        }
        assert "just-version" in uses["extractions/setup-just"]
        assert "version" in uses["astral-sh/setup-uv"]