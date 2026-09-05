"""Tests for the /pasteurize repro-rerun command — the N-run reproduction verdict.

The verdict must confirm the *expected* failure mode, not any failure, and it
must stop a hung reproduction command. See
`.cheese/notes/r014-megamerge/review-pasteurize.md` and
`.cheese/notes/r014-megamerge/edge-affinage-pasteurize.md`.

The bundle-level tests keep shape-agnostic assertions on purpose: this worktree
never rebuilds `pasteurize.pyz`, so the archive can lag the source until the
integration barrier rebuilds it. Strict contract coverage runs against the
module and its in-process `main()`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol, TypedDict, cast

import pytest


class _RunRecord(TypedDict):
    exit_code: int
    timed_out: bool
    matched: bool


class _RerunVerdict(TypedDict):
    exit_code: int
    reproduced: bool
    runs: int
    failures: int
    matches: int
    timeouts: int
    threshold: float
    results: list[_RunRecord]


class _ReproRerunModule(Protocol):
    DEFAULT_THRESHOLD: float
    TIMEOUT_EXIT_CODE: int

    def rerun(
        self,
        cmd: str,
        runs: int,
        *,
        expect_exit: int | None = None,
        expect_output: str | None = None,
        timeout: float = ...,
        max_seconds: float | None = None,
        threshold: float = ...,
    ) -> _RerunVerdict: ...

    def main(self, argv: list[str] | None = None) -> int: ...

BUNDLE = Path(__file__).resolve().parents[3] / "skills/pasteurize/scripts/pasteurize.pyz"


def _flake_command(counter: Path, failing_runs: int) -> str:
    """Build a shell expression that exits 7 for the first `failing_runs` calls."""
    return (
        f'N=$(cat {counter} 2>/dev/null || echo 0); '
        f'echo $((N+1)) > {counter}; '
        f'[ "$N" -lt "{failing_runs}" ] && exit 7 || exit 0'
    )


class TestRerunFunction:
    def test_reproducible_failure(self, repro_rerun: _ReproRerunModule) -> None:
        verdict = repro_rerun.rerun("false", 3)
        assert verdict["exit_code"] == 1
        assert verdict["reproduced"] is True
        assert verdict["runs"] == 3
        assert verdict["failures"] == 3
        assert verdict["matches"] == 3
        assert verdict["timeouts"] == 0
        assert verdict["results"] == [
            {"exit_code": 1, "timed_out": False, "matched": True}
        ] * 3

    def test_non_reproducible(self, repro_rerun: _ReproRerunModule) -> None:
        verdict = repro_rerun.rerun("true", 3)
        assert verdict["exit_code"] == 0
        assert verdict["reproduced"] is False
        assert verdict["failures"] == 0
        assert verdict["matches"] == 0

    def test_last_nonzero_wins_when_multiple_failures(
        self, repro_rerun: _ReproRerunModule, tmp_path: Path
    ) -> None:
        counter = tmp_path / "n"
        cmd = (
            f'N=$(cat {counter} 2>/dev/null || echo 0); '
            f'echo $((N+1)) > {counter}; '
            f'case "$N" in 0) exit 3 ;; 1) exit 0 ;; 2) exit 9 ;; *) exit 0 ;; esac'
        )
        verdict = repro_rerun.rerun(cmd, 3)
        assert verdict["failures"] == 2
        assert verdict["exit_code"] == 9

    def test_runs_override_one(self, repro_rerun: _ReproRerunModule) -> None:
        verdict = repro_rerun.rerun("false", 1)
        assert verdict["runs"] == 1
        assert verdict["failures"] == 1

    def test_runs_override_five(self, repro_rerun: _ReproRerunModule) -> None:
        verdict = repro_rerun.rerun("true", 5)
        assert verdict["runs"] == 5
        assert verdict["failures"] == 0


class TestExpectedFailureMode:
    """Regression: an unrelated failure must not report `reproduced: true`."""

    def test_wrong_output_is_not_reproduced(
        self, repro_rerun: _ReproRerunModule
    ) -> None:
        verdict = repro_rerun.rerun(
            "echo 'wrong failure'; exit 1", 3, expect_output="cache race"
        )
        assert verdict["failures"] == 3
        assert verdict["matches"] == 0
        assert verdict["reproduced"] is False
        assert [record["matched"] for record in verdict["results"]] == [False] * 3

    def test_expected_output_is_reproduced(
        self, repro_rerun: _ReproRerunModule
    ) -> None:
        verdict = repro_rerun.rerun(
            "echo 'cache race detected'; exit 1", 3, expect_output="cache race"
        )
        assert verdict["matches"] == 3
        assert verdict["reproduced"] is True

    def test_expected_output_matches_stderr(
        self, repro_rerun: _ReproRerunModule
    ) -> None:
        verdict = repro_rerun.rerun(
            "echo 'cache race detected' >&2; exit 1", 1, expect_output="cache race"
        )
        assert verdict["matches"] == 1

    def test_wrong_exit_code_is_not_reproduced(
        self, repro_rerun: _ReproRerunModule
    ) -> None:
        verdict = repro_rerun.rerun("exit 2", 3, expect_exit=7)
        assert verdict["failures"] == 3
        assert verdict["matches"] == 0
        assert verdict["reproduced"] is False

    def test_expected_exit_code_is_reproduced(
        self, repro_rerun: _ReproRerunModule
    ) -> None:
        verdict = repro_rerun.rerun("exit 7", 3, expect_exit=7)
        assert verdict["matches"] == 3
        assert verdict["reproduced"] is True

    def test_expected_exit_zero_can_be_the_symptom(
        self, repro_rerun: _ReproRerunModule
    ) -> None:
        verdict = repro_rerun.rerun("true", 2, expect_exit=0)
        assert verdict["matches"] == 2
        assert verdict["failures"] == 0


class TestThreshold:
    """Regression: a flake below the threshold is not a reproduction."""

    def test_default_threshold_rejects_a_one_in_three_flake(
        self, repro_rerun: _ReproRerunModule, tmp_path: Path
    ) -> None:
        verdict = repro_rerun.rerun(_flake_command(tmp_path / "n", 1), 3)
        assert verdict["matches"] == 1
        assert verdict["threshold"] == repro_rerun.DEFAULT_THRESHOLD
        assert verdict["reproduced"] is False

    def test_lower_threshold_accepts_the_same_flake(
        self, repro_rerun: _ReproRerunModule, tmp_path: Path
    ) -> None:
        verdict = repro_rerun.rerun(
            _flake_command(tmp_path / "n", 1), 3, threshold=0.3
        )
        assert verdict["matches"] == 1
        assert verdict["reproduced"] is True

    def test_two_in_three_meets_the_default_threshold(
        self, repro_rerun: _ReproRerunModule, tmp_path: Path
    ) -> None:
        verdict = repro_rerun.rerun(_flake_command(tmp_path / "n", 2), 3)
        assert verdict["matches"] == 2
        assert verdict["reproduced"] is True


class TestTimeout:
    """Regression: a hung reproduction command must not block the phase."""

    def test_per_run_timeout_kills_a_hung_command(
        self, repro_rerun: _ReproRerunModule
    ) -> None:
        started = time.monotonic()
        verdict = repro_rerun.rerun("sleep 30", 2, timeout=0.5)
        elapsed = time.monotonic() - started
        assert elapsed < 10
        assert verdict["timeouts"] == 2
        assert verdict["exit_code"] == repro_rerun.TIMEOUT_EXIT_CODE
        assert all(record["timed_out"] for record in verdict["results"])

    def test_timeout_kills_the_complete_process_group(
        self, repro_rerun: _ReproRerunModule, tmp_path: Path
    ) -> None:
        marker = tmp_path / "child-survived"
        cmd = f"(sleep 2; touch {marker}) & sleep 30"
        verdict = repro_rerun.rerun(cmd, 1, timeout=0.5)
        assert verdict["timeouts"] == 1
        time.sleep(3)
        assert not marker.exists(), "the timeout left an orphaned grandchild running"

    def test_overall_limit_stops_further_runs(
        self, repro_rerun: _ReproRerunModule
    ) -> None:
        started = time.monotonic()
        verdict = repro_rerun.rerun("sleep 30", 5, timeout=0.5, max_seconds=1.2)
        elapsed = time.monotonic() - started
        assert elapsed < 10
        assert verdict["runs"] < 5


class TestMainCli:
    """Cover the argument surface in process, against the current source."""

    def _run(
        self,
        repro_rerun: _ReproRerunModule,
        capsys: pytest.CaptureFixture[str],
        *args: str,
    ) -> tuple[int, _RerunVerdict | None, str]:
        code = repro_rerun.main(list(args))
        captured = capsys.readouterr()
        payload: _RerunVerdict | None = None
        if captured.out.strip():
            payload = cast(_RerunVerdict, json.loads(captured.out))
        return code, payload, captured.err

    def test_expect_output_reaches_the_verdict(
        self, repro_rerun: _ReproRerunModule, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, payload, _ = self._run(
            repro_rerun,
            capsys,
            "--cmd",
            "echo 'wrong failure'; exit 1",
            "--runs",
            "2",
            "--expect-output",
            "cache race",
            "--json",
        )
        assert code == 0
        assert payload is not None
        assert payload["reproduced"] is False
        assert payload["matches"] == 0

    def test_expect_exit_reaches_the_verdict(
        self, repro_rerun: _ReproRerunModule, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _, payload, _ = self._run(
            repro_rerun, capsys, "--cmd", "exit 7", "--expect-exit", "7", "--json"
        )
        assert payload is not None
        assert payload["reproduced"] is True

    def test_threshold_reaches_the_verdict(
        self, repro_rerun: _ReproRerunModule, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _, payload, _ = self._run(
            repro_rerun, capsys, "--cmd", "false", "--threshold", "1.0", "--json"
        )
        assert payload is not None
        assert payload["threshold"] == 1.0

    def test_timeout_reaches_the_verdict(
        self, repro_rerun: _ReproRerunModule, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _, payload, _ = self._run(
            repro_rerun,
            capsys,
            "--cmd",
            "sleep 30",
            "--runs",
            "1",
            "--timeout",
            "0.5",
            "--json",
        )
        assert payload is not None
        assert payload["timeouts"] == 1

    @pytest.mark.parametrize(
        "args",
        [
            ["--cmd", "true", "--timeout", "0"],
            ["--cmd", "true", "--max-seconds", "0"],
            ["--cmd", "true", "--threshold", "1.5"],
            ["--cmd", "true", "--expect-output", "(["],
        ],
    )
    def test_invalid_argument_exits_two(
        self,
        repro_rerun: _ReproRerunModule,
        capsys: pytest.CaptureFixture[str],
        args: list[str],
    ) -> None:
        code, _, err = self._run(repro_rerun, capsys, *args)
        assert code == 2
        assert err.startswith("ERROR:")


def _invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "repro-rerun", *args],
        capture_output=True,
        text=True,
    )


class TestBundleCli:
    def test_default_runs_is_three(self) -> None:
        result = _invoke("--cmd", "false", "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload["runs"] == 3

    def test_reproducible_command(self) -> None:
        result = _invoke("--cmd", "false", "--runs", "3", "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload["exit_code"] == 1
        assert payload["reproduced"] is True
        assert payload["failures"] == 3

    def test_non_reproducible_command(self) -> None:
        result = _invoke("--cmd", "true", "--runs", "3", "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload["exit_code"] == 0
        assert payload["reproduced"] is False
        assert payload["failures"] == 0

    def test_dict_emitted_as_json_even_without_flag(self) -> None:
        result = _invoke("--cmd", "true", "--runs", "1")
        assert result.returncode == 0
        assert cast(dict[str, object], json.loads(result.stdout))["runs"] == 1

    def test_runs_override(self) -> None:
        result = _invoke("--cmd", "false", "--runs", "5", "--json")
        assert result.returncode == 0
        payload = cast(dict[str, object], json.loads(result.stdout))
        assert payload["runs"] == 5
        assert payload["failures"] == 5

    def test_missing_cmd_exits_two(self) -> None:
        result = _invoke()
        assert result.returncode == 2
        assert result.stderr.startswith("ERROR:")
        assert "--cmd" in result.stderr

    def test_empty_cmd_exits_two(self) -> None:
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
