"""Command surface for the Wheypoint application bundle."""

from __future__ import annotations

import sys

from dataclasses import replace

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("commit")
def _commit(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint.wheypoint import commit_main

    return commit_main(argv)


@bundle_command("resolve")
def _resolve(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint.wheypoint import resolve_main

    return resolve_main(argv)


@bundle_command("show")
def _show(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint.wheypoint import show_main

    return show_main(argv)


@bundle_command("lint")
def _lint(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint.wheypoint import lint_main

    return lint_main(argv)


COMMANDS = (
    replace(
        derive_command(_commit),
        summary="Commit a handoff delta and write the generated projection",
    ),
    replace(
        derive_command(_resolve),
        summary="Resolve a slug, work id, or path to the current record",
    ),
    replace(
        derive_command(_show),
        summary="Print the current record for a work id",
    ),
    replace(
        derive_command(_lint),
        summary="Lint a generated projection against the record",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)