"""Command surface for the pasteurize application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared import bundle_commands
from easy_cheese.shared.fanout import pasteurize_route_cli

from . import debug_tag_sweep, repro_rerun


@bundle_commands.bundle_command("debug-tag-sweep")
def run_debug_tag_sweep(argv: list[str]) -> int:
    """Scan the tree for instrumentation tags."""
    return debug_tag_sweep.main(argv)


@bundle_commands.bundle_command("pasteurize-route")
def run_pasteurize_route(argv: list[str]) -> int:
    """Size the pasteurize fan-out from a JSON request."""
    return pasteurize_route_cli.main(argv)


@bundle_commands.bundle_command("repro-rerun")
def run_repro_rerun(argv: list[str]) -> int:
    """Re-run a repro command N times and emit a verdict."""
    return repro_rerun.main(argv)


def main(argv: list[str] | None = None) -> int:
    return bundle_commands.dispatch(__name__, sys.argv[1:] if argv is None else argv)