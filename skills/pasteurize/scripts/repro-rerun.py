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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared" / "scripts"))
import cli  # noqa: E402

DEFAULT_RUNS = 3


def rerun(cmd: str, runs: int) -> dict:
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
    if not args.cmd:
        raise cli.CliError("--cmd is required")
    if args.runs < 1:
        raise cli.CliError(f"--runs must be >= 1, got {args.runs}")
    verdict = rerun(args.cmd, args.runs)
    cli.emit(verdict, json_mode=args.json_mode)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cmd", help="shell expression to re-run")
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"number of times to execute --cmd (default {DEFAULT_RUNS})",
    )
    parser.set_defaults(func=_cmd)


if __name__ == "__main__":
    cli.run(_setup)
