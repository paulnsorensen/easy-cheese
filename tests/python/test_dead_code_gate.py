"""Vulture dead-code gate: exercises the `just lint-py-dead-code` recipe."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

_needs_just = pytest.mark.skipif(shutil.which("just") is None, reason="just is not installed")


@_needs_just
def test_clean_tree_exits_zero_without_a_probe() -> None:
    result = subprocess.run(
        ["just", "lint-py-dead-code"], cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


@_needs_just
def test_min_confidence_60_finding_fails_the_gate(tmp_path: Path) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(
        "def probe():\n    unused_var = 1\n    return 2\n\nprobe()\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["just", "lint-py-dead-code", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    expected = f"{probe}:2: unused variable 'unused_var' (60% confidence)"
    assert result.returncode == 3 and expected in output, output


def test_lint_job_runs_the_dead_code_recipe() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["lint"]["steps"]
    assert any(step.get("run") == "just lint-py-dead-code" for step in steps), steps