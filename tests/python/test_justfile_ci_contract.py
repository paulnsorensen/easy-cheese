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