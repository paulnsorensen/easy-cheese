#!/usr/bin/env python3
"""Validate a cheese-factory PR plan document.

The PR plan stays JSON by convention because `pr_plan_to_branches.sh` consumes
it with jq, but this validator also accepts YAML so humans can inspect draft
plans before converting them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from manifest_io import ManifestLoadError, read_mapping_arg_or_stdin

SHAPES = {"single", "orthogonal_flat", "stacked_linear", "diamond_stack"}
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def _type_name(value: object) -> str:
    return type(value).__name__


def _require_string(obj: dict[str, Any], field: str, where: str) -> list[str]:
    value = obj.get(field)
    if not isinstance(value, str) or not value.strip():
        return [f"{where}.{field} must be a non-empty string"]
    return []


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
            errors.append(f"{where} must be an object, got {_type_name(group)}")
            continue

        for field in ("branch", "title", "base"):
            errors.extend(_require_string(group, field, where))

        branch = group.get("branch")
        if isinstance(branch, str):
            if branch in seen_branches:
                errors.append(f"{where}.branch duplicates {branch!r}")
            seen_branches.add(branch)
            if not BRANCH_RE.match(branch):
                errors.append(f"{where}.branch contains characters unsafe for a branch name")

        commits = group.get("commits")
        if not isinstance(commits, list) or not commits:
            errors.append(f"{where}.commits must be a non-empty list")
        else:
            for commit_index, commit in enumerate(commits, start=1):
                if not isinstance(commit, str) or not commit.strip():
                    errors.append(f"{where}.commits[{commit_index}] must be a non-empty string")

        depends_on = group.get("depends_on", [])
        if depends_on is not None:
            if not isinstance(depends_on, list):
                errors.append(f"{where}.depends_on must be a list when present")
            else:
                for dep_index, dep in enumerate(depends_on, start=1):
                    if not isinstance(dep, str) or not dep.strip():
                        errors.append(f"{where}.depends_on[{dep_index}] must be a non-empty string")

    if shape == "single" and len(groups) != 1:
        errors.append("single shape must contain exactly one group")
    if shape == "orthogonal_flat":
        for index, group in enumerate(groups, start=1):
            if isinstance(group, dict) and group.get("base") != "main":
                errors.append(f"groups[{index}].base must be main for orthogonal_flat")

    return errors


def main(argv: list[str]) -> int:
    try:
        plan = read_mapping_arg_or_stdin(argv, "usage: validate_pr_plan.py [<pr-plan.json|yaml>]")
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
