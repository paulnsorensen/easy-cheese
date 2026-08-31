"""Command surface for the Press application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command(
        "press-route",
        "easy_cheese.shared.fanout.press_route_cli:main",
        "Decide whether Press continues or stops (JSON in, JSON out)",
    ),
    Command("press-telemetry", "easy_cheese.shared.fanout.press_telemetry_cli:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)