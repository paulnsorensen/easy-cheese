"""Command surface for the pasteurize application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command(
        "debug-tag-sweep",
        "easy_cheese.skills.pasteurize.debug_tag_sweep:main",
        "Scan a tree for surviving instrumentation tags",
    ),
    Command(
        "pasteurize-route",
        "easy_cheese.shared.fanout.pasteurize_route_cli:main",
        "Size a /pasteurize investigation into fan-out lanes (JSON in, JSON out)",
    ),
    Command(
        "repro-rerun",
        "easy_cheese.skills.pasteurize.repro_rerun:main",
        "Re-run a repro command N times and emit a structured verdict",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)