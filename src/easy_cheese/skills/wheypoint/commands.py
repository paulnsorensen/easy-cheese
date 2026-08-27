"""Command surface for the Wheypoint application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

_MODULE = "easy_cheese.skills.wheypoint.wheypoint"
COMMANDS = {name: _MODULE for name in ("commit", "resolve", "show", "lint")}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
