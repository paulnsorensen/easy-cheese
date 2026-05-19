#!/usr/bin/env python3
"""Validate a cheese-factory PR plan document.

The plan's canonical on-disk format is YAML (see ``manifest_io``), but this
validator accepts either YAML or JSON — both are read into the same Python
mapping before shape checks run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_SCRIPTS = SCRIPT_DIR.parents[2] / "shared" / "scripts"
for _path in (SCRIPT_DIR, SHARED_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from manifest_io import ManifestLoadError, read_mapping_arg_or_stdin
from schema import non_empty_string, type_name

SHAPES = {"single", "orthogonal_flat", "stacked_linear", "diamond_stack"}
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
# 7 is git's default short-SHA floor (`core.abbrev`); shorter values risk
# colliding with a branch / tag of the same name, since git resolves refs
# before SHA prefixes. Full SHA-1 is 40 hex chars.
COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _validate_commits(commits: object, where: str) -> list[str]:
    if not isinstance(commits, list) or not commits:
        return [f"{where}.commits must be a non-empty list"]
    errors: list[str] = []
    for index, commit in enumerate(commits, start=1):
        loc = f"{where}.commits[{index}]"
        if not isinstance(commit, str) or not commit.strip():
            errors.append(f"{loc} must be a non-empty string")
        elif not COMMIT_SHA_RE.match(commit):
            errors.append(f"{loc} must be a hex SHA (7-40 hex chars); got {commit!r}")
    return errors


def _validate_depends_on(depends_on: object, where: str) -> list[str]:
    if depends_on is None:
        return []
    if not isinstance(depends_on, list):
        return [f"{where}.depends_on must be a list when present"]
    errors: list[str] = []
    for index, dep in enumerate(depends_on, start=1):
        if not isinstance(dep, str) or not dep.strip():
            errors.append(f"{where}.depends_on[{index}] must be a non-empty string")
    return errors


def validate_pr_plan(plan: dict[str, Any]) -> list[str]:
    """Return validation errors for a pr-plan document."""
    errors: list[str] = []
    shape = plan.get("shape")
    if shape not in SHAPES:
        errors.append("shape must be one of single|orthogonal_flat|stacked_linear|diamond_stack")

    groups = plan.get("groups")
    if not isinstance(groups, list) or not groups:
        errors.append("groups must be a non-empty list")
        return errors

    seen_branches: set[str] = set()
    for index, group in enumerate(groups, start=1):
        where = f"groups[{index}]"
        if not isinstance(group, dict):
            errors.append(f"{where} must be an object, got {type_name(group)}")
            continue

        for field in ("branch", "title", "base"):
            errors.extend(non_empty_string(group, field, where))
        if "body" in group and not isinstance(group["body"], str):
            # Body is optional and may be empty (`gh pr create --body ''` is
            # valid). We only enforce the type, since the emitter calls
            # `.replace()` on it.
            errors.append(f"{where}.body must be a string when present")

        branch = group.get("branch")
        if isinstance(branch, str):
            if branch in seen_branches:
                errors.append(f"{where}.branch duplicates {branch!r}")
            seen_branches.add(branch)
            if not BRANCH_RE.match(branch):
                errors.append(f"{where}.branch contains characters unsafe for a branch name")

        errors.extend(_validate_commits(group.get("commits"), where))
        errors.extend(_validate_depends_on(group.get("depends_on", []), where))

    if shape == "single" and len(groups) != 1:
        errors.append("single shape must contain exactly one group")
    if shape == "orthogonal_flat":
        for index, group in enumerate(groups, start=1):
            if isinstance(group, dict) and group.get("base") != "main":
                errors.append(f"groups[{index}].base must be main for orthogonal_flat")

    return errors


def main(argv: list[str]) -> int:
    try:
        plan = read_mapping_arg_or_stdin(argv, "usage: validate_pr_plan.py [<pr-plan.yaml|pr-plan.json>]")
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if str(exc).startswith("usage:") else 1

    errors = validate_pr_plan(plan)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"\nFAIL: {len(errors)} validation error(s)", file=sys.stderr)
        return 1

    print(f"OK: {len(plan.get('groups', []))} PR group(s), plan valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
