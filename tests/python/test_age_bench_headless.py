"""CLI contract tests for the age-bench headless `run` command.

Spec: age-fanout-mechanics-benchmark.md, AC-10, curd/4.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import cast

from _age_bench_helpers import run_cli  # pyright: ignore[reportImplicitRelativeImport]

SRC = Path(__file__).resolve().parents[2] / "src"
CASE_ID = "off-by-one-window-sum"

_FAKE_CLAUDE_NO_FINDINGS = """#!/usr/bin/env python3
print("No findings.")
"""

_FAKE_CLAUDE_WITH_FINDING = """#!/usr/bin/env python3
print("## High")
print("- **[correctness:high]** `src/app.py:42` — the retry loop never resets the backoff.")
"""

_FAKE_CLAUDE_WRITES_REPORT_FILE = """#!/usr/bin/env python3
import pathlib
report_dir = pathlib.Path(".cheese/age")
report_dir.mkdir(parents=True, exist_ok=True)
report_path = report_dir / "test-slug.md"
report_path.write_text(
    "## High\\n"
    "- **[correctness:high]** `src/app.py:42` — the retry loop never resets the backoff.\\n",
    encoding="utf-8",
)
print(f"Age report: {report_path}")
"""


def _base_env(*, path: str) -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(SRC), "PATH": path}


def _write_fake_claude(tmp_path: Path, script: str) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_claude = fake_bin / "claude"
    _ = fake_claude.write_text(script, encoding="utf-8")
    fake_claude.chmod(fake_claude.stat().st_mode | stat.S_IEXEC)
    return fake_bin


def test_run_exits_non_zero_with_a_named_reason_when_the_report_has_no_findings(
    tmp_path: Path,
) -> None:
    fake_bin = _write_fake_claude(tmp_path, _FAKE_CLAUDE_NO_FINDINGS)

    env = _base_env(path=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    result = run_cli(["run", "--tool", "age", "--case", CASE_ID], env=env)

    assert result.returncode != 0
    assert "no parseable findings" in result.stderr


def test_run_judges_a_findings_bearing_headless_report(tmp_path: Path) -> None:
    fake_bin = _write_fake_claude(tmp_path, _FAKE_CLAUDE_WITH_FINDING)

    fixture_path = tmp_path / "transport-fixture.json"
    _ = fixture_path.write_text(json.dumps(["Bug Hit"]), encoding="utf-8")

    env = _base_env(path=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    result = run_cli(
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
    payload = cast("dict[str, object]", json.loads(result.stdout))
    assert payload["case_id"] == CASE_ID
    assert payload["tool"] == "age"
    assert payload["buckets"] == ["Bug Hit"]
    assert payload["hits"] == 1
    assert payload["recall"] == 1.0


def test_run_reads_the_report_file_when_headless_prints_only_its_path(
    tmp_path: Path,
) -> None:
    fake_bin = _write_fake_claude(tmp_path, _FAKE_CLAUDE_WRITES_REPORT_FILE)

    fixture_path = tmp_path / "transport-fixture.json"
    _ = fixture_path.write_text(json.dumps(["Bug Hit"]), encoding="utf-8")

    env = _base_env(path=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    result = run_cli(
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
    payload = cast("dict[str, object]", json.loads(result.stdout))
    assert payload["buckets"] == ["Bug Hit"]
    assert payload["hits"] == 1
    assert payload["recall"] == 1.0


def test_run_exits_non_zero_with_a_named_reason_when_headless_is_unavailable(
    tmp_path: Path,
) -> None:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()

    env = _base_env(path=str(empty_bin))
    result = run_cli(["run", "--tool", "age", "--case", CASE_ID], env=env)

    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "claude" in result.stderr
    assert "not found on PATH" in result.stderr
