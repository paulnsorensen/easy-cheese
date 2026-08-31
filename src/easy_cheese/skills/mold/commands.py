"""Command surface for the Mold application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("artifact-path")
def _artifact_path(argv: list[str]) -> int:
    from easy_cheese.shared.artifact_path import main

    return main(argv)


@bundle_command("curd-count")
def _curd_count(argv: list[str]) -> int:
    from easy_cheese.skills.mold.curd_count import main

    return main(argv)


@bundle_command("gate-graph")
def _gate_graph(argv: list[str]) -> int:
    from easy_cheese.skills.mold.gate_graph import main

    return main(argv)


@bundle_command("publish")
def _publish(argv: list[str]) -> int:
    from easy_cheese.skills.mold.contract_handlers import publish_main

    return publish_main(argv)


@bundle_command("render-html")
def _render_html(argv: list[str]) -> int:
    from easy_cheese.shared.html_report_cli import main

    return main(argv)


@bundle_command("taste-test")
def _taste_test(argv: list[str]) -> int:
    from easy_cheese.shared.taste_test import main

    return main(argv)


@bundle_command("validate-spec")
def _validate_spec(argv: list[str]) -> int:
    from easy_cheese.skills.mold.validate_spec import main

    return main(argv)


COMMANDS = (
    derive_command(_artifact_path),
    derive_command(_curd_count),
    derive_command(_gate_graph),
    derive_command(_publish),
    derive_command(_render_html),
    derive_command(_taste_test),
    derive_command(_validate_spec),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)