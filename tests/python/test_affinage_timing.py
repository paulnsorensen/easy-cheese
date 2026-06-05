"""Tests for /affinage timing report serialization.

The workflow is instruction-driven, so the bundled helper is the stable contract:
agents can collect phase data however they execute the steps, then render the same
durable Markdown section into `.cheese/affinage/pr-<n>.md`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import build_pyz


def _run_timing(tmp_path: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    source = tmp_path / "timing.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(build_pyz.cached_bundle("affinage")), "timing", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_timing_subcommand_renders_phase_table(tmp_path: Path) -> None:
    result = _run_timing(
        tmp_path,
        {
            "phases": [
                {
                    "phase": "total",
                    "duration_ms": 630_000,
                    "attempts": 1,
                    "status": "ok",
                    "notes": "end-to-end affinage handling",
                },
                {
                    "phase": "comment_intake",
                    "duration_ms": 44_000,
                    "attempts": 1,
                    "items_seen": 8,
                    "items_actionable": 1,
                    "notes": "8 comments/reviews fetched | one actionable\nno raw output",
                },
            ]
        },
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "## Timing\n"
        "\n"
        "| Phase | Duration | Attempts | Status | Items | Notes |\n"
        "| --- | ---: | ---: | --- | --- | --- |\n"
        "| total | 10m30s | 1 | ok | - | end-to-end affinage handling |\n"
        "| comment_intake | 44s | 1 | ok | 8 seen / 1 actionable | "
        "8 comments/reviews fetched \\| one actionable no raw output |\n"
    )


def test_timing_subcommand_keeps_completed_phases_on_halt(tmp_path: Path) -> None:
    result = _run_timing(
        tmp_path,
        {
            "phases": [
                {"phase": "pr_status", "duration_ms": 12_345, "attempts": 2, "status": "ok"},
                {
                    "phase": "comment_intake",
                    "duration_ms": 900,
                    "attempts": 1,
                    "status": "halt: pr-status-unavailable",
                    "notes": "gh failed before grading",
                },
            ]
        },
    )

    assert result.returncode == 0, result.stderr
    assert "| pr_status | 12s | 2 | ok | - | - |" in result.stdout
    assert "| comment_intake | 900ms | 1 | halt: pr-status-unavailable | - | gh failed before grading |" in result.stdout


def test_timing_subcommand_redacts_common_secret_shapes(tmp_path: Path) -> None:
    result = _run_timing(
        tmp_path,
        {
            "phases": [
                {
                    "phase": "reply_posting",
                    "duration_ms": 1_000,
                    "notes": "Authorization: Bearer ghp_secret token=abc123 api_key=def456",
                }
            ]
        },
    )

    assert result.returncode == 0, result.stderr
    assert "ghp_secret" not in result.stdout
    assert "abc123" not in result.stdout
    assert "def456" not in result.stdout
    assert "Authorization: Bearer [redacted]" in result.stdout
    assert "token=[redacted]" in result.stdout
    assert "api_key=[redacted]" in result.stdout


def test_timing_subcommand_rejects_empty_phase_list(tmp_path: Path) -> None:
    result = _run_timing(tmp_path, {"phases": []})

    assert result.returncode == 1
    assert "phases list must not be empty" in result.stderr
