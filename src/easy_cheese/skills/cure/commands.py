"""Command surface for the Cure application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
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