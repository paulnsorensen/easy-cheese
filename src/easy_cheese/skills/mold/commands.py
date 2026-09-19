"""This module defines the Mold bundle command surface."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("domain-model-target")
def _domain_model_target(argv: list[str]) -> int:
    from easy_cheese.shared.paths import main

    return main(["domain-model-target", *argv])


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


@bundle_command("finalize")
def _finalize(argv: list[str]) -> int:
    from easy_cheese.skills.mold.producer import main

    return main(argv)


@bundle_command("normalize-planner")
def _normalize_planner(argv: list[str]) -> int:
    from easy_cheese.skills.mold.producer import normalize_planner_main

    return normalize_planner_main(argv)


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
    derive_command(
        _artifact_path,
        "Resolve the durable or transient artifact path for a phase and slug",
    ),
    derive_command(
        _finalize,
        "Finalize a Mold spec and publish only a consumer-valid handoff",
    ),
    derive_command(
        _normalize_planner,
        "Materialize a planner writer envelope into a canonical PlannerResult",
    ),
    derive_command(
        _curd_count, "Count candidate curds in a spec and recommend the next skill"
    ),
    derive_command(
        _domain_model_target,
        "Resolve the domain-model store from explicit Hallouminate probe results",
    ),
    derive_command(
        _gate_graph, "Render the gate state machine as dot, svg, png, or mermaid"
    ),
    derive_command(
        _render_html,
        "Render a markdown report into one self-contained offline HTML file",
    ),
    derive_command(
        _taste_test,
        "Run the applicability, contract, and fork-coherence taste gate;"
        + " --precheck runs the lexical pre-check on the draft without a verdict",
    ),
    derive_command(
        _validate_spec,
        "Check a spec against the current Mold specification requirements",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)
