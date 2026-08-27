"""Command surface for the Hard Cheese application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

COMMANDS = {
    "append-attempt": "easy_cheese.skills.hard_cheese.append_attempt",
    "freshness-check": "easy_cheese.skills.hard_cheese.freshness_check",
}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
