"""Command surface for the Easy Cheese setup application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command(
        "global",
        "easy_cheese.shared.hallouminate_setup:global_main",
        "Register or repair the durable Hallouminate corpus",
    ),
    Command(
        "local",
        "easy_cheese.shared.hallouminate_setup:local_main",
        "Register or repair this repository's Hallouminate tenant",
    ),
    Command(
        "doctor",
        "easy_cheese.shared.hallouminate_setup:doctor_main",
        "Run both the global and local registration legs",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)