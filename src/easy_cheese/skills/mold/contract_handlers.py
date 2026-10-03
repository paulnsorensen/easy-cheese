"""Handlers for the Mold finalize and planner-normalization commands.

``finalize`` publishes a canonical ``MoldCookHandoff`` for one spec, and
``normalize-planner`` materializes a planner writer envelope into a canonical
``PlannerResult``.  Both adapt argv and stdout only; every finalization and
normalization decision stays in :mod:`easy_cheese.skills.mold.producer`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import TypeVar, cast

import fromargs

from easy_cheese_schemas.contracts import CurdPlan
from easy_cheese_schemas.mold_cook import MoldCookInputKind, MoldCookMode
from easy_cheese.shared.taste_test import ForkTasteVerdict

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

_EnumT = TypeVar("_EnumT", bound=Enum)


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
        raise fromargs.CliError(str(exc), exit_code=1) from exc
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


def _parse_enum(value: str, enum: type[_EnumT], label: str) -> _EnumT:
    try:
        return enum(value)
    except ValueError as exc:
        raise FinalizationError(f"invalid {label}: {value!r}") from exc


def _finalize(
    spec: str,
    *,
    artifact_root: str,
    operation_id: str,
    request_id: str,
    input_kind: str = MoldCookInputKind.DIRECT_SPEC.value,
    mode: str = MoldCookMode.FULL.value,
    planner_result: str | None = None,
    plan: str | None = None,
    coverage: str | None = None,
    taste_result: str | None = None,
    ledger: str | None = None,
    save_approved: bool = False,
) -> dict[str, object]:
    """Finalize a Mold spec and publish only a consumer-valid handoff.

    Parameters
    ----------
    spec
        Path to the mold spec markdown file.
    artifact_root
        Root directory for finalization artifacts.
    operation_id
        Idempotency key for this finalize operation.
    request_id
        Request id the handoff carries.
    input_kind
        MoldCookInputKind value naming the input shape.
    mode
        MoldCookMode value naming the execution mode.
    planner_result
        Optional path to a canonical PlannerResult JSON artifact.
    plan
        Optional path to a CurdPlan JSON artifact.
    coverage
        Optional path to a proposed coverage JSON artifact.
    taste_result
        Optional path to a fork taste verdict JSON artifact.
    ledger
        Optional path to a decision ledger JSON artifact.
    save_approved
        The user approved saving the draft with unchecked coherence items.
        The save stays not ready and publishes no pointer.
    """
    try:
        taste: object | None = (
            None if taste_result is None else read_json_artifact(Path(taste_result))
        )
        ledger_data: object | None = (
            None if ledger is None else read_json_artifact(Path(ledger))
        )
        outcome = finalize_mold(
            Path(spec),
            artifact_root=Path(artifact_root),
            operation_id=operation_id,
            request_id=request_id,
            input_kind=_parse_enum(input_kind, MoldCookInputKind, "input kind"),
            mode=_parse_enum(mode, MoldCookMode, "mode"),
            planner_result=Path(planner_result) if planner_result is not None else None,
            plan=Path(plan) if plan is not None else None,
            proposed_coverage=Path(coverage) if coverage is not None else None,
            taste_result=cast(
                ForkTasteVerdict | Mapping[str, object] | Path | None, taste
            ),
            decision_ledger=ledger_data,
            save_approved=save_approved,
        )
    except (
        FinalizationError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise fromargs.CliError(str(exc), exit_code=1) from exc
    return outcome.to_dict()


def build_app() -> fromargs.App:
    return fromargs.App(
        "finalize",
        help="Finalize a Mold spec and publish only a consumer-valid handoff.",
        help_formatter="plain",
        default_command=_finalize,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
