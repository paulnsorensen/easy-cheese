"""Command surface for the Melt application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("batch-resolve", "easy_cheese.skills.melt.batch_resolve:main"),
    Command("conflict-pick", "easy_cheese.skills.melt.conflict_pick:main"),
    Command("conflict-summary", "easy_cheese.skills.melt.conflict_summary:main"),
    Command("detect-squash-residue", "easy_cheese.skills.melt.detect_squash_residue:main"),
    Command("lockfile-resolve", "easy_cheese.skills.melt.lockfile_resolve:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)