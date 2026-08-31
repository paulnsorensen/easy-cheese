"""Command surface for the Plate application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command(
        "stack-tools",
        "easy_cheese.skills.plate.stack_tools:main",
        "Detect supported stacked-PR providers without mutating the repo",
    ),
    Command(
        "validate-publication",
        "easy_cheese.skills.plate.publication:main",
        "Validate terminal publication evidence",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)