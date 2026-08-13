"""Contracts for the machine-readable Just recipe graph."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_ci_recipe_depends_on_lint_dead() -> None:
    result = subprocess.run(
        ["just", "--dump", "--dump-format", "json"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    dump: Any = json.loads(result.stdout)
    assert isinstance(dump, dict)

    recipes = dump["recipes"]
    assert isinstance(recipes, dict)

    ci = recipes["ci"]
    assert isinstance(ci, dict)

    dependencies = ci["dependencies"]
    assert isinstance(dependencies, list)
    assert all(isinstance(dependency, dict) for dependency in dependencies)
    assert "lint-dead" in {dependency["recipe"] for dependency in dependencies}


def test_ci_jobs_install_just_and_uv() -> None:
    workflow: Any = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "validate.yml").read_text()
    )
    assert isinstance(workflow, dict)
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    setup_just = (
        "extractions/setup-just@f8a3cce218d9f83db3a2ecd90e41ac3de6cdfd9b"
    )
    setup_uv = "astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9"
    for job_name in ("test", "lint"):
        steps = jobs[job_name]["steps"]
        assert isinstance(steps, list)
        uses = {
            step["uses"]: step.get("with", {})
            for step in steps
            if isinstance(step, dict) and "uses" in step
        }
        assert uses[setup_just]["just-version"] == "1.58.0"
        assert setup_uv in uses
