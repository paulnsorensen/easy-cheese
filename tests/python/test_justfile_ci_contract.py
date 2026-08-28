"""Contracts for the Just recipes and CI tool pins."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

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
    recipes = json.loads(result.stdout)["recipes"]
    for name in ("check", "ci"):
        dependencies = {
            dependency["recipe"] for dependency in recipes[name]["dependencies"]
        }
        assert "lint-py-dead-code" in dependencies


def test_ci_jobs_pin_tools() -> None:
    """Test and lint jobs pin both uv and just setup actions."""
    jobs = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    )["jobs"]
    for name in ("test", "lint"):
        uses = {
            step["uses"].split("@")[0]: step.get("with", {})
            for step in jobs[name]["steps"]
            if "uses" in step
        }
        assert "version" in uses["astral-sh/setup-uv"]
        assert "just-version" in uses["extractions/setup-just"]