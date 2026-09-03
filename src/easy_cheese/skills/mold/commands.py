"""This module defines the Mold bundle command surface."""

from __future__ import annotations

import sys
from dataclasses import replace

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


@bundle_command("migrate")
def _migrate(argv: list[str]) -> int:
    from easy_cheese.skills.mold.contract_handlers import migrate_main

    return migrate_main(argv)


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
    replace(
        derive_command(_artifact_path),
        summary="Resolve the durable or transient artifact path for a phase and slug",
    ),
    replace(
        derive_command(_curd_count),
        summary="Count candidate curds in a spec and recommend the next skill",
    ),
    replace(
        derive_command(_gate_graph),
        summary="Render the gate state machine as dot, svg, png, or mermaid",
    ),
    replace(
        derive_command(_migrate),
        summary="Migrate a legacy artifact and emit its handoff pointer as canonical JSON",
    ),
    replace(
        derive_command(_publish),
        summary="Publish a curd plan and emit its handoff pointer as canonical JSON",
    ),
    replace(
        derive_command(_render_html),
        summary="Render a markdown report into one self-contained offline HTML file",
    ),
    replace(
        derive_command(_taste_test),
        summary="Run the applicability, contract, and fork-coherence taste gate",
    ),
    replace(
        derive_command(_validate_spec),
        summary="Check a produced spec's curdle-time SAP posture",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)