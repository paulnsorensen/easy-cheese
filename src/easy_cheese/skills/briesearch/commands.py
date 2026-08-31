"""Command surface for the Briesearch application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command(
        "artifact-path",
        "easy_cheese.shared.artifact_path:main",
        "Resolve the durable or transient artifact path for a phase and slug",
    ),
    Command(
        "budget-check",
        "easy_cheese.skills.briesearch.budget:main",
        "Enforce the search budget and dedup rules from the run ledger",
    ),
    Command(
        "ground-check",
        "easy_cheese.skills.briesearch.ground_check:main",
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