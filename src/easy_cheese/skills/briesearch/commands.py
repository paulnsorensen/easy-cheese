"""Command surface for the Briesearch application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("artifact-path", "easy_cheese.shared.artifact_path:main"),
    Command("ground-check", "easy_cheese.skills.briesearch.ground_check:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)