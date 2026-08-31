"""Command surface for the Age application bundle."""

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
        "html-report",
        "easy_cheese.skills.age.age_html_report:main",
        "Render an /age markdown report into one offline HTML file",
    ),
    Command(
        "age-route",
        "easy_cheese.shared.fanout.age_route_cli:main",
        "Size an /age review into single-pass or fan-out lanes (JSON in, JSON out)",
    ),
    Command(
        "review-surface",
        "easy_cheese.shared.fanout.review_surface_cli:main",
        "Score the reviewable git surface that routing sizes against (JSON out)",
    ),
    Command(
        "severity",
        "easy_cheese.shared.severity:main",
        "Compute per-finding severity and fix-cost-now buckets",
    ),
    Command(
        "slugify",
        "easy_cheese.shared.slugify:main",
        "Derive a kebab-case slug and durable spec path from task text",
    ),
    Command(
        "review-lock",
        "easy_cheese.skills.age.review_lock:main",
        "Record or verify the production-tree digest that keeps /age review-only",
    ),
    Command(
        "write-handoff-artifact",
        "easy_cheese.skills.age.review_lock:gated_write_handoff_artifact",
        "Write a handoff preamble plus optional body atomically, behind the review lock",
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