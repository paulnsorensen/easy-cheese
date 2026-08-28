"""Command surface for the Wheypoint application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("commit", "easy_cheese.skills.wheypoint.wheypoint:commit_main"),
    Command("resolve", "easy_cheese.skills.wheypoint.wheypoint:resolve_main"),
    Command("show", "easy_cheese.skills.wheypoint.wheypoint:show_main"),
    Command("lint", "easy_cheese.skills.wheypoint.wheypoint:lint_main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)