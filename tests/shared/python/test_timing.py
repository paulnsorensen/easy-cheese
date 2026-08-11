"""Tests for the shared workflow-artifact timing helper."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TIMING_CLI = REPO_ROOT / "shared" / "scripts" / "timing.py"


def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TIMING_CLI), *args],
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
    )


def test_now_emits_an_iso_8601_utc_timestamp() -> None:
    result = _run("now")

    assert result.returncode == 0, result.stderr
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n", result.stdout)


def test_render_emits_timestamps_and_phase_timings() -> None:
    result = _run(
        "render",
        stdin=json.dumps(
            {
                "started_at": "2026-08-11T10:00:00-07:00",
                "ended_at": "2026-08-11T17:10:30Z",
                "phases": [
                    {
                        "phase": "total",
                        "duration_ms": 630_000,
                        "attempts": 1,
                        "status": "ok",
                        "notes": "end-to-end handling",
                    },
                    {
                        "phase": "report_write",
                        "duration_ms": 44_000,
                        "items_seen": 8,
                        "items_actionable": 1,
                        "notes": "8 items | no raw output\nkept",
                    },
                ],
            }
        ),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "## Timing\n"
        "\n"
        "- Started: `2026-08-11T17:00:00Z`\n"
        "- Ended: `2026-08-11T17:10:30Z`\n"
        "\n"
        "| Phase | Duration | Attempts | Status | Items | Notes |\n"
        "| --- | ---: | ---: | --- | --- | --- |\n"
        "| total | 10m30s | 1 | ok | - | end-to-end handling |\n"
        "| report_write | 44s | 1 | ok | 8 seen / 1 actionable | "
        "8 items \\| no raw output kept |\n"
    )


def test_render_redacts_common_secret_shapes() -> None:
    result = _run(
        "render",
        stdin=json.dumps(
            {
                "started_at": "2026-08-11T17:00:00Z",
                "ended_at": "2026-08-11T17:00:01Z",
                "phases": [
                    {
                        "phase": "reply_posting",
                        "duration_ms": 1_000,
                        "notes": (
                            "Authorization: token scheme-secret "
                            "GITHUB_TOKEN=env-secret password: colon-secret"
                        ),
                    }
                ],
            }
        ),
    )

    assert result.returncode == 0, result.stderr
    assert "scheme-secret" not in result.stdout
    assert "env-secret" not in result.stdout
    assert "colon-secret" not in result.stdout
    assert "Authorization: token [redacted]" in result.stdout
    assert "GITHUB_TOKEN=[redacted]" in result.stdout
    assert "password: [redacted]" in result.stdout


def test_render_rejects_naive_or_reversed_timestamps() -> None:
    naive = _run(
        "render",
        stdin=json.dumps(
            {
                "started_at": "2026-08-11T17:00:00",
                "ended_at": "2026-08-11T17:00:01Z",
                "phases": [{"phase": "total", "duration_ms": 1_000}],
            }
        ),
    )
    reversed_range = _run(
        "render",
        stdin=json.dumps(
            {
                "started_at": "2026-08-11T17:00:02Z",
                "ended_at": "2026-08-11T17:00:01Z",
                "phases": [{"phase": "total", "duration_ms": 1_000}],
            }
        ),
    )

    assert naive.returncode == 2
    assert "started_at must include a UTC offset" in naive.stderr
    assert reversed_range.returncode == 2
    assert "ended_at must not precede started_at" in reversed_range.stderr
