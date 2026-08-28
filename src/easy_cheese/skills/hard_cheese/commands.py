"""Command surface for the hard-cheese application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("append-attempt", "easy_cheese.skills.hard_cheese.append_attempt:main"),
    Command("freshness-check", "easy_cheese.skills.hard_cheese.freshness_check:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)