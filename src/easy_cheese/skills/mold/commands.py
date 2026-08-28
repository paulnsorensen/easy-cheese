"""Command surface for the Mold application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("artifact-path", "easy_cheese.shared.artifact_path:main"),
    Command("curd-count", "easy_cheese.skills.mold.curd_count:main"),
    Command("gate-graph", "easy_cheese.skills.mold.gate_graph:main"),
    Command("render_html", "easy_cheese.shared.html_report_cli:main"),
    Command("taste-test", "easy_cheese.shared.taste_test:main"),
    Command("validate-spec", "easy_cheese.skills.mold.validate_spec:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)