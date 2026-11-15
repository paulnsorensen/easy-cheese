"""Handlers for Mold finalization and planner normalization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import fromargs

from easy_cheese_schemas.contracts import CurdPlan

# The producer owns the bounded JSON read and the canonical JSON projection
# that both commands report with, so the CLI borrows them instead of keeping a
# second copy of either rule.
from easy_cheese.skills.mold.producer import (
    FinalizationError,
    _canonical_output as canonical_output,  # pyright: ignore[reportPrivateUsage]
    _read_json as read_json_artifact,  # pyright: ignore[reportPrivateUsage]
    _write_bounded as write_bounded_artifact,  # pyright: ignore[reportPrivateUsage]
    finalize_mold,
    normalize_planner_result,
)

__all__ = [
    "main",
    "normalize_planner_main",
]

def _normalize_planner(
    writer: str,
    *,
    request: str,
    invocation: str,
    output: str | None = None,
) -> dict[str, object]:
    """Materialize a planner writer envelope into a canonical PlannerResult.

    Parameters
    ----------
    writer
        Path to the planner writer's JSON envelope.
    request
        Path to the JSON planner request.
    invocation
        Path to the JSON invocation record naming the plan and curd ids.
    output
        Optional path to also write the canonical result to.
    """
    try:
        writer_raw = read_json_artifact(Path(writer))
        request_raw = read_json_artifact(Path(request))
        invocation_raw = read_json_artifact(Path(invocation))
        if not isinstance(invocation_raw, Mapping):
            raise FinalizationError("invocation must be a JSON object")
        invocation_mapping = cast(Mapping[str, object], invocation_raw)
        host_raw = invocation_mapping.get("planner", invocation_mapping)
        if not isinstance(host_raw, Mapping):
            raise FinalizationError("invocation.planner must be a JSON object")
        host = cast(Mapping[str, object], host_raw)
        plan_id_raw = host.get("plan_id")
        curd_ids_raw = host.get("curd_ids")
        if not isinstance(plan_id_raw, str) or not plan_id_raw.strip():
            raise FinalizationError("invocation.plan_id is required")
        if not isinstance(curd_ids_raw, Mapping):
            raise FinalizationError("invocation.curd_ids is required")
        if not isinstance(request_raw, Mapping) or not isinstance(writer_raw, Mapping):
            raise FinalizationError("request and writer must be JSON objects")
        result = normalize_planner_result(
            cast(Mapping[str, object], request_raw),
            cast(Mapping[str, object], writer_raw),
            plan_id=plan_id_raw,
            curd_ids={
                cast(str, key): cast(str, value)
                for key, value in cast(Mapping[object, object], curd_ids_raw).items()
            },
            artifacts=cast(Mapping[str, object] | None, host.get("artifacts")),
            evidence=cast(Mapping[str, object] | None, host.get("evidence")),
            lineages=cast(Mapping[str, object] | None, host.get("lineages")),
            source_plan=cast(
                CurdPlan | Mapping[str, object] | Path | None,
                host.get("source_plan"),
            ),
        )
        payload = canonical_output(result)
        if output is not None:
            write_bounded_artifact(
                Path(output), (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
            )
    except (
        FinalizationError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    return payload


def _normalize_planner_app() -> fromargs.App:
    return fromargs.App(
        "normalize-planner",
        help="Materialize a planner writer envelope into a canonical PlannerResult.",
        help_formatter="plain",
        default_command=_normalize_planner,
    )


def normalize_planner_main(argv: list[str] | None = None) -> int:
    return _normalize_planner_app().run(argv)



def _finalize(
    spec: str,
    *,
    artifact_root: str,
    operation_id: str,
    request_id: str,
    planner_result: str | None = None,
    plan: str | None = None,
    coverage: str | None = None,
    save_approved: bool = False,
) -> dict[str, object]:
    """Save Mold work with direct bound spec, plan, and scope references."""
    try:
        outcome = finalize_mold(
            Path(spec),
            artifact_root=Path(artifact_root),
            operation_id=operation_id,
            request_id=request_id,
            planner_result=Path(planner_result) if planner_result is not None else None,
            plan=Path(plan) if plan is not None else None,
            proposed_coverage=Path(coverage) if coverage is not None else None,
            save_approved=save_approved,
        )
    except (
        FinalizationError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    return outcome.to_dict()


def build_app() -> fromargs.App:
    return fromargs.App(
        "finalize",
        help="Finalize a Mold spec with direct Cook references.",
        help_formatter="plain",
        default_command=_finalize,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
