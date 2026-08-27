"""Command surface for the Ultracook compatibility application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

COMMANDS = {
    "artifact-path": "easy_cheese.shared.artifact_path",
    "baseline": "easy_cheese.shared.fanout.baseline",
    "phase_decision": "easy_cheese.shared.fanout.phase_decision",
    "mode": "easy_cheese.shared.fanout.mode",
    "worktree": "easy_cheese.shared.worktree",
    "milknado": "easy_cheese.shared.fanout.milknado",
    "validate_decomposition": "easy_cheese.shared.fanout.validate_decomposition",
    "validate_manifest": "easy_cheese.shared.fanout.validate_manifest",
    "validate_pr_plan": "easy_cheese.shared.fanout.validate_pr_plan",
    "manifest_update": "easy_cheese.shared.fanout.manifest_update",
    "wiring_topo_sort": "easy_cheese.shared.fanout.wiring_topo_sort",
    "pr_plan_to_branches": "easy_cheese.shared.fanout.pr_plan_to_branches",
    "age-route": "easy_cheese.shared.fanout.age_route_cli",
    "curd-block": "easy_cheese.shared.fanout.curd_block",
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
