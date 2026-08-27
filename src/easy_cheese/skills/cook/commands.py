"""Command surface for the Cook application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

COMMANDS = {
    "artifact-path": "easy_cheese.shared.artifact_path",
    "age-route": "easy_cheese.shared.fanout.age_route_cli",
    "baseline": "easy_cheese.shared.fanout.baseline",
    "milknado": "easy_cheese.shared.fanout.milknado",
    "mode": "easy_cheese.shared.fanout.mode",
    "worktree": "easy_cheese.shared.worktree",
    "normalize": "easy_cheese.skills.cook.cook_cli",
    "validate": "easy_cheese.skills.cook.cook_cli",
    "slugify": "easy_cheese.shared.slugify",
    "write_handoff_artifact": "easy_cheese.shared.write_handoff_artifact",
    "read_handoff_slug": "easy_cheese.shared.read_handoff_slug",
    "findings_cli": "easy_cheese.shared.findings_cli",
    "gates_cli": "easy_cheese.shared.gates_cli",
    "paths_cli": "easy_cheese.shared.paths_cli",
    "handoff_cli": "easy_cheese.shared.handoff_cli",
    "render_html": "easy_cheese.shared.html_report_cli",
}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
