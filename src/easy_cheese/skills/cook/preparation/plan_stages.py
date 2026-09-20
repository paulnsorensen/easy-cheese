"""The planner, plan, approval, and runner stages of one preparation round."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    ArtifactRef,
    CurdPlan,
    PlannerDisposition,
    PlannerRequest,
    PlannerResult,
    require_contract_version,
    validate_contract,
)
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    CookPreparationOutcome,
    CookPreparationResult,
    CookRequirementKind,
    CookUnmetRequirement,
    MoldCookApprovalKind,
    MoldCookCoverage,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared.mold_cook_handoff import canonical_mold_cook_proposal
from easy_cheese.shared.workflow import plan as workflow_plan

from ._types import (
    ApprovedPlan,
    CookEvidenceError,
    DependencyClosureError,
    MaterializedPlan,
    PreparationContext,
    ResolvedPreparationSource,
    SpecStage,
)
from .approval import (
    approval_value,
    build_planner_request,
    check_approval,
    check_previous_proposal,
    coverage_for_plan,
    persist_proposal,
)
from .evidence import load_contract, persist_bytes, persist_value, read_path
from .outcomes import hold_result, publish_handoff, ready_result
from .results import validate_preparation_result
from .setup import apply_runner_setup


def stage_planner_result(
    ctx: PreparationContext,
    spec: SpecStage,
    resolved: ResolvedPreparationSource,
    scope_ref: ArtifactRef | None,
) -> PlannerResult | CookPreparationResult:
    """Obtain the planner result, or return the round that asks for one."""

    if resolved.planner_value is not None:
        return resolved.planner_value
    request = ctx.request
    classified = ctx.classified
    refs = ctx.refs
    evidence = ctx.evidence
    planner_value: PlannerResult | None = None
    planner_source = evidence.planner_result
    if planner_source is None and evidence.planner_view is None:
        return validate_preparation_result(
            _planning_result(ctx, spec.objective, scope_ref)
        )
    if planner_source is None:
        planner_request = build_planner_request(request, spec.objective)
        dispatch = evidence.planner_dispatch
        if evidence.planner_view is not None:

            def planner_view_dispatch(_request: PlannerRequest) -> object:
                return evidence.planner_view

            dispatch = planner_view_dispatch
        if dispatch is None:
            raise CookEvidenceError("planner output requires an orchestrator callback")
        try:
            planner_value = workflow_plan(planner_request, dispatch)
        except (ContractValidationError, TypeError, ValueError) as exc:
            return validate_preparation_result(
                hold_result(
                    request,
                    classified,
                    refs,
                    holds=(
                        CookExecutionHold(
                            hold_id=f"planner-{request.request_id}",
                            kind=CookHoldKind.INTEGRITY,
                            reason=f"planner execution failed: {exc}",
                        ),
                    ),
                )
            )
    elif isinstance(planner_source, PlannerResult):
        planner_value = planner_source
    elif isinstance(planner_source, ArtifactRef):
        planner_value = cast(
            PlannerResult,
            load_contract(planner_source, PlannerResult, ctx.artifacts),
        )
        refs.append(planner_source)
    else:
        planner_raw = read_path(Path(planner_source).expanduser())
        planner_value = cast(
            PlannerResult,
            validate_contract(
                planner_raw,
                PlannerResult,
                require_contract_version(PlannerResult),
            ).value,
        )
        refs.append(
            persist_bytes(
                ctx.artifacts,
                content=planner_raw,
                artifact_id=f"{request.request_id}/planner-result",
                role="planner_result",
                media_type="application/json",
                schema_uri=require_contract_version(PlannerResult).schema_uri,
            )
        )
    assert planner_value is not None
    return planner_value


def _planning_result(
    ctx: PreparationContext,
    objective: str,
    scope_ref: ArtifactRef | None,
) -> CookPreparationResult:
    """Build the round that returns a planner request to the orchestrator."""

    references = (*ctx.refs, scope_ref) if scope_ref is not None else tuple(ctx.refs)
    return CookPreparationResult(
        contract_version=require_contract_version(CookPreparationResult),
        request_id=ctx.request.request_id,
        input_kind=ctx.classified.kind,
        outcome=CookPreparationOutcome.NEEDS_PLANNING,
        references=references,
        approved_scope_ref=scope_ref,
        planner_request=build_planner_request(ctx.request, objective),
    )


def stage_plan_material(
    ctx: PreparationContext,
    spec: SpecStage,
    resolved: ResolvedPreparationSource,
    planner_value: PlannerResult,
    scope_ref: ArtifactRef | None,
) -> MaterializedPlan | CookPreparationResult:
    """Persist the planner result and its plan, or return the blocked round."""

    request = ctx.request
    refs = ctx.refs
    planner_ref = resolved.planner_ref
    if planner_ref is None:
        planner_ref = persist_value(
            ctx.artifacts,
            planner_value,
            artifact_id=f"{request.request_id}/planner-result",
            role="planner_result",
            schema_uri=require_contract_version(PlannerResult).schema_uri,
        )
        refs.append(planner_ref)
    if planner_value.disposition in {
        PlannerDisposition.BLOCKED,
        PlannerDisposition.EXECUTOR_FAILURE,
        PlannerDisposition.NO_WORK,
    }:
        requirement_kind = (
            CookRequirementKind.INTEGRITY
            if planner_value.disposition is PlannerDisposition.EXECUTOR_FAILURE
            else CookRequirementKind.PLAN
        )
        return validate_preparation_result(
            hold_result(
                request,
                ctx.classified,
                refs,
                requirements=(
                    CookUnmetRequirement(
                        requirement_id=f"planner-{planner_value.disposition.value}",
                        kind=requirement_kind,
                        description=(
                            planner_value.reason or planner_value.disposition.value
                        ),
                        evidence=(planner_ref,),
                    ),
                ),
            )
        )
    if planner_value.plan is None:
        return validate_preparation_result(
            _planning_result(ctx, spec.objective, scope_ref)
        )
    plan = planner_value.plan
    plan_ref = resolved.plan_ref
    if plan_ref is None:
        plan_ref = persist_value(
            ctx.artifacts,
            plan,
            artifact_id=f"{request.request_id}/curd-plan",
            role="curd_plan",
            schema_uri=require_contract_version(CurdPlan).schema_uri,
        )
        refs.append(plan_ref)
    return MaterializedPlan(
        planner_ref=planner_ref,
        plan=plan,
        plan_ref=plan_ref,
        candidate_coverage=MoldCookCoverage(
            curd_ids=tuple(curd.curd_id for curd in plan.curds),
            unresolved_work=planner_value.unresolved_work,
        ),
    )


def stage_plan_approval(
    ctx: PreparationContext,
    spec: SpecStage,
    planner_value: PlannerResult,
    material: MaterializedPlan,
    scope_ref: ArtifactRef | None,
) -> ApprovedPlan | CookPreparationResult:
    """Bind explicit plan approval, or return the plan proposal round."""

    request = ctx.request
    refs = ctx.refs
    expected_kind = (
        MoldCookApprovalKind.PARTIAL_PLAN
        if planner_value.disposition is PlannerDisposition.PARTIAL
        else MoldCookApprovalKind.PLAN
    )
    if ctx.evidence.plan_approval is None:
        proposal_ref = persist_proposal(
            request,
            canonical_mold_cook_proposal(
                request_id=request.request_id,
                kind=expected_kind,
                spec_digest=spec.spec_ref.digest,
                coverage=material.candidate_coverage,
                planner_result=planner_value,
                plan_digest=material.plan.digest,
            ),
            artifact_id=f"{request.request_id}/plan-proposal",
        )
        references = (*refs, scope_ref) if scope_ref is not None else tuple(refs)
        return validate_preparation_result(
            CookPreparationResult(
                contract_version=require_contract_version(CookPreparationResult),
                request_id=request.request_id,
                input_kind=ctx.classified.kind,
                outcome=CookPreparationOutcome.NEEDS_APPROVAL,
                references=tuple((*references, proposal_ref)),
                approval_kind=expected_kind,
                proposal_ref=proposal_ref,
                proposal_digest=proposal_ref.digest,
                missing_decision="explicit plan approval",
            )
        )
    approval, approval_ref = approval_value(ctx.evidence.plan_approval, request=request)
    expected_proposal = canonical_mold_cook_proposal(
        request_id=request.request_id,
        kind=expected_kind,
        spec_digest=spec.spec_ref.digest,
        coverage=approval.coverage,
        planner_result=planner_value,
        plan_digest=material.plan.digest,
    )
    check_previous_proposal(
        ctx.previous,
        kind=expected_kind,
        expected_proposal=expected_proposal,
        artifacts=ctx.artifacts,
    )
    check_approval(
        approval,
        approval_ref=approval_ref,
        request=request,
        spec_ref=spec.spec_ref,
        expected=expected_kind,
        expected_proposal=expected_proposal,
    )
    try:
        coverage = coverage_for_plan(planner_value, material.plan, approval)
    except DependencyClosureError:
        planner_request = build_planner_request(
            request,
            "replan approval coverage with its required dependencies",
            source_plan=planner_value,
        )
        return validate_preparation_result(
            CookPreparationResult(
                contract_version=require_contract_version(CookPreparationResult),
                request_id=request.request_id,
                input_kind=ctx.classified.kind,
                outcome=CookPreparationOutcome.NEEDS_PLANNING,
                references=tuple((*refs, approval_ref)),
                approved_scope_ref=scope_ref,
                planner_request=planner_request,
            )
        )
    return ApprovedPlan(approval_ref=approval_ref, coverage=coverage)


def stage_runner_setup(
    ctx: PreparationContext,
    spec: SpecStage,
    material: MaterializedPlan,
    approved: ApprovedPlan,
) -> CookPreparationResult:
    """Apply runner setup and publish the handoff this round authorizes."""

    request = ctx.request
    classified = ctx.classified
    refs = ctx.refs
    refs.append(approved.approval_ref)
    applied = apply_runner_setup(
        request,
        classified,
        refs,
        authority_request=request,
        runner_approval=ctx.evidence.runner_approval,
        setup_evidence=ctx.evidence.setup_evidence,
        spec_ref=spec.spec_ref,
        coverage=approved.coverage,
        plan=material.plan,
        plan_ref=material.plan_ref,
    )
    if isinstance(applied, CookPreparationResult):
        return applied
    handoff_ref = publish_handoff(
        request,
        source=classified,
        spec_ref=spec.spec_ref,
        approval_ref=approved.approval_ref,
        coverage=approved.coverage,
        planner_result_ref=material.planner_ref,
        plan_ref=material.plan_ref,
        taste_verdict_ref=(
            None if spec.readiness is None else spec.readiness.taste_verdict_ref
        ),
        taste_ledger_ref=(
            None if spec.readiness is None else spec.readiness.taste_ledger_ref
        ),
        runner_approval_ref=applied.runner_approval_ref,
        setup_evidence_refs=applied.setup_evidence_refs,
    )
    return validate_preparation_result(
        ready_result(request, classified, refs, handoff_ref, approved.coverage)
    )
