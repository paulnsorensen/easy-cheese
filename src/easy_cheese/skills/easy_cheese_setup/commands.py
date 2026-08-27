"""Command surface for the Easy Cheese setup application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

_MODULE = "easy_cheese.shared.hallouminate_setup"
COMMANDS = {name: _MODULE for name in ("global", "local", "doctor")}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
