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
def test_check_and_ci_do_not_repeat_wedge_check() -> None:
    """The test recipe owns archive freshness before archive execution."""
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
        assert "wedge-check" not in dependencies
        assert "test" in dependencies


@needs_just
def test_test_recipe_gates_runtime_and_committed_archives_before_suites() -> None:
    """The test recipe validates committed archives before executing them."""
    result = subprocess.run(
        ["just", "--dump", "--dump-format", "json"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assignments = cast(
        dict[str, dict[str, object]], json.loads(result.stdout)["assignments"]
    )
    value = cast(str, assignments["python"]["value"])

    assert "--with-requirements requirements/runtime.txt" in value
    assert "requirements-build.txt" not in value

    justfile = (ROOT / "justfile").read_text(encoding="utf-8")
    gates = justfile.index("scripts/runtime_gates.py")
    freshness = justfile.index("just wedge-check")
    python_suite = justfile.index("-m pytest tests/python")
    browser_suite = justfile.index("just test-mold-review")
    assert gates < freshness < min(python_suite, browser_suite)
    assert "skill_archives.py" not in justfile
    assert "EASY_CHEESE_PREBUILT_PYZ" not in justfile
    assert "prebuilt_pyz_dir" not in justfile
    assert '{{wedge}} bundle --root skills --check' in justfile


def test_docs_workflow_matches_the_package_build_command() -> None:
    """The documentation workflow builds and deploys what the package emits."""
    workflow = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
        ),
    )
    jobs = cast(dict[str, dict[str, object]], workflow["jobs"])
    scripts = cast(
        dict[str, str],
        cast(dict[str, object], json.loads((ROOT / "package.json").read_text()))[
            "scripts"
        ],
    )
    assert "docs:build" in scripts

    build_steps = cast(list[dict[str, object]], jobs["build"]["steps"])
    runs = [cast(str, step["run"]) for step in build_steps if "run" in step]
    assert any("docs:build" in run for run in runs)

    uploads = [
        step["with"]
        for step in build_steps
        if "upload-pages-artifact" in cast(str, step.get("uses", ""))
    ]
    assert uploads == [{"path": "dist"}], build_steps

    deploy = jobs["deploy"]
    assert deploy["needs"] == "build"
    assert "refs/heads/main" in cast(str, deploy["if"])


def test_validate_workflow_gates_committed_archives_before_suites() -> None:
    """validate.yml checks committed archives before executing them."""
    workflow_path = ROOT / ".github" / "workflows" / "validate.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = cast(dict[str, object], yaml.safe_load(workflow_text))
    jobs = cast(dict[str, object], workflow["jobs"])
    steps = cast(list[dict[str, object]], cast(dict[str, object], jobs["test"])["steps"])
    runs = [cast(str, step["run"]) for step in steps if "run" in step]
    gates = next(i for i, run in enumerate(runs) if "scripts/runtime_gates.py" in run)
    freshness = next(i for i, run in enumerate(runs) if "just wedge-check" in run)
    suites = [i for i, run in enumerate(runs) if "-m pytest" in run]
    assert suites
    assert gates < freshness < min(suites)
    assert workflow_text.count("\non:") == 1
    assert "pull_request:" in workflow_text
    assert "push:" in workflow_text
    assert "branches: [main]" in workflow_text
    assert workflow["permissions"] == {"contents": "read"}
    assert "skill_archives.py" not in workflow_text
    assert "EASY_CHEESE_PREBUILT_PYZ" not in workflow_text
    assert not (ROOT / ".github" / "workflows" / "wedge.yml").exists()


def test_ci_jobs_pin_tools() -> None:
    """Test and lint jobs pin uv and install a pinned just from PyPI.

    The just install must not use a GitHub-releases action: every such
    call spends the repo-wide GITHUB_TOKEN budget and fails all jobs once
    it is exhausted.
    """
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
        assert "extractions/setup-just" not in uses
        runs = [cast(str, step["run"]) for step in steps if "run" in step]
        assert any("uv tool install rust-just==1.58.0" in run for run in runs)