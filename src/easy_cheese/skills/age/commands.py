"""Command surface for the Age application bundle."""

from __future__ import annotations

import sys

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
    derive_command(_artifact_path),
    derive_command(_html_report),
    derive_command(_age_route),
    derive_command(_review_surface),
    derive_command(_severity),
    derive_command(_slugify),
    derive_command(_write_handoff_artifact),
    derive_command(_read_handoff_slug),
    derive_command(_findings_cli),
    derive_command(_gates_cli),
    derive_command(_paths_cli),
    derive_command(_handoff_cli),
    derive_command(_render_html),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)