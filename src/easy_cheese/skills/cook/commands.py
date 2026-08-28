"""Command surface for the Cook application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("artifact-path", "easy_cheese.shared.artifact_path:main"),
    Command("age-route", "easy_cheese.shared.fanout.age_route_cli:main"),
    Command("baseline", "easy_cheese.shared.fanout.baseline:main"),
    Command("phase_decision", "easy_cheese.shared.fanout.phase_decision:main"),
    Command("milknado", "easy_cheese.shared.fanout.milknado:main"),
    Command("mode", "easy_cheese.shared.fanout.mode:main"),
    Command("worktree", "easy_cheese.shared.worktree:main"),
    Command("validate_decomposition", "easy_cheese.shared.fanout.validate_decomposition:main"),
    Command("validate_manifest", "easy_cheese.shared.fanout.validate_manifest:main"),
    Command("validate_pr_plan", "easy_cheese.shared.fanout.validate_pr_plan:main"),
    Command("manifest_update", "easy_cheese.shared.fanout.manifest_update:main"),
    Command("wiring_topo_sort", "easy_cheese.shared.fanout.wiring_topo_sort:main"),
    Command("pr_plan_to_branches", "easy_cheese.shared.fanout.pr_plan_to_branches:main"),
    Command("curd-block", "easy_cheese.shared.fanout.curd_block:main"),
    Command("normalize", "easy_cheese.skills.cook.cook_cli:normalize_main"),
    Command("validate", "easy_cheese.skills.cook.cook_cli:validate_main"),
    Command("slugify", "easy_cheese.shared.slugify:main"),
    Command("write_handoff_artifact", "easy_cheese.shared.write_handoff_artifact:main"),
    Command("read_handoff_slug", "easy_cheese.shared.read_handoff_slug:main"),
    Command("findings_cli", "easy_cheese.shared.findings_cli:main"),
    Command("gates_cli", "easy_cheese.shared.gates_cli:main"),
    Command("paths_cli", "easy_cheese.shared.paths_cli:main"),
    Command("handoff_cli", "easy_cheese.shared.handoff_cli:main"),
    Command("render_html", "easy_cheese.shared.html_report_cli:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)