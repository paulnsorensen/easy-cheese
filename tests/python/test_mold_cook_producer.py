from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared.mold_cook_handoff import (
    bind_mold_cook_approval,
    canonical_mold_cook_proposal,
    materialize_artifact_ref,
)
from easy_cheese.shared.publication import accept_mold_cook_handoff
from easy_cheese.shared.taste_test import ForkTasteVerdict
from easy_cheese.skills.mold.producer import (
    FinalizationOutcome,
    finalize_mold,
    normalize_planner_result,
)
from easy_cheese_schemas.contracts import (
    BoundedScope,
    CriterionWriterView,
    CurdPlan,
    CurdPlanWriterView,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    PlannerResultWriterView,
    SemanticCurdWriterView,
)
from easy_cheese_schemas.mold_cook import (
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import supported_version_for


FIXTURE = Path(__file__).parent / "fixtures" / "spec_format" / "valid_spec.md"


def make_spec(
    tmp_path: Path,
    *,
    landing_id: str | None = None,
    do_not_implement: bool = False,
) -> Path:
    text = FIXTURE.read_text(encoding="utf-8")
    if landing_id is not None:
        replacement = (
            'gates_overridden: []\nlanding:\n  shape: stacked_linear\n  layers: [["'
            + landing_id
            + '"]]\n  per_layer_green: required\n  review_fixes: fold\n'
        )
        text = text.replace("gates_overridden: []\n", replacement)
    if do_not_implement:
        text = text.replace(
            "gates_overridden: []\n",
            "gates_overridden: []\nrequest_directive: do-not-implement\n",
            1,
        )
    path = tmp_path / "spec.md"
    _ = path.write_text(text, encoding="utf-8")
    return path


def taste_fixture(spec_path: Path, *, passed: bool = True) -> ForkTasteVerdict:
    return ForkTasteVerdict.from_mapping(
        {
            "draft_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            "verdict": "pass" if passed else "fail",
            "forks": [],
            "contradictions": [],
            "orphaned_decisions": [],
            "unsupported_assumptions": [],
            "acceptance_gaps": [] if passed else ["failed-fork"],
        }
    )


def make_planner_result() -> PlannerResult:
    version = supported_version_for(PlannerRequest)
    request = cast(Callable[..., PlannerRequest], PlannerRequest)(
        contract_version=version,
        request_id="request-1",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Implement the Mold to Cook boundary",
    )
    writer = cast(Callable[..., PlannerResultWriterView], PlannerResultWriterView)(
        disposition=PlannerDisposition.COMPLETE,
        plan=cast(Callable[..., CurdPlanWriterView], CurdPlanWriterView)(
            objective=request.objective,
            curds=[
                cast(Callable[..., SemanticCurdWriterView], SemanticCurdWriterView)(
                    key="core",
                    outcome="Implement the canonical boundary",
                    scope=cast(Callable[..., BoundedScope], BoundedScope)(
                        paths=["src/core.py"]
                    ),
                    outputs=["A consumer-valid handoff"],
                    criteria=[
                        cast(Callable[..., CriterionWriterView], CriterionWriterView)(
                            description="The handoff is consumer-valid",
                            check="pytest tests/python/test_mold_cook_producer.py",
                        )
                    ],
                )
            ],
        ),
    )
    return normalize_planner_result(
        request,
        writer,
        plan_id="plan-1",
        curd_ids={"core": "curd-1"},
    )


def make_approval(
    tmp_path: Path,
    spec_path: Path,
    *,
    plan: PlannerResult | None,
    coverage: MoldCookCoverage | None = None,
) -> MoldCookApproval:
    selected_coverage = coverage or cast(
        Callable[..., MoldCookCoverage], MoldCookCoverage
    )(
        curd_ids=["curd-1"],
    )
    plan_digest = None if plan is None else cast(CurdPlan, plan.plan).digest
    proposal = canonical_mold_cook_proposal(
        request_id="request-1",
        kind=MoldCookApprovalKind.PLAN,
        spec_digest="sha256:" + hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        coverage=selected_coverage,
        planner_result=plan,
        plan_digest=plan_digest,
    )
    response = b"approved\n"
    evidence_root = tmp_path / "artifacts" / "approval-evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    proposal_path = evidence_root / "proposal.json"
    response_path = evidence_root / "response.txt"
    _ = proposal_path.write_bytes(proposal)
    _ = response_path.write_bytes(response)
    proposal_ref = materialize_artifact_ref(
        proposal,
        artifact_id="proposal-1",
        role="proposal",
        uri=proposal_path.resolve().as_uri(),
        media_type="application/json",
    )
    response_ref = materialize_artifact_ref(
        response,
        artifact_id="response-1",
        role="response",
        uri=response_path.resolve().as_uri(),
        media_type="text/plain",
    )
    return bind_mold_cook_approval(
        request_id="request-1",
        kind=MoldCookApprovalKind.PLAN,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest="sha256:" + hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text=response.decode(),
        response_source="response.txt",
        coverage=selected_coverage,
        plan_digest=plan_digest,
    )


_MISSING_APPROVAL = object()


def finalize_fixture(
    tmp_path: Path,
    *,
    spec_path: Path | None = None,
    approval: MoldCookApproval
    | Mapping[str, object]
    | Path
    | None
    | object = _MISSING_APPROVAL,
    planner: PlannerResult | None = None,
    taste: ForkTasteVerdict | None = None,
    curdle_anyway: bool = False,
) -> FinalizationOutcome:
    spec = spec_path or make_spec(tmp_path)
    selected_plan = planner or make_planner_result()
    selected_approval = (
        make_approval(tmp_path, spec, plan=selected_plan)
        if approval is _MISSING_APPROVAL
        else cast(MoldCookApproval | Mapping[str, object] | Path | None, approval)
    )
    return finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.FULL,
        approval=selected_approval,
        planner_result=selected_plan,
        plan=cast(CurdPlan, selected_plan.plan),
        taste_result=taste or taste_fixture(spec),
        decision_ledger=(),
        curdle_anyway=curdle_anyway,
    )


def test_complete_finalization_publishes_a_pointer_consumers_can_accept(
    tmp_path: Path,
) -> None:
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    assert outcome.ready is True
    pointer_path = tmp_path / "artifacts" / "pointers" / "operation-1.json"
    accepted = accept_mold_cook_handoff(
        pointer_path, artifact_root=tmp_path / "artifacts"
    )
    accepted_handoff = cast(MoldCookHandoff, accepted.canonical.value)
    assert accepted_handoff.request_id == "request-1"
    assert outcome.payload["next"] == "cook"


def test_failed_taste_is_saved_without_execution_authority(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    outcome = finalize_fixture(
        tmp_path, spec_path=spec, taste=taste_fixture(spec, passed=False)
    )

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert outcome.payload["requirements"] == [
        {
            "requirement_id": "taste-verdict",
            "kind": "evidence",
            "description": "taste verdict did not pass: failed-fork",
            "evidence": [],
        }
    ]
    assert "pointer" not in outcome.payload


def test_missing_approval_is_saved_without_execution_authority(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path, approval=None)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert outcome.payload["requirements"] == [
        {
            "requirement_id": "approval-evidence",
            "kind": "approval",
            "description": "explicit approval evidence is required before publication",
            "evidence": [],
        },
        {
            "requirement_id": "scope-approval",
            "kind": "scope",
            "description": "approved scope coverage is required before finalization",
            "evidence": [],
        },
    ]
    assert "pointer" not in outcome.payload


def test_invalid_landing_id_is_saved_without_execution_authority(
    tmp_path: Path,
) -> None:
    spec = make_spec(tmp_path, landing_id="not-a-plan-curd")
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    requirements = cast(Sequence[Mapping[str, object]], outcome.payload["requirements"])
    assert tuple(
        (item["requirement_id"], item["kind"], item["evidence"])
        for item in requirements
    ) == (("landing-declaration", "integrity", []),)
    assert "pointer" not in outcome.payload


def test_do_not_implement_hold_blocks_ready_publication(tmp_path: Path) -> None:
    spec = make_spec(tmp_path, do_not_implement=True)
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert outcome.payload["holds"] == [
        {
            "hold_id": "user-do-not-implement",
            "kind": "user_intent",
            "reason": "whole-request directive 'do-not-implement' blocks execution",
            "evidence": [],
        }
    ]


def test_stale_approval_reference_is_saved_not_ready(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    approval = make_approval(tmp_path, spec, plan=make_planner_result())
    stale = bind_mold_cook_approval(
        request_id=approval.request_id,
        kind=approval.kind,
        decision=approval.decision,
        source=approval.source,
        spec_digest="sha256:" + "0" * 64,
        proposal_ref=approval.proposal_ref,
        response_ref=approval.response_ref,
        response_text=approval.response_text,
        response_source=approval.response_source,
        coverage=approval.coverage,
        plan_digest=approval.plan_digest,
    )
    outcome = finalize_fixture(tmp_path, spec_path=spec, approval=stale)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    requirements = cast(Sequence[Mapping[str, object]], outcome.payload["requirements"])
    assert tuple(
        (item["requirement_id"], item["kind"], item["evidence"])
        for item in requirements
    ) == (("approval-spec", "integrity", []),)


def test_curdle_anyway_is_save_only_and_records_a_hold(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path, curdle_anyway=True)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert outcome.payload["holds"] == [
        {
            "hold_id": "curdle-anyway",
            "kind": "preparation",
            "reason": "curdle anyway is save-only and never waives execution readiness",
            "evidence": [],
        }
    ]
    assert "pointer" not in outcome.payload


@pytest.mark.parametrize("extra", ["failed taste", "missing approval"])
def test_non_ready_results_are_durable(tmp_path: Path, extra: str) -> None:
    if extra == "failed taste":
        spec = make_spec(tmp_path)
        outcome = finalize_fixture(
            tmp_path, spec_path=spec, taste=taste_fixture(spec, passed=False)
        )
    else:
        outcome = finalize_fixture(tmp_path, approval={})

    assert outcome.result_path is not None
    assert outcome.result_path.is_file()
    assert outcome.payload["saved"] is True
