"""Command surface for the pasteurize application bundle."""

from __future__ import annotations

import sys
from dataclasses import replace

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
    replace(
        derive_command(_debug_tag_sweep),
        summary="Scan a tree for surviving instrumentation tags",
    ),
    replace(
        derive_command(_pasteurize_route),
        summary="Size a /pasteurize investigation into fan-out lanes (JSON in, JSON out)",
    ),
    replace(
        derive_command(_repro_rerun),
        summary="Re-run a repro command N times and emit a structured verdict",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)