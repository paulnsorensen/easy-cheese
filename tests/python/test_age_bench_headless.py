"""CLI contract tests for the age-bench headless `run` command.

Spec: age-fanout-mechanics-benchmark.md, AC-10, curd/4.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
CASE_ID = "off-by-one-window-sum"

_DRIVER = (
    "from easy_cheese.skills.age_bench.commands import main;"
    "import sys;"
    "sys.exit(main(sys.argv[1:]))"
)

_FAKE_CLAUDE = """#!/usr/bin/env python3
import sys
print("No findings.")
"""

_FAKE_CLAUDE_WITH_FINDING = """#!/usr/bin/env python3
import sys
print("## High")
print("- **[correctness:high]** `src/app.py:42` — the retry loop never resets the backoff.")
"""


def _run_cli(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _DRIVER, *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _base_env(*, path: str) -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(SRC), "PATH": path}


def test_run_drives_the_review_and_hands_the_report_to_judge(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    fake_claude.write_text(_FAKE_CLAUDE, encoding="utf-8")
    fake_claude.chmod(fake_claude.stat().st_mode | stat.S_IEXEC)

    env = _base_env(path=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    result = _run_cli(["run", "--tool", "age", "--case", CASE_ID], env=env)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["case_id"] == CASE_ID
    assert payload["tool"] == "age"
    assert payload["buckets"] == []
    assert payload["recall"] == 0.0


def test_run_judges_a_findings_bearing_headless_report(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    fake_claude.write_text(_FAKE_CLAUDE_WITH_FINDING, encoding="utf-8")
    fake_claude.chmod(fake_claude.stat().st_mode | stat.S_IEXEC)

    fixture_path = tmp_path / "transport-fixture.json"
    fixture_path.write_text(json.dumps(["Bug Hit"]), encoding="utf-8")

    env = _base_env(path=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    result = _run_cli(
        [
            "run",
            "--tool",
            "age",
            "--case",
            CASE_ID,
            "--transport-fixture",
            str(fixture_path),
        ],
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["case_id"] == CASE_ID
    assert payload["tool"] == "age"
    assert payload["buckets"] == ["Bug Hit"]
    assert payload["hits"] == 1
    assert payload["recall"] == 1.0


def test_run_exits_non_zero_with_a_named_reason_when_headless_is_unavailable(tmp_path):
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()

    env = _base_env(path=str(empty_bin))
    result = _run_cli(["run", "--tool", "age", "--case", CASE_ID], env=env)

    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "claude" in result.stderr
    assert "not found on PATH" in result.stderr
