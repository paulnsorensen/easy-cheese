"""Command surface for the Cure application bundle."""

from __future__ import annotations

from dataclasses import replace
import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("slugify")
def _slugify(argv: list[str]) -> int:
    from easy_cheese.shared.slugify import main

    return main(argv)


@bundle_command("write-handoff-artifact")
def _write_handoff_artifact(argv: list[str]) -> int:
    from easy_cheese.shared.write_handoff_artifact import main

    return main(argv)


@bundle_command("read-handoff-slug")
def _read_handoff_slug(argv: list[str]) -> int:
    from easy_cheese.shared.read_handoff_slug import main

    return main(argv)


@bundle_command("findings-cli")
def _findings_cli(argv: list[str]) -> int:
    from easy_cheese.shared.findings_cli import main

    return main(argv)


@bundle_command("gates-cli")
def _gates_cli(argv: list[str]) -> int:
    from easy_cheese.shared.gates_cli import main

    return main(argv)


@bundle_command("paths-cli")
def _paths_cli(argv: list[str]) -> int:
    from easy_cheese.shared.paths_cli import main

    return main(argv)


@bundle_command("handoff-cli")
def _handoff_cli(argv: list[str]) -> int:
    from easy_cheese.shared.handoff_cli import main

    return main(argv)


@bundle_command("render-html")
def _render_html(argv: list[str]) -> int:
    from easy_cheese.shared.html_report_cli import main

    return main(argv)


COMMANDS = (
    replace(
        derive_command(_slugify),
        summary="Derive a kebab-case slug and durable spec path from task text",
    ),
    replace(
        derive_command(_write_handoff_artifact),
        summary="Write a handoff preamble plus optional body atomically",
    ),
    replace(
        derive_command(_read_handoff_slug),
        summary="Read the handoff preamble back from a phase artifact",
    ),
    replace(
        derive_command(_findings_cli),
        summary="Render an /age report's selection table and resolve selection verbs",
    ),
    replace(
        derive_command(_gates_cli),
        summary="Map a quality-gate scoreboard's booleans to a readiness verdict",
    ),
    replace(
        derive_command(_paths_cli),
        summary="Slugify, validate, resolve, and list .cheese artifact paths",
    ),
    replace(
        derive_command(_handoff_cli),
        summary="Render, parse, and dispatch-split handoff preambles",
    ),
    replace(
        derive_command(_render_html),
        summary="Render a markdown report into one self-contained offline HTML file",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)