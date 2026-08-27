"""Command surface for the Pasteurize application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

COMMANDS = {
    "debug-tag-sweep": "easy_cheese.skills.pasteurize.debug_tag_sweep",
    "repro-rerun": "easy_cheese.skills.pasteurize.repro_rerun",
    "pasteurize-route": "easy_cheese.shared.fanout.pasteurize_route_cli",
}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
