"""Command surface for the Cook application bundle."""

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
        "age-route",
        "easy_cheese.shared.fanout.age_route_cli:main",
        "Size an /age review into single-pass or fan-out lanes (JSON in, JSON out)",
    ),
    Command(
        "baseline",
        "easy_cheese.shared.fanout.baseline:main",
        "Classify a current test-failure list against a stored baseline",
    ),
    Command(
        "phase-decision",
        "easy_cheese.shared.fanout.phase_decision:main",
        "Decide what the fan-out pathway does after a phase sub-agent returns",
    ),
    Command(
        "milknado",
        "easy_cheese.shared.fanout.milknado:main",
        "Probe the milknado engine seam used by parallel mode",
    ),
    Command(
        "mode",
        "easy_cheese.shared.fanout.mode:main",
        "Select the fan-out mode from the canonical size thresholds",
    ),
    Command(
        "worktree",
        "easy_cheese.shared.worktree:main",
        "Create, harvest, and tear down isolated sub-agent worktrees",
    ),
    Command(
        "validate-decomposition",
        "easy_cheese.shared.fanout.validate_decomposition:main",
        "Validate a fan-out decomposition manifest",
    ),
    Command(
        "validate-manifest",
        "easy_cheese.shared.fanout.validate_manifest:main",
        "Validate a fan-out run manifest",
    ),
    Command(
        "validate-pr-plan",
        "easy_cheese.shared.fanout.validate_pr_plan:main",
        "Validate a fan-out PR-plan document",
    ),
    Command(
        "manifest-update",
        "easy_cheese.shared.fanout.manifest_update:main",
        "Apply an atomic, schema-validated update to a fan-out run manifest",
    ),
    Command(
        "wiring-topo-sort",
        "easy_cheese.shared.fanout.wiring_topo_sort:main",
        "Topologically sort a manifest's wiring into ordered waves",
    ),
    Command(
        "pr-plan-to-branches",
        "easy_cheese.shared.fanout.pr_plan_to_branches:main",
        "Convert a fan-out PR plan into branch, cherry-pick, and PR commands",
    ),
    Command(
        "curd-block",
        "easy_cheese.shared.fanout.curd_block:main",
        "Validate a curd block against the spec-locked decomposition schema",
    ),
    Command(
        "normalize",
        "easy_cheese.skills.cook.contract_handlers:normalize_main",
        "Normalize a typed contract payload on the host",
    ),
    Command(
        "validate",
        "easy_cheese.skills.cook.contract_handlers:validate_main",
        "Validate a typed contract payload against its registered schema",
    ),
    Command(
        "slugify",
        "easy_cheese.shared.slugify:main",
        "Derive a kebab-case slug and durable spec path from task text",
    ),
    Command(
        "write-handoff-artifact",
        "easy_cheese.shared.write_handoff_artifact:main",
        "Write a handoff preamble plus optional body atomically",
    ),
    Command(
        "read-handoff-slug",
        "easy_cheese.shared.read_handoff_slug:main",
        "Read the handoff preamble back from a phase artifact",
    ),
    Command(
        "findings-cli",
        "easy_cheese.shared.findings_cli:main",
        "Render an /age report's selection table and resolve selection verbs",
    ),
    Command(
        "gates-cli",
        "easy_cheese.shared.gates_cli:main",
        "Map a quality-gate scoreboard's booleans to a readiness verdict",
    ),
    Command(
        "paths-cli",
        "easy_cheese.shared.paths_cli:main",
        "Slugify, validate, resolve, and list .cheese artifact paths",
    ),
    Command(
        "handoff-cli",
        "easy_cheese.shared.handoff_cli:main",
        "Render, parse, and dispatch-split handoff preambles",
    ),
    Command(
        "render-html",
        "easy_cheese.shared.html_report_cli:main",
        "Render a markdown report into one self-contained offline HTML file",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)