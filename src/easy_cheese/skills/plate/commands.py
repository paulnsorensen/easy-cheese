"""Command surface for the plate application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared import bundle_commands

from . import publication, stack_tools


@bundle_commands.bundle_command("stack-tools")
def run_stack_tools(argv: list[str]) -> int:
    """Report available stacked-PR providers without changing repository state."""
    return stack_tools.main(argv)


@bundle_commands.bundle_command("validate-publication")
def run_validate_publication(argv: list[str]) -> int:
    """Validate and normalize a Plate publication evidence record."""
    return publication.main(argv)


def main(argv: list[str] | None = None) -> int:
    return bundle_commands.dispatch(__name__, sys.argv[1:] if argv is None else argv)
