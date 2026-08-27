"""Command surface for the Melt application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

COMMANDS = {
    "batch-resolve": "easy_cheese.skills.melt.batch_resolve",
    "conflict-pick": "easy_cheese.skills.melt.conflict_pick",
    "conflict-summary": "easy_cheese.skills.melt.conflict_summary",
    "detect-squash-residue": "easy_cheese.skills.melt.detect_squash_residue",
    "lockfile-resolve": "easy_cheese.skills.melt.lockfile_resolve",
}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
