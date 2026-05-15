#!/usr/bin/env python3
"""Convert a cheese-factory pr-plan to branch / cherry-pick / PR-create commands.

Reads the plan (YAML or JSON) from a path argument or stdin and prints one shell
command per line. The orchestrator reviews the commands, then pipes them to
`bash -s` to execute. Dry-run friendly — this script never invokes git or gh.

Validation is delegated to ``validate_pr_plan`` so there is exactly one source
of truth for plan shape.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from manifest_io import ManifestLoadError, read_mapping_arg_or_stdin
from validate_pr_plan import validate_pr_plan

PROG = "pr_plan_to_branches.py"

USAGE = f"""\
Usage: {PROG} [<pr-plan.yaml|pr-plan.json>]

Reads a cheese-factory pr-plan (from $1 or stdin) and prints the shell
commands needed to create the planned branches and PRs.

The script emits commands only; it never invokes git or gh itself. Pipe its
output to `bash -s` to execute, or eyeball it first.

Supported shapes (from the plan's "shape" field):
  - single            One PR, one branch from main.
  - orthogonal_flat   N PRs each branching from main, no inter-dep.
  - stacked_linear    Linear stack; each PR bases on the previous branch.
  - diamond_stack     Seed PR at base, N curd PRs from seed, wiring PR last.
"""


def sq(value: str) -> str:
    """Single-quote a value for a POSIX shell command line, always wrapping.

    Mirrors the four-character escape used by the previous bash implementation:
    close quote, backslash-escaped quote, open quote — ``'\\''``.
    """
    return "'" + value.replace("'", "'\\''") + "'"


def emit_commands(plan: dict[str, Any]) -> None:
    shape = plan["shape"]
    groups = plan["groups"]
    print(f"# pr-plan shape: {shape} ({len(groups)} groups)")
    for index, group in enumerate(groups, start=1):
        branch = group["branch"]
        title = group["title"]
        body = group.get("body", "")
        base = group["base"]
        commits = group["commits"]

        print()
        print(f"# Group {index}: {branch} (base: {base})")
        print(f"git checkout -b {sq(branch)} {sq(base)}")
        for sha in commits:
            print(f"git cherry-pick {sq(sha)}")
        print(f"git push -u origin {sq(branch)}")
        print(
            f"gh pr create --base {sq(base)} --head {sq(branch)} "
            f"--title {sq(title)} --body {sq(body)}"
        )


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] in ("-h", "--help"):
        print(USAGE)
        return 0

    try:
        plan = read_mapping_arg_or_stdin(argv, f"usage: {PROG} [<pr-plan.yaml|pr-plan.json>]")
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if str(exc).startswith("usage:") else 1

    errors = validate_pr_plan(plan)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    emit_commands(plan)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
