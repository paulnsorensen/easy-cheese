"""Emit the branch-carving commands for an orthogonal_flat pr_plan."""

from __future__ import annotations

import fromargs

from easy_cheese.shared.fanout.pr_plan_to_branches import emit_carve_commands
from easy_cheese.shared.manifest_io import ManifestLoadError, read_mapping_arg_or_stdin
from easy_cheese_schemas.pr_plan import PrShape
from easy_cheese_schemas.schema_runtime import load_pr_plan

_USAGE = "usage: carve-flat --source-branch <branch> [--pr-plan <plan.json|plan.yaml>]"


def carve_cmd(source_branch: str, *, pr_plan: str | None = None) -> dict[str, object]:
    """Emit per-group carve and restore commands for an orthogonal_flat pr_plan.

    The command never runs git or gh. For each group, run its `carve` commands,
    then the quality gate, then publish the group, then its `restore` command.

    Parameters
    ----------
    source_branch
        Branch to return to after each group is published.
    pr_plan
        Path to the pr_plan (YAML or JSON); reads stdin when omitted.
    """
    try:
        raw = read_mapping_arg_or_stdin([pr_plan] if pr_plan else [], _USAGE)
    except ManifestLoadError as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    loaded = load_pr_plan(raw)
    if loaded.value is None:
        raise fromargs.CliError("\n".join(loaded.problems), exit_code=2)
    if loaded.value.shape is not PrShape.ORTHOGONAL_FLAT:
        raise fromargs.CliError(
            f"carve-flat needs shape orthogonal_flat, got {loaded.value.shape.value}", exit_code=2
        )
    return {"groups": emit_carve_commands(loaded.value, source_branch)}


def build_app() -> fromargs.App:
    return fromargs.App(
        "carve-flat",
        help="Emit the branch-carving commands for an orthogonal_flat pr_plan.",
        help_formatter="plain",
        default_command=carve_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
