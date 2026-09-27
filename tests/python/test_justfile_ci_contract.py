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
def test_check_and_ci_verify_the_wedge_locks() -> None:
    """Both aggregate recipes verify every skill's wedge lock and launcher."""
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

    assert "wedge-check" in dependencies("check")
    assert "wedge-check" in dependencies("ci")


@needs_just
def test_test_recipe_gates_the_runtime_and_builds_archives_once() -> None:
    """The test interpreter carries only the runtime closure; the recipe runs
    the runtime gates, then builds every skill archive once through the pinned
    wedge and exports the set for every suite (scripts/skill_archives.py).
    """
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
    build = justfile.index('scripts/skill_archives.py build "$EASY_CHEESE_PREBUILT_PYZ"')
    suites = justfile.index("-m pytest tests/python")
    assert gates < build < suites
    assert 'export EASY_CHEESE_PREBUILT_PYZ="$prebuilt_pyz_dir"' in justfile


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


def test_validate_workflow_gates_the_runtime_and_builds_archives_once() -> None:
    """validate.yml's test job runs the runtime gates, then builds every skill
    archive once through the pinned wedge and exports the set before any
    pytest suite executes a skill.
    """
    jobs = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        )["jobs"],
    )
    steps = cast(list[dict[str, object]], cast(dict[str, object], jobs["test"])["steps"])
    runs = [cast(str, step["run"]) for step in steps if "run" in step]
    gates = next(i for i, run in enumerate(runs) if "scripts/runtime_gates.py" in run)
    build = next(i for i, run in enumerate(runs) if "scripts/skill_archives.py build" in run)
    suites = [i for i, run in enumerate(runs) if "-m pytest" in run]
    assert suites
    assert gates < build < min(suites)
    assert 'EASY_CHEESE_PREBUILT_PYZ=$RUNNER_TEMP/archives" >> "$GITHUB_ENV"' in runs[build]


def test_wedge_workflow_checks_locks_on_pull_requests_and_publishes_on_main() -> None:
    """wedge.yml verifies every lock on a pull request and publishes archives
    only after a push to main, both through the wedge that tools/wedge pins
    (the pin itself is covered by test_wedge_pin.py).
    """
    jobs = cast(
        dict[str, object],
        yaml.safe_load(
            (ROOT / ".github" / "workflows" / "wedge.yml").read_text(encoding="utf-8")
        )["jobs"],
    )

    def wedge_run(job: str) -> str:
        steps = cast(list[dict[str, object]], cast(dict[str, object], jobs[job])["steps"])
        runs = [cast(str, step["run"]) for step in steps if "run" in step]
        matches = [run for run in runs if "--project tools/wedge wedge" in run]
        assert len(matches) == 1, (job, runs)
        return matches[0]

    assert "wedge check --root skills" in wedge_run("check")
    publish = wedge_run("publish")
    assert "wedge publish" in publish and "--root skills" in publish
    assert "pull_request" in cast(str, cast(dict[str, object], jobs["check"])["if"])
    assert "push" in cast(str, cast(dict[str, object], jobs["publish"])["if"])


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