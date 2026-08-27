"""Command surface for the Mold application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

COMMANDS = {
    "artifact-path": "easy_cheese.shared.artifact_path",
    "curd-count": "easy_cheese.skills.mold.curd_count",
    "gate-graph": "easy_cheese.skills.mold.gate_graph",
    "render_html": "easy_cheese.shared.html_report_cli",
    "taste-test": "easy_cheese.shared.taste_test",
    "validate-spec": "easy_cheese.skills.mold.validate_spec",
}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
