#!/usr/bin/env python3
"""Re-run a repro command N times and emit a structured verdict.

Confirmation-bias killer for /pasteurize: instead of the skill freelancing a
"yes this reproduces" claim from a single observation, this script forces N
actual executions of the supplied shell command and reports the failure
count, so callers can distinguish reproducible failures from flakes.

Output shape:

    {
      "exit_code": int,   # last non-zero exit seen, or 0 if all runs passed
      "reproduced": bool, # any non-zero run
      "runs": int,        # total runs (== --runs)
      "failures": int     # non-zero count
    }

CLI:

    python3 repro-rerun.py --cmd "false" --runs 3 --json
    -> {"exit_code": 1, "reproduced": true, "runs": 3, "failures": 3}
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from typing import TextIO, TypedDict, cast

from easy_cheese.shared import cli  # noqa: E402

DEFAULT_RUNS = 3


class _RerunVerdict(TypedDict):
    exit_code: int
    reproduced: bool
    runs: int
    failures: int


def rerun(cmd: str, runs: int) -> _RerunVerdict:
    """Execute `cmd` (shell expression) `runs` times; aggregate the verdict."""
    last_nonzero = 0
    failures = 0
    for _ in range(runs):
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            failures += 1
            last_nonzero = result.returncode
    return {
        "exit_code": last_nonzero,
        "reproduced": failures > 0,
        "runs": runs,
        "failures": failures,
    }


def _cmd(args: argparse.Namespace) -> None:
    cmd = cast("str | None", args.cmd)
    if not cmd:
        raise cli.CliError("--cmd is required")
    runs = cast(int, args.runs)
    if runs < 1:
        raise cli.CliError(f"--runs must be >= 1, got {runs}")
    verdict = rerun(cmd, runs)
    cli.emit(
        verdict,
        json_mode=cast(bool, args.json_mode),
        stdout=cast(TextIO, args.stdout),
    )


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("--cmd", help="shell expression to re-run")
    _ = parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"number of times to execute --cmd (default {DEFAULT_RUNS})",
    )
    parser.set_defaults(func=_cmd)


def main(argv: list[str] | None = None) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
