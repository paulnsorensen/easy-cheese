"""Command surface for the Wheypoint application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command(
        "commit",
        "easy_cheese.skills.wheypoint.wheypoint:commit_main",
        "Commit a handoff delta and write the generated projection",
    ),
    Command(
        "resolve",
        "easy_cheese.skills.wheypoint.wheypoint:resolve_main",
        "Resolve a slug, work id, or path to the current record",
    ),
    Command(
        "show",
        "easy_cheese.skills.wheypoint.wheypoint:show_main",
        "Print the current record for a work id",
    ),
    Command(
        "lint",
        "easy_cheese.skills.wheypoint.wheypoint:lint_main",
        "Lint a generated projection against the record",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)