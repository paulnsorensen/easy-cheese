"""Command surface for the Briesearch application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import (
    Command,
    bundle_command,
    derive_command,
    dispatch,
)


@bundle_command("artifact-path")
def _artifact_path(argv: list[str]) -> int:
    from easy_cheese.shared.artifact_path import main

    return main(argv)


@bundle_command("ground-check")
def _ground_check(argv: list[str]) -> int:
    from easy_cheese.skills.briesearch.ground_check import main

    return main(argv)


def _with_summary(command: Command, summary: str) -> Command:
    return Command(command.name, command.target, summary)


COMMANDS = (
    _with_summary(
        derive_command(_artifact_path),
        "Resolve the durable or transient artifact path for a phase and slug",
    ),
    Command(
        "budget-check",
        "easy_cheese.skills.briesearch.budget:main",
        "Enforce the search budget and dedup rules from the run ledger",
    ),
    _with_summary(
        derive_command(_ground_check),
        "Lint a synthesis report for grounding and citation violations",
    ),
    Command(
        "research-layout",
        "easy_cheese.skills.briesearch.research_layout:main",
        "Print the slug-aware research corpus layout as JSON",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)