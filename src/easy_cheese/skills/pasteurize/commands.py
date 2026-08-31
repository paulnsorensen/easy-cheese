"""Command surface for the pasteurize application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("debug-tag-sweep")
def _debug_tag_sweep(argv: list[str]) -> int:
    from easy_cheese.skills.pasteurize.debug_tag_sweep import main

    return main(argv)


@bundle_command("pasteurize-route")
def _pasteurize_route(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.pasteurize_route_cli import main

    return main(argv)


@bundle_command("repro-rerun")
def _repro_rerun(argv: list[str]) -> int:
    from easy_cheese.skills.pasteurize.repro_rerun import main

    return main(argv)


COMMANDS = (
    derive_command(_debug_tag_sweep),
    derive_command(_pasteurize_route),
    derive_command(_repro_rerun),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)