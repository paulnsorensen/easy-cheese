"""Command surface for the hard-cheese application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import (
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


COMMANDS = (
    derive_command(
        _append_attempt, "Atomically append an attempt row to the audit trail"
    ),
    derive_command(
        _freshness_check, "Decide whether a prior attempt is fresh, stale, or new"
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)
