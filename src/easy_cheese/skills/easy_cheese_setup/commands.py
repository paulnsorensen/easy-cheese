"""Command surface for the Easy Cheese setup application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = tuple(
    Command(name, f"easy_cheese.shared.hallouminate_setup:{name}_main")
    for name in ("global", "local", "doctor")
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)