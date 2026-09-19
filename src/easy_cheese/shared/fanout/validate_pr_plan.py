#!/usr/bin/env python3
"""Validate an /ultracook fan-out PR plan document.

The plan's canonical on-disk format is YAML (see ``manifest_io``), but this
validator accepts either YAML or JSON -- both are read into the same Python
mapping before shape checks run.

Shape and content rules live once in ``easy_cheese_schemas.PrPlan`` (branch
/ base charset gating, commit SHA format, shape invariants); this module is a
thin dict-in/errors-out wrapper around it so the CLI keeps its historical
interface.
"""

from __future__ import annotations

import sys

from easy_cheese.shared.manifest_io import (  # noqa: E402
    ManifestLoadError,
    read_mapping_arg_or_stdin,
)
from easy_cheese_schemas.schema_runtime import load_pr_plan  # noqa: E402


def validate_pr_plan(plan: dict[str, object]) -> list[str]:
    """Report the problems of one pr-plan document through the registered seam."""
    return list(load_pr_plan(plan).problems)


def main(argv: list[str]) -> int:
    try:
        plan = read_mapping_arg_or_stdin(argv, "usage: validate_pr_plan.py [<pr-plan.yaml|pr-plan.json>]")
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if str(exc).startswith("usage:") else 1

    loaded = load_pr_plan(plan)
    if loaded.problems:
        for error in loaded.problems:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"\nFAIL: {len(loaded.problems)} validation error(s)", file=sys.stderr)
        return 1

    assert loaded.value is not None
    print(f"OK: {len(loaded.value.groups)} PR group(s), plan valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))