"""Command surface for the Age application bundle."""

from __future__ import annotations

import sys

from dataclasses import replace

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("artifact-path")
def _artifact_path(argv: list[str]) -> int:
    from easy_cheese.shared.artifact_path import main

    return main(argv)


@bundle_command("html-report")
def _html_report(argv: list[str]) -> int:
    from easy_cheese.skills.age.age_html_report import main

    return main(argv)


@bundle_command("age-route")
def _age_route(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.age_route_cli import main

    return main(argv)


@bundle_command("review-surface")
def _review_surface(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.review_surface_cli import main

    return main(argv)


@bundle_command("severity")
def _severity(argv: list[str]) -> int:
    from easy_cheese.shared.severity import main

    return main(argv)


@bundle_command("slugify")
def _slugify(argv: list[str]) -> int:
    from easy_cheese.shared.slugify import main

    return main(argv)


@bundle_command("review-lock")
def _review_lock(argv: list[str]) -> int:
    from easy_cheese.skills.age.review_lock import main

    return main(argv)


@bundle_command("write-handoff-artifact")
def _write_handoff_artifact(argv: list[str]) -> int:
    from easy_cheese.skills.age.review_lock import gated_write_handoff_artifact

    return gated_write_handoff_artifact(argv)


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
        derive_command(_artifact_path),
        summary="Resolve the durable or transient artifact path for a phase and slug",
    ),
    replace(
        derive_command(_html_report),
        summary="Render an /age markdown report into one offline HTML file",
    ),
    replace(
        derive_command(_age_route),
        summary="Size an /age review into single-pass or fan-out lanes (JSON in, JSON out)",
    ),
    replace(
        derive_command(_review_surface),
        summary="Score the reviewable git surface that routing sizes against (JSON out)",
    ),
    replace(
        derive_command(_severity),
        summary="Compute per-finding severity and fix-cost-now buckets",
    ),
    replace(
        derive_command(_slugify),
        summary="Derive a kebab-case slug and durable spec path from task text",
    ),
    replace(
        derive_command(_review_lock),
        summary="Record or verify the production tree digest that keeps /age review-only",
    ),
    replace(
        derive_command(_write_handoff_artifact),
        summary="Write an age handoff atomically after the review lock verifies the tree",
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