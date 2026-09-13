#!/usr/bin/env python3
"""Convert a fan-out pr-plan to branch / cherry-pick / PR-create commands.

Reads the plan (YAML or JSON) from a path argument or stdin and prints one shell
command per line. The orchestrator reviews the commands, then pipes them to
`bash -s` to execute. Dry-run friendly — this script never invokes git or gh.

The plan is loaded through the registered ``PrPlan`` v1 contract, the single
source of truth for plan shape, before any command is emitted.
"""

from __future__ import annotations

import sys
from typing import cast

from easy_cheese.shared.manifest_io import (  # noqa: E402
    ManifestLoadError,
    read_mapping_arg_or_stdin,
)

from easy_cheese_schemas import PrPlan, load  # noqa: E402

PROG = "pr_plan_to_branches.py"

USAGE = f"""\
Usage: {PROG} [<pr-plan.yaml|pr-plan.json>]

Reads a fan-out pr-plan (from $1 or stdin) and prints the shell
commands needed to create the planned branches and PRs.

The script emits commands only; it never invokes git or gh itself. Pipe its
output to `bash -s` to execute, or eyeball it first.

The emitted stream is `set -euo pipefail` so a failed cherry-pick halts before
push / PR create. `gh pr create` is guarded with `gh pr view` so a partially
shipped plan can be re-run without aborting at the first already-created PR.
`git checkout -b` and `git push -u origin` are NOT guarded — if a prior run
already created the branch or pushed it, edit those lines out before piping.

Supported shapes (from the plan's "shape" field):
  - single            One PR, one branch from main.
  - orthogonal_flat   N PRs each branching from main, no inter-dep.
  - stacked_linear    Linear stack; each PR bases on the previous branch.
  - diamond_stack     Seed PR at base, N curd PRs from seed, wiring PR last.
"""


def sq(value: str) -> str:
    # Single-quote a value for POSIX shell using the four-character escape '\''.
    return "'" + value.replace("'", "'\\''") + "'"


def emit_commands(plan: PrPlan) -> None:
    print(f"# pr-plan shape: {plan.shape.value} ({len(plan.groups)} groups)")
    print("set -euo pipefail")
    for index, group in enumerate(plan.groups, start=1):
        # A validated PrPlan normalizes an absent or null body to an empty
        # string, so `gh pr create --body ''` is what the emitter renders.
        body = group.body or ""
        print()
        print(f"# Group {index}: {group.branch} (base: {group.base})")
        print(f"git checkout -b {sq(group.branch)} {sq(group.base)}")
        for sha in group.commits:
            print(f"git cherry-pick {sq(sha)}")
        print(f"git push -u origin {sq(group.branch)}")
        print(
            f"gh pr view {sq(group.branch)} --json number >/dev/null 2>&1 || "
            + f"gh pr create --base {sq(group.base)} --head {sq(group.branch)} "
            + f"--title {sq(group.title)} --body {sq(body)}"
        )


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0

    try:
        plan = read_mapping_arg_or_stdin(argv, f"usage: {PROG} [<pr-plan.yaml|pr-plan.json>]")
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if str(exc).startswith("usage:") else 1

    loaded = load(plan, PrPlan, strict=True)
    if loaded.problems:
        for error in loaded.problems:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    emit_commands(cast(PrPlan, loaded.value))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
