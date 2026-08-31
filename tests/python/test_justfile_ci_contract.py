"""Contracts for the Just recipes and CI tool pins."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
needs_just = pytest.mark.skipif(
    shutil.which("just") is None, reason="just is not installed"
)


@needs_just
def test_check_and_ci_depend_on_dead_code() -> None:
    """Both aggregate recipes invoke the owner-qualified dead-code gate."""
    result = subprocess.run(
        ["just", "--dump", "--dump-format", "json"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    recipes = cast(dict[str, object], json.loads(result.stdout)["recipes"])
    for name in ("check", "ci"):
        recipe = cast(dict[str, object], recipes[name])
        deps = cast(list[dict[str, object]], recipe["dependencies"])
        dependencies = {cast(str, dependency["recipe"]) for dependency in deps}
        assert "lint-py-dead-code" in dependencies


@needs_just
def test_check_and_ci_depend_on_bundle_currency() -> None:
    """check runs the index-mode bundle check; ci runs the head-mode one."""
    result = subprocess.run(
        ["just", "--dump", "--dump-format", "json"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    recipes = cast(dict[str, object], json.loads(result.stdout)["recipes"])

    def dependencies(name: str) -> set[str]:
        recipe = cast(dict[str, object], recipes[name])
        deps = cast(list[dict[str, object]], recipe["dependencies"])
        return {cast(str, dependency["recipe"]) for dependency in deps}

    assert "check-bundles" in dependencies("check")
    assert "check-bundles-ci" in dependencies("ci")
    assert "bundle" in dependencies("check-bundles-ci")


def test_build_pyz_workflow_runs_the_bundle_currency_matrix() -> None:
    """build-pyz.yml's matrix job runs check_bundles.py -- the full
    isolated-execution + command-dispatch conformance matrix -- across every
    pinned Python, not just the justfile's local convenience recipes.
    """
    jobs = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / ".github" / "workflows" / "build-pyz.yml").read_text(encoding="utf-8")
        )["jobs"],
    )
    build = cast(dict[str, object], jobs["build"])
    matrix = cast(
        list[dict[str, str]],
        cast(dict[str, object], cast(dict[str, object], build["strategy"])["matrix"])[
            "include"
        ],
    )
    assert {entry["python"] for entry in matrix} >= {"3.12", "3.14"}
    steps = cast(list[dict[str, object]], build["steps"])
    runs = [cast(str, step["run"]) for step in steps if "run" in step]
    assert any("scripts/check_bundles.py" in run for run in runs)
    assert any("scripts/build_pyz.py" in run for run in runs)


def test_ci_jobs_pin_tools() -> None:
    """Test and lint jobs pin both uv and just setup actions."""
    jobs = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        )["jobs"],
    )
    for name in ("test", "lint"):
        job = cast(dict[str, object], jobs[name])
        steps = cast(list[dict[str, object]], job["steps"])
        uses: dict[str, object] = {
            cast(str, step["uses"]).split("@")[0]: step.get("with", {})
            for step in steps
            if "uses" in step
        }
        assert "version" in cast(dict[str, object], uses["astral-sh/setup-uv"])
        assert "just-version" in cast(dict[str, object], uses["extractions/setup-just"])