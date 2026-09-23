#!/usr/bin/env python3
"""Re-run a reproduction command N times and emit a structured verdict.

Confirmation-bias killer for /pasteurize: instead of the skill freelancing a
"yes this reproduces" claim from a single observation, this script forces N
actual executions of the supplied shell command, matches each run against the
expected failure mode, and reports the match rate against a required
threshold.

A run matches the expected failure mode when every supplied expectation holds:

  * the run exits non-zero, or exits with `--expect-exit` when that is given;
  * the combined stdout and stderr contains `--expect-output` when that regex
    is given.

Output shape:

    {
      "exit_code": int,     # last non-zero exit seen, or 0 if all runs passed
      "reproduced": bool,   # match rate >= threshold
      "runs": int,          # runs actually executed
      "failures": int,      # non-zero exit count
      "matches": int,       # runs matching the expected failure mode
      "timeouts": int,      # runs killed by the per-run timeout
      "threshold": float,   # required match rate
      "results": [          # one record per executed run
        {"exit_code": int, "timed_out": bool, "matched": bool}
      ]
    }

CLI:

    python3 repro-rerun.py --cmd "false" --runs 3 --json
    -> {"exit_code": 1, "reproduced": true, "runs": 3, ...}
"""
from __future__ import annotations

from cyclopts import App, Parameter
import os
import re
import signal
import subprocess
import sys
import time
from typing import Annotated, TypedDict

from easy_cheese.shared import cli  # noqa: E402

DEFAULT_RUNS = 3
# skills/pasteurize/SKILL.md requires a feedback loop under 30 seconds.
DEFAULT_TIMEOUT = 30.0
# skills/pasteurize/SKILL.md requires more than 50 percent reproduction.
DEFAULT_THRESHOLD = 0.5
# Exit code reported for a run that the per-run timeout killed.
TIMEOUT_EXIT_CODE = 124


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


def _kill_group(process: subprocess.Popen[str]) -> None:
    """Terminate the complete child process group of a timed-out run."""
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except OSError:
        process.kill()


def _run_once(cmd: str, timeout: float) -> tuple[int, str, bool]:
    """Execute `cmd` once and return (exit code, combined output, timed out)."""
    process = subprocess.Popen(  # noqa: S602
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(process)
        output, _ = process.communicate()
        return TIMEOUT_EXIT_CODE, output or "", True
    return process.returncode, output or "", False


def _matched_expectation(
    exit_code: int,
    output: str,
    *,
    expect_exit: int | None,
    expect_output: re.Pattern[str] | None,
) -> bool:
    """Report whether one run shows the expected failure mode."""
    if expect_exit is None:
        if exit_code == 0:
            return False
    elif exit_code != expect_exit:
        return False
    if expect_output is not None and not expect_output.search(output):
        return False
    return True


def rerun(
    cmd: str,
    runs: int,
    *,
    expect_exit: int | None = None,
    expect_output: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_seconds: float | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> _RerunVerdict:
    """Execute `cmd` up to `runs` times and aggregate the reproduction verdict."""
    pattern = re.compile(expect_output) if expect_output else None
    budget = max_seconds if max_seconds is not None else timeout * runs
    started = time.monotonic()

    records: list[_RunRecord] = []
    last_nonzero = 0
    failures = 0
    matches = 0
    timeouts = 0

    for _ in range(runs):
        if time.monotonic() - started >= budget:
            break
        exit_code, output, timed_out = _run_once(cmd, timeout)
        matched = _matched_expectation(
            exit_code, output, expect_exit=expect_exit, expect_output=pattern
        )
        if exit_code != 0:
            failures += 1
            last_nonzero = exit_code
        if timed_out:
            timeouts += 1
        if matched:
            matches += 1
        records.append(
            {"exit_code": exit_code, "timed_out": timed_out, "matched": matched}
        )

    executed = len(records)
    rate = matches / executed if executed else 0.0
    return {
        "exit_code": last_nonzero,
        "reproduced": executed > 0 and rate >= threshold,
        "runs": executed,
        "failures": failures,
        "matches": matches,
        "timeouts": timeouts,
        "threshold": threshold,
        "results": records,
    }


def _command(cmd: str | None = None, runs: int = DEFAULT_RUNS, expect_exit: int | None = None, expect_output: str | None = None, timeout: float = DEFAULT_TIMEOUT, max_seconds: float | None = None, threshold: float = DEFAULT_THRESHOLD, json_mode: Annotated[bool, Parameter(name="--json")] = False) -> int:
    if not cmd:
        raise cli.CliError("--cmd is required")
    if runs < 1:
        raise cli.CliError(f"--runs must be >= 1, got {runs}")
    if timeout <= 0:
        raise cli.CliError(f"--timeout must be > 0, got {timeout}")
    if max_seconds is not None and max_seconds <= 0:
        raise cli.CliError(f"--max-seconds must be > 0, got {max_seconds}")
    if not 0.0 <= threshold <= 1.0:
        raise cli.CliError(f"--threshold must be between 0 and 1, got {threshold}")
    if expect_output:
        try:
            _ = re.compile(expect_output)
        except re.error as exc:
            raise cli.CliError(f"--expect-output is not a valid regex: {exc}") from exc
    verdict = rerun(cmd, runs, expect_exit=expect_exit, expect_output=expect_output, timeout=timeout, max_seconds=max_seconds, threshold=threshold)
    cli.emit(verdict, json_mode=json_mode)
    return 0


app = App(name="repro-rerun")
_ = app.default(_command)


def main(argv: list[str] | None = None) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))