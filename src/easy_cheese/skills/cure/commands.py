"""Command surface for the Cure application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("slugify", "easy_cheese.shared.slugify:main"),
    Command("write-handoff-artifact", "easy_cheese.shared.write_handoff_artifact:main"),
    Command("read-handoff-slug", "easy_cheese.shared.read_handoff_slug:main"),
    Command("findings-cli", "easy_cheese.shared.findings_cli:main"),
    Command("gates-cli", "easy_cheese.shared.gates_cli:main"),
    Command("paths-cli", "easy_cheese.shared.paths_cli:main"),
    Command("handoff-cli", "easy_cheese.shared.handoff_cli:main"),
    Command("render-html", "easy_cheese.shared.html_report_cli:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)