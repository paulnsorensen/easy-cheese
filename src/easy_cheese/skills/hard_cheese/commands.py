"""Command surface for the hard-cheese application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import (
    Command,
    CommandHandler,
    bundle_command,
    derive_command,
    dispatch,
)


@bundle_command("append-attempt")
def _append_attempt(argv: list[str]) -> int:
    from easy_cheese.skills.hard_cheese.append_attempt import main

    return main(argv)


@bundle_command("freshness-check")
def _freshness_check(argv: list[str]) -> int:
    from easy_cheese.skills.hard_cheese.freshness_check import main

    return main(argv)


def _command(handler: CommandHandler, summary: str) -> Command:
    command = derive_command(handler)
    return Command(command.name, command.target, summary)


COMMANDS = (
    _command(
        _append_attempt,
        "Atomically append an attempt row to the audit trail",
    ),
    _command(
        _freshness_check,
        "Decide whether a prior attempt is fresh, stale, or new",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)