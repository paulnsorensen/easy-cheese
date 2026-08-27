"""Command surface for the hard-cheese application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared import bundle_commands

from . import append_attempt, freshness_check


@bundle_commands.bundle_command("append-attempt")
def run_append_attempt(argv: list[str]) -> int:
    """Append a hard-cheese attempt row."""
    return append_attempt.main(argv)


@bundle_commands.bundle_command("freshness-check")
def run_freshness_check(argv: list[str]) -> int:
    """Check whether a hard-cheese attempt is fresh."""
    return freshness_check.main(argv)


def main(argv: list[str] | None = None) -> int:
    return bundle_commands.dispatch(__name__, sys.argv[1:] if argv is None else argv)
