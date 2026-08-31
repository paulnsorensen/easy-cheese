"""Command surface for the Mold application bundle."""

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
        "curd-count",
        "easy_cheese.skills.mold.curd_count:main",
        "Count candidate curds in a spec and recommend the next skill",
    ),
    Command(
        "gate-graph",
        "easy_cheese.skills.mold.gate_graph:main",
        "Render the gate state machine as dot, svg, png, or mermaid",
    ),
    Command(
        "render-html",
        "easy_cheese.shared.html_report_cli:main",
        "Render a markdown report into one self-contained offline HTML file",
    ),
    Command(
        "taste-test",
        "easy_cheese.shared.taste_test:main",
        "Run the applicability, contract, and fork-coherence taste gate",
    ),
    Command(
        "validate-spec",
        "easy_cheese.skills.mold.validate_spec:main",
        "Check a produced spec's curdle-time SAP posture",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)