"""Command surface for the Briesearch application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared import artifact_path, bundle_commands

from . import ground_check


@bundle_commands.bundle_command("artifact-path")
def resolve_artifact_path(argv: list[str]) -> int:
    """Resolve a durable research artifact path."""
    return artifact_path.main(argv)


@bundle_commands.bundle_command("ground-check")
def check_grounding(argv: list[str]) -> int:
    """Check a research report for grounding violations."""
    return ground_check.main(argv)


def main(argv: list[str] | None = None) -> int:
    return bundle_commands.dispatch(__name__, sys.argv[1:] if argv is None else argv)
