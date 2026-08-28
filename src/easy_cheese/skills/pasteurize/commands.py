"""Command surface for the pasteurize application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("debug-tag-sweep", "easy_cheese.skills.pasteurize.debug_tag_sweep:main"),
    Command(
        "pasteurize-route",
        "easy_cheese.shared.fanout.pasteurize_route_cli:main",
    ),
    Command("repro-rerun", "easy_cheese.skills.pasteurize.repro_rerun:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)