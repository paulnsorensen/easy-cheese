"""Command surface for the age-bench skill."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("prepare")
def _prepare(argv: list[str]) -> int:
    from easy_cheese.skills.age_bench.prepare import main

    return main(argv)


@bundle_command("judge")
def _judge(argv: list[str]) -> int:
    from easy_cheese.skills.age_bench.judge import main

    return main(argv)


@bundle_command("scoreboard")
def _scoreboard(argv: list[str]) -> int:
    from easy_cheese.skills.age_bench.scoreboard import main

    return main(argv)


COMMANDS = (
    derive_command(
        _prepare,
        "Seed an isolated git worktree for a benchmark case and print the two review commands",
    ),
    derive_command(
        _judge,
        "Bucket a captured review report's findings against a case's expected defect and emit recall/precision/SNR",
    ),
    derive_command(
        _scoreboard, "Write a per-overlap-area scoreboard table for a benchmark run"
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)
