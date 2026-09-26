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

import fromargs

from easy_cheese.shared.manifest_io import (  # noqa: E402
    ManifestLoadError,
    read_mapping_arg_or_stdin,
)
from easy_cheese_schemas.schema_runtime import load_pr_plan  # noqa: E402


def validate_pr_plan(plan: dict[str, object]) -> list[str]:
    """Report the problems of one pr-plan document through the registered seam."""
    return list(load_pr_plan(plan).problems)


def check(path: str | None = None) -> dict[str, object]:
    """Validate an /ultracook fan-out PR plan document.

    Parameters
    ----------
    path
        Path to the plan (YAML or JSON); reads stdin when omitted.
    """
    argv = [path] if path else []
    try:
        plan = read_mapping_arg_or_stdin(argv, "usage: validate_pr_plan.py [<pr-plan.yaml|pr-plan.json>]")
    except ManifestLoadError as exc:
        exit_code = 2 if str(exc).startswith("usage:") else 1
        raise fromargs.CliError(str(exc), exit_code=exit_code) from exc

    loaded = load_pr_plan(plan)
    if loaded.problems:
        raise fromargs.CliError(
            "\n".join(f"ERROR: {error}" for error in loaded.problems), exit_code=1
        )

    assert loaded.value is not None
    return {"valid": True, "groups": len(loaded.value.groups)}


def build_app() -> fromargs.App:
    return fromargs.App(
        "validate-pr-plan",
        help="Validate an /ultracook fan-out PR plan document.",
        help_formatter="plain",
        default_command=check,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())