"""Validate a ready Mold finalization result before Cook starts any writer.

    python3 skills/cook/scripts/cook.pyz validate-result \\
        --result <result.json> --artifact-root <root>

Loads the finalization result, then runs the same host validation that
``execute_bound_plan`` runs: digests, planner and plan binding, exact
coverage, spec holds, and request directives. Any failure exits non-zero.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import fromargs

from easy_cheese.shared.mold_cook_handoff import validate_bound_execution
from easy_cheese_schemas import ArtifactRef, MoldCookCoverage
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    structure_contract_value,
)


def validate_result(*, result: str, artifact_root: str) -> str:
    """Refuse a finalization result that Cook may not execute.

    Parameters
    ----------
    result
        Path to the Mold finalization result JSON.
    artifact_root
        Artifact root that retains the spec, planner result, and plan.
    """
    result_path = Path(result)
    if not result_path.is_file():
        raise fromargs.CliError(f"--result not found: {result}")
    try:
        decoded = cast(object, json.loads(result_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise fromargs.CliError(f"result is not readable JSON: {exc}") from exc
    if not isinstance(decoded, Mapping):
        raise fromargs.CliError("result must be a JSON object")
    finalized = cast(Mapping[str, object], decoded)
    if finalized.get("status") != "ready" or finalized.get("ready") is not True:
        raise fromargs.CliError("result is not ready; do not dispatch a writer")
    try:
        refs = {
            name: structure_contract_value(finalized[name], ArtifactRef, name)
            for name in ("spec_ref", "planner_result_ref", "plan_ref")
        }
        coverage = structure_contract_value(
            finalized["coverage"], MoldCookCoverage, "coverage"
        )
        plan = validate_bound_execution(
            spec_ref=refs["spec_ref"],
            planner_result_ref=refs["planner_result_ref"],
            plan_ref=refs["plan_ref"],
            coverage=coverage,
            artifact_root=artifact_root,
        )
    except (OSError, ValueError, TypeError, KeyError, ContractValidationError) as exc:
        raise fromargs.CliError(f"bound execution refused: {exc}") from exc
    return json.dumps(
        {"valid": True, "plan_id": plan.plan_id, "curd_ids": list(coverage.curd_ids)},
        sort_keys=True,
    )


def build_app() -> fromargs.App:
    return fromargs.App(
        "validate-result",
        help="Validate a ready Mold finalization result before any writer starts.",
        help_formatter="plain",
        default_command=validate_result,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
