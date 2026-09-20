"""Handlers for the Mold finalize and planner-normalization commands.

``finalize`` publishes a canonical ``MoldCookHandoff`` for one spec, and
``normalize-planner`` materializes a planner writer envelope into a canonical
``PlannerResult``.  Both adapt argv and stdout only; every finalization and
normalization decision stays in :mod:`easy_cheese.skills.mold.producer`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import TypeVar, cast

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


def _write_json_output(value: object, output: Path | None) -> None:
    text = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if output is None:
        _ = sys.stdout.write(text)
    else:
        write_bounded_artifact(output, text.encode())
        _ = sys.stdout.write(text)


def normalize_planner_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="normalize-planner",
        description="Materialize a planner writer envelope into a canonical PlannerResult.",
    )
    _ = parser.add_argument("writer", type=Path)
    _ = parser.add_argument("--request", required=True, type=Path)
    _ = parser.add_argument("--invocation", required=True, type=Path)
    _ = parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        writer_raw = read_json_artifact(cast(Path, args.writer))
        request_raw = read_json_artifact(cast(Path, args.request))
        invocation = read_json_artifact(cast(Path, args.invocation))
        if not isinstance(invocation, Mapping):
            raise FinalizationError("invocation must be a JSON object")
        invocation_mapping = cast(Mapping[str, object], invocation)
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
        _write_json_output(canonical_output(result), cast(Path | None, args.output))
        return 0
    except (
        FinalizationError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _parse_enum(value: str, enum: type[_EnumT], label: str) -> _EnumT:
    try:
        return enum(value)
    except ValueError as exc:
        raise FinalizationError(f"invalid {label}: {value!r}") from exc


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="finalize",
        description="Finalize a Mold spec and publish only a consumer-valid handoff.",
    )
    _ = parser.add_argument("spec", type=Path)
    _ = parser.add_argument("--approval", type=Path)
    _ = parser.add_argument("--artifact-root", required=True, type=Path)
    _ = parser.add_argument("--operation-id", required=True)
    _ = parser.add_argument("--request-id", required=True)
    _ = parser.add_argument("--input-kind", default=MoldCookInputKind.DIRECT_SPEC.value)
    _ = parser.add_argument("--mode", default=MoldCookMode.FULL.value)
    _ = parser.add_argument("--planner-result", type=Path)
    _ = parser.add_argument("--plan", type=Path)
    _ = parser.add_argument("--coverage", type=Path)
    _ = parser.add_argument("--taste-result", type=Path)
    _ = parser.add_argument("--ledger", type=Path)
    _ = parser.add_argument("--curdle-anyway", action="store_true")
    args = parser.parse_args(argv)
    try:
        taste_path = cast(Path | None, args.taste_result)
        ledger_path = cast(Path | None, args.ledger)
        taste: object | None = (
            None if taste_path is None else read_json_artifact(taste_path)
        )
        ledger: object | None = (
            None if ledger_path is None else read_json_artifact(ledger_path)
        )
        outcome = finalize_mold(
            cast(Path, args.spec),
            artifact_root=cast(Path, args.artifact_root),
            operation_id=cast(str, args.operation_id),
            request_id=cast(str, args.request_id),
            input_kind=_parse_enum(
                cast(str, args.input_kind), MoldCookInputKind, "input kind"
            ),
            mode=_parse_enum(cast(str, args.mode), MoldCookMode, "mode"),
            approval=cast(Path | None, args.approval),
            planner_result=cast(Path | None, args.planner_result),
            plan=cast(Path | None, args.plan),
            proposed_coverage=cast(Path | None, args.coverage),
            taste_result=cast(
                ForkTasteVerdict | Mapping[str, object] | Path | None, taste
            ),
            decision_ledger=ledger,
            curdle_anyway=cast(bool, args.curdle_anyway),
        )
        _write_json_output(outcome.to_dict(), None)
        return 0
    except (
        FinalizationError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
