"""Tests for skills/pasteurize/scripts/repro-rerun.py — N-run reproducibility verdict."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import build_pyz  # noqa: E402

BUNDLE = build_pyz.cached_bundle("pasteurize")


class TestRerunFunction:
    def test_reproducible_failure(self, repro_rerun: ModuleType) -> None:
        verdict = repro_rerun.rerun("false", 3)
        assert verdict == {
            "exit_code": 1,
            "reproduced": True,
            "runs": 3,
            "failures": 3,
        }

    def test_non_reproducible(self, repro_rerun: ModuleType) -> None:
        verdict = repro_rerun.rerun("true", 3)
        assert verdict == {
            "exit_code": 0,
            "reproduced": False,
            "runs": 3,
            "failures": 0,
        }

    def test_mixed_first_run_fails(self, repro_rerun: ModuleType, tmp_path: Path) -> None:
        # Counter file: fails on first invocation, passes thereafter. This
        # exercises the flake-vs-repro distinction without relying on $RANDOM.
        counter = tmp_path / "n"
        # Bash arithmetic: read N (default 0), increment, write back, exit 1 iff N==0.
        cmd = (
            f'N=$(cat {counter} 2>/dev/null || echo 0); '
            f'echo $((N+1)) > {counter}; '
            f'[ "$N" = "0" ] && exit 7 || exit 0'
        )
        verdict = repro_rerun.rerun(cmd, 3)
        assert verdict["runs"] == 3
        assert verdict["failures"] == 1
        assert verdict["reproduced"] is True
        # last non-zero exit code was 7 (first run), and that's what we report
        # because no later run produced a non-zero exit to overwrite it.
        assert verdict["exit_code"] == 7

    def test_last_nonzero_wins_when_multiple_failures(
        self, repro_rerun: ModuleType, tmp_path: Path
    ) -> None:
        # First run exits 3, second exits 0, third exits 9 -> we report 9.
        counter = tmp_path / "n"
        cmd = (
            f'N=$(cat {counter} 2>/dev/null || echo 0); '
            f'echo $((N+1)) > {counter}; '
            f'case "$N" in 0) exit 3 ;; 1) exit 0 ;; 2) exit 9 ;; *) exit 0 ;; esac'
        )
        verdict = repro_rerun.rerun(cmd, 3)
        assert verdict["failures"] == 2
        assert verdict["exit_code"] == 9

    def test_runs_override_one(self, repro_rerun: ModuleType) -> None:
        verdict = repro_rerun.rerun("false", 1)
        assert verdict["runs"] == 1
        assert verdict["failures"] == 1

    def test_runs_override_five(self, repro_rerun: ModuleType) -> None:
        verdict = repro_rerun.rerun("true", 5)
        assert verdict["runs"] == 5
        assert verdict["failures"] == 0


def _invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "repro-rerun", *args],
        capture_output=True,
        text=True,
    )


class TestCli:
    def test_default_runs_is_three(self) -> None:
        result = _invoke("--cmd", "false", "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["runs"] == 3

    def test_json_shape_reproducible(self) -> None:
        result = _invoke("--cmd", "false", "--runs", "3", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "exit_code": 1,
            "reproduced": True,
            "runs": 3,
            "failures": 3,
        }

    def test_json_shape_non_reproducible(self) -> None:
        result = _invoke("--cmd", "true", "--runs", "3", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "exit_code": 0,
            "reproduced": False,
            "runs": 3,
            "failures": 0,
        }

    def test_dict_emitted_as_json_even_without_flag(self) -> None:
        # cli.emit always serializes dicts as JSON, so --json is decorative
        # for this script — verify the contract anyway.
        result = _invoke("--cmd", "true", "--runs", "1")
        assert result.returncode == 0
        assert json.loads(result.stdout)["runs"] == 1

    def test_runs_override(self) -> None:
        result = _invoke("--cmd", "false", "--runs", "5", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["runs"] == 5
        assert json.loads(result.stdout)["failures"] == 5

    def test_missing_cmd_exits_two(self) -> None:
        result = _invoke()
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:")
        assert "--cmd" in result.stderr

    def test_empty_cmd_exits_two(self) -> None:
        # Explicit empty string is still missing.
        result = _invoke("--cmd", "")
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:")

    def test_zero_runs_rejected(self) -> None:
        result = _invoke("--cmd", "true", "--runs", "0")
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:")

    def test_help_exits_zero(self) -> None:
        result = _invoke("--help")
        assert result.returncode == 0
        assert "--cmd" in result.stdout
        assert "--runs" in result.stdout
