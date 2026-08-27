"""Command surface for the Cut application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

COMMANDS = {"red-gate": "easy_cheese.shared.cut.red_gate"}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
