from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest
from easy_cheese.skills.mold.producer import (
    FinalizationError,
    normalize_planner_result,
)
from easy_cheese_schemas.contracts import (
    BoundedScope,
    CriterionWriterView,
    CurdPlanWriterView,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResultWriterView,
    SemanticCurdWriterView,
    canonical_bytes,
)
from easy_cheese_schemas.planner import materialize_planner_result
from easy_cheese_schemas.schema_runtime import supported_version_for


def _request() -> PlannerRequest:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    return cast(Callable[..., PlannerRequest], PlannerRequest)(
        contract_version=version,
        request_id="normalization-request",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Materialize the canonical planner result",
    )


def _writer() -> PlannerResultWriterView:
    return cast(Callable[..., PlannerResultWriterView], PlannerResultWriterView)(
        disposition=PlannerDisposition.COMPLETE,
        plan=cast(Callable[..., CurdPlanWriterView], CurdPlanWriterView)(
            objective="Materialize the canonical planner result",
            curds=[
                cast(Callable[..., SemanticCurdWriterView], SemanticCurdWriterView)(
                    key="planner",
                    outcome="Create a canonical plan",
                    scope=cast(Callable[..., BoundedScope], BoundedScope)(
                        paths=["src/planner.py"]
                    ),
                    outputs=["A typed planner result"],
                    criteria=[
                        cast(Callable[..., CriterionWriterView], CriterionWriterView)(
                            description="The plan has canonical identity",
                            check="pytest tests/python/test_mold_planner_normalization.py",
                        )
                    ],
                )
            ],
        ),
    )


def test_normalization_returns_the_same_canonical_result_as_host_materialization() -> None:
    request = _request()
    writer = _writer()

    normalized = normalize_planner_result(
        request,
        writer,
        plan_id="planner-plan-1",
        curd_ids={"planner": "planner-curd-1"},
    )
    direct = materialize_planner_result(
        request,
        writer,
        plan_id="planner-plan-1",
        curd_ids={"planner": "planner-curd-1"},
    )

    assert normalized == direct
    assert canonical_bytes(normalized) == canonical_bytes(direct)
    assert normalized.plan is not None
    assert normalized.plan.plan_id == "planner-plan-1"
    assert normalized.plan.curds[0].curd_id == "planner-curd-1"


def test_normalization_rejects_a_bare_writer_mapping() -> None:
    with pytest.raises(FinalizationError):
        _ = normalize_planner_result(
            _request(),
            {"payload": _writer()},
            plan_id="planner-plan-1",
            curd_ids={"planner": "planner-curd-1"},
        )
