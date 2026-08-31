"""Command surface for the Melt application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command(
        "batch-resolve",
        "easy_cheese.skills.melt.batch_resolve:main",
        "Run mergiraf structural merge over every conflicted file",
    ),
    Command(
        "conflict-pick",
        "easy_cheese.skills.melt.conflict_pick:main",
        "Take ours or theirs per conflict hunk",
    ),
    Command(
        "conflict-summary",
        "easy_cheese.skills.melt.conflict_summary:main",
        "Summarize conflicts with line numbers and framed context",
    ),
    Command(
        "detect-squash-residue",
        "easy_cheese.skills.melt.detect_squash_residue:main",
        "Detect squash-merge residue and print both remedies",
    ),
    Command(
        "lockfile-resolve",
        "easy_cheese.skills.melt.lockfile_resolve:main",
        "Take one side of a lockfile conflict and regenerate it",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)