"""Tests for shared/gates.py's classify CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast


from easy_cheese.shared.gates import classify

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "src" / "easy_cheese" / "shared"
GATES_CLI_PATH = SHARED_SCRIPTS / "gates.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATES_CLI_PATH), *args],
        capture_output=True,
        text=True,
    )


class TestClassifyHappyPath:
    def test_clean_floor_no_gaps_is_ready(self) -> None:
        result = _run("classify", "--press-status", "ready-for-age", "--hard-floor-met")
        assert result.returncode == 0, result.stderr
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload == {"press_status": "ready-for-age", "readiness": "ready for /age"}

    def test_level_4_or_5_only_means_follow_up(self) -> None:
        result = _run(
            "classify",
            "--press-status",
            "soft-only",
            "--hard-floor-met",
            "--has-open-level-4-or-5",
        )
        assert result.returncode == 0, result.stderr
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload["readiness"] == "follow-up recommended"

    def test_open_level_1_or_2_blocks(self) -> None:
        result = _run(
            "classify",
            "--press-status",
            "hard-broken",
            "--hard-floor-met",
            "--has-open-level-1-or-2",
        )
        assert result.returncode == 0, result.stderr
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload["readiness"] == "blocked"

    def test_missing_press_status_exits_two(self) -> None:
        result = _run("classify", "--hard-floor-met")
        assert result.returncode == 2
        payload = cast("dict[str, object]", json.loads(result.stderr))
        assert "press-status" in str(payload["error"]).lower() or "press_status" in str(payload["error"]).lower()


class TestJsonMode:
    def test_classify_default_dict_emit_is_json(self) -> None:
        result = _run("classify", "--press-status", "ready-for-age", "--hard-floor-met")
        assert result.returncode == 0
        json.loads(result.stdout)


class TestInvalidInput:
    def test_unknown_subcommand_exits_two(self) -> None:
        result = _run("frobnicate")
        assert result.returncode == 2

    def test_missing_subcommand_exits_two(self) -> None:
        result = _run()
        assert result.returncode == 2


class TestInProcessClassify:
    def test_classify_helper_returns_dict(self) -> None:
        payload = classify(press_status="ready-for-age", hard_floor_met=True)
        assert payload == {"press_status": "ready-for-age", "readiness": "ready for /age"}