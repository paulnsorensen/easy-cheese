"""Command surface for the Melt application bundle."""

from __future__ import annotations

import sys
from dataclasses import replace

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("batch-resolve")
def _batch_resolve(argv: list[str]) -> int:
    from easy_cheese.skills.melt.batch_resolve import main

    return main(argv)


@bundle_command("conflict-pick")
def _conflict_pick(argv: list[str]) -> int:
    from easy_cheese.skills.melt.conflict_pick import main

    return main(argv)


@bundle_command("conflict-summary")
def _conflict_summary(argv: list[str]) -> int:
    from easy_cheese.skills.melt.conflict_summary import main

    return main(argv)


@bundle_command("detect-squash-residue")
def _detect_squash_residue(argv: list[str]) -> int:
    from easy_cheese.skills.melt.detect_squash_residue import main

    return main(argv)


@bundle_command("lockfile-resolve")
def _lockfile_resolve(argv: list[str]) -> int:
    from easy_cheese.skills.melt.lockfile_resolve import main

    return main(argv)


COMMANDS = (
    replace(
        derive_command(_batch_resolve),
        summary="Run mergiraf structural merge over every conflicted file",
    ),
    replace(
        derive_command(_conflict_pick),
        summary="Take ours or theirs for each conflict hunk",
    ),
    replace(
        derive_command(_conflict_summary),
        summary="Summarize conflicts with line numbers and framed context",
    ),
    replace(
        derive_command(_detect_squash_residue),
        summary="Detect squash-merge residue and print both remedies",
    ),
    replace(
        derive_command(_lockfile_resolve),
        summary="Take one side of a lockfile conflict and regenerate it",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)