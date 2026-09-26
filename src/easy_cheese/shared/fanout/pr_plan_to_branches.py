#!/usr/bin/env python3
"""Convert a fan-out pr-plan to branch / cherry-pick / PR-create commands.

Reads the plan (YAML or JSON) from a path argument or stdin and returns one
shell command per line under the "commands" key. The orchestrator reviews the
commands, then pipes them to `bash -s` to execute. Dry-run friendly — this
script never invokes git or gh.

The plan is loaded through the registered ``PrPlan`` v1 contract, the single
source of truth for plan shape, before any command is emitted.
"""

from __future__ import annotations

import fromargs

from easy_cheese.shared.manifest_io import (  # noqa: E402
    ManifestLoadError,
    read_mapping_arg_or_stdin,
)

from easy_cheese_schemas import PrPlan  # noqa: E402
from easy_cheese_schemas.schema_runtime import load_pr_plan  # noqa: E402

PROG = "pr_plan_to_branches.py"


def sq(value: str) -> str:
    # Single-quote a value for POSIX shell using the four-character escape '\''.
    return "'" + value.replace("'", "'\\''") + "'"


def emit_commands(plan: PrPlan) -> list[str]:
    """Render the branch / cherry-pick / PR-create shell commands for `plan`."""
    lines = [
        f"# pr-plan shape: {plan.shape.value} ({len(plan.groups)} groups)",
        "set -euo pipefail",
    ]
    for index, group in enumerate(plan.groups, start=1):
        # `body` is optional and may be absent, null, or empty; all three mean
        # the same thing here, so `gh pr create --body ''` is what is rendered.
        body = group.body or ""
        lines.append("")
        lines.append(f"# Group {index}: {group.branch} (base: {group.base})")
        lines.append(f"git checkout -b {sq(group.branch)} {sq(group.base)}")
        for sha in group.commits:
            lines.append(f"git cherry-pick {sq(sha)}")
        lines.append(f"git push -u origin {sq(group.branch)}")
        lines.append(
            f"gh pr view {sq(group.branch)} --json number >/dev/null 2>&1 || "
            + f"gh pr create --base {sq(group.base)} --head {sq(group.branch)} "
            + f"--title {sq(group.title)} --body {sq(body)}"
        )
    return lines


def convert(path: str | None = None) -> dict[str, object]:
    """Convert a fan-out pr-plan to branch / cherry-pick / PR-create commands.

    The emitted stream is `set -euo pipefail`, so a failed cherry-pick halts
    before push or PR create. `gh pr create` is guarded with `gh pr view`, so
    a partially shipped plan can re-run without a failure on an
    already-created PR. `git checkout -b` and `git push -u origin` are not
    guarded: edit those lines out before piping, if a prior run already
    created the branch or pushed it.

    Supported shapes (from the plan's "shape" field): single (one PR from
    main), orthogonal_flat (N PRs from main, no inter-dependency),
    stacked_linear (each PR bases on the previous branch), and diamond_stack
    (a seed PR at the base, N curd PRs from the seed, a wiring PR last).

    Parameters
    ----------
    path
        Path to the pr-plan (YAML or JSON); reads stdin when omitted.
    """
    argv = [path] if path else []
    try:
        plan = read_mapping_arg_or_stdin(argv, f"usage: {PROG} [<pr-plan.yaml|pr-plan.json>]")
    except ManifestLoadError as exc:
        exit_code = 2 if str(exc).startswith("usage:") else 1
        raise fromargs.CliError(str(exc), exit_code=exit_code) from exc

    loaded = load_pr_plan(plan)
    if loaded.value is None:
        raise fromargs.CliError(
            "\n".join(f"ERROR: {error}" for error in loaded.problems), exit_code=1
        )

    return {"commands": emit_commands(loaded.value)}


def build_app() -> fromargs.App:
    return fromargs.App(
        "pr-plan-to-branches",
        help="Convert a fan-out pr-plan to branch / cherry-pick / PR-create commands.",
        help_formatter="plain",
        default_command=convert,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
