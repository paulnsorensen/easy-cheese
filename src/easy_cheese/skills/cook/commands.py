"""Command surface for the Cook application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("artifact-path")
def _artifact_path(argv: list[str]) -> int:
    from easy_cheese.shared.artifact_path import main

    return main(argv)


@bundle_command("age-route")
def _age_route(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.age_route_cli import main

    return main(argv)


@bundle_command("baseline")
def _baseline(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.baseline import main

    return main(argv)


@bundle_command("phase-decision")
def _phase_decision(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.phase_decision import main

    return main(argv)


@bundle_command("milknado")
def _milknado(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.milknado import main

    return main(argv)


@bundle_command("mode")
def _mode(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.mode import main

    return main(argv)


@bundle_command("worktree")
def _worktree(argv: list[str]) -> int:
    from easy_cheese.shared.worktree import main

    return main(argv)


@bundle_command("validate-decomposition")
def _validate_decomposition(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.validate_decomposition import main

    return main(argv)


@bundle_command("validate-manifest")
def _validate_manifest(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.validate_manifest import main

    return main(argv)


@bundle_command("validate-pr-plan")
def _validate_pr_plan(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.validate_pr_plan import main

    return main(argv)


@bundle_command("manifest-update")
def _manifest_update(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.manifest_update import main

    return main(argv)


@bundle_command("wiring-topo-sort")
def _wiring_topo_sort(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.wiring_topo_sort import main

    return main(argv)


@bundle_command("pr-plan-to-branches")
def _pr_plan_to_branches(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.pr_plan_to_branches import main

    return main(argv)


@bundle_command("curd-block")
def _curd_block(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.curd_block import main

    return main(argv)


@bundle_command("normalize")
def _normalize(argv: list[str]) -> int:
    from easy_cheese.skills.cook.contract_handlers import normalize_main

    return normalize_main(argv)


@bundle_command("validate")
def _validate(argv: list[str]) -> int:
    from easy_cheese.skills.cook.contract_handlers import validate_main

    return validate_main(argv)


@bundle_command("accept")
def _accept(argv: list[str]) -> int:
    from easy_cheese.skills.cook.contract_handlers import accept_main

    return accept_main(argv)


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
    derive_command(_age_route),
    derive_command(_baseline),
    derive_command(_phase_decision),
    derive_command(_milknado),
    derive_command(_mode),
    derive_command(_worktree),
    derive_command(_validate_decomposition),
    derive_command(_validate_manifest),
    derive_command(_validate_pr_plan),
    derive_command(_manifest_update),
    derive_command(_wiring_topo_sort),
    derive_command(_pr_plan_to_branches),
    derive_command(_curd_block),
    derive_command(_normalize),
    derive_command(_validate),
    derive_command(_accept),
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