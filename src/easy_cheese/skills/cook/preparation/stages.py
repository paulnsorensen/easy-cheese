"""The spec and scope stages of one preparation round."""

from __future__ import annotations

import attrs

from easy_cheese_schemas import ArtifactRef, require_contract_version
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    CookPreparationOutcome,
    CookPreparationResult,
    MoldCookApprovalKind,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese.shared.mold_cook_handoff import (
    canonical_mold_cook_proposal,
    evaluate_mold_cook_spec,
    host_scope_coverage,
)

from ._types import (
    ClassifiedCookInput,
    CookEvidenceError,
    PreparationContext,
    ResolvedPreparationSource,
    SpecStage,
)
from .approval import (
    approval_value,
    check_approval,
    check_previous_proposal,
    persist_proposal,
)
from .evidence import resolve_ref
from .outcomes import hold_result, publish_handoff, ready_result
from .results import validate_preparation_result
from .spec import bound_spec_ref, continuity_hold, spec_readiness


def stage_spec_binding(
    ctx: PreparationContext,
    resolved: ResolvedPreparationSource,
) -> SpecStage | CookPreparationResult:
    """Bind the canonical spec, then hold on a missing spec or continuity."""

    request = ctx.request
    classified = ctx.classified
    refs = ctx.refs
    artifacts = ctx.artifacts
    processing_source = resolved.processing_source
    objective = resolved.objective
    spec_ref = resolved.spec_ref
    readiness = resolved.readiness
    if ctx.evidence.spec_binding is not None and spec_ref is None:
        spec_ref, objective = bound_spec_ref(ctx.evidence.spec_binding, request=request)
        processing_source = ClassifiedCookInput(
            MoldCookInputKind.TASK,
            objective,
        )
        readiness = evaluate_mold_cook_spec(
            resolve_ref(spec_ref, artifacts),
            spec_ref=spec_ref,
        )
    if spec_ref is None:
        return validate_preparation_result(
            hold_result(
                request,
                classified,
                refs,
                (
                    CookExecutionHold(
                        hold_id=f"missing-spec-{request.request_id}",
                        kind=CookHoldKind.BLOCKED,
                        reason="Cook requires a canonical host-bound Mold spec",
                    ),
                ),
            )
        )
    if spec_ref not in refs:
        refs.append(spec_ref)
    spec_raw = resolve_ref(spec_ref, artifacts)
    if readiness is None:
        readiness = spec_readiness(
            processing_source,
            spec_ref=spec_ref,
            raw=spec_raw,
        )
    if readiness is not None:
        if readiness.holds:
            return validate_preparation_result(
                hold_result(request, classified, refs, readiness.holds)
            )
        continuity = continuity_hold(
            processing_source,
            ctx.root,
            identity=readiness.spec_slug,
        )
        if continuity is not None:
            return validate_preparation_result(
                hold_result(request, classified, refs, (continuity,))
            )
    return SpecStage(
        processing_source=processing_source,
        objective=objective,
        spec_ref=spec_ref,
        spec_raw=spec_raw,
        readiness=readiness,
    )


def stage_scope_approval(
    ctx: PreparationContext,
    spec: SpecStage,
    resolved: ResolvedPreparationSource,
) -> CookPreparationResult | ArtifactRef | None:
    """Bind explicit scope approval, or return the scope proposal round."""

    if resolved.legacy_mode:
        return None
    request = ctx.request
    classified = ctx.classified
    refs = ctx.refs
    proposed_coverage = host_scope_coverage(spec.readiness, resolved.planner_value)
    scope_envelope = (
        None
        if proposed_coverage is None
        else canonical_mold_cook_proposal(
            request_id=request.request_id,
            kind=MoldCookApprovalKind.SCOPE,
            spec_digest=spec.spec_ref.digest,
            coverage=proposed_coverage,
        )
    )
    # Round one displays these bytes and round two compares against them, so
    # both rounds must render the proposal the same way.
    displayed_proposal = spec.spec_raw if scope_envelope is None else scope_envelope
    if ctx.evidence.scope_approval is None:
        proposal_ref = persist_proposal(
            request,
            displayed_proposal,
            artifact_id=f"{request.request_id}/scope-proposal",
        )
        return validate_preparation_result(
            CookPreparationResult(
                contract_version=require_contract_version(CookPreparationResult),
                request_id=request.request_id,
                input_kind=classified.kind,
                outcome=CookPreparationOutcome.NEEDS_APPROVAL,
                references=tuple((*refs, proposal_ref)),
                approval_kind=MoldCookApprovalKind.SCOPE,
                proposal_ref=proposal_ref,
                proposal_digest=proposal_ref.digest,
                missing_decision="explicit scope approval",
            )
        )
    scope, scope_ref = approval_value(ctx.evidence.scope_approval, request=request)
    scope_proposal = (
        canonical_mold_cook_proposal(
            request_id=request.request_id,
            kind=MoldCookApprovalKind.SCOPE,
            spec_digest=spec.spec_ref.digest,
            coverage=scope.coverage,
        )
        if scope_envelope is None
        else scope_envelope
    )
    check_previous_proposal(
        ctx.previous,
        kind=MoldCookApprovalKind.SCOPE,
        expected_proposal=displayed_proposal,
        artifacts=ctx.artifacts,
    )
    check_approval(
        scope,
        approval_ref=scope_ref,
        request=request,
        spec_ref=spec.spec_ref,
        expected=MoldCookApprovalKind.SCOPE,
        expected_proposal=scope_proposal,
    )
    refs.append(scope_ref)
    approved_scope_ref = attrs.evolve(scope_ref, role="approved_scope")
    if request.mode is MoldCookMode.LIGHT:
        if len(scope.coverage.curd_ids) != 1 or scope.coverage.unresolved_work:
            raise CookEvidenceError(
                "Light authorization must name exactly one resolved curd"
            )
        handoff_ref = publish_handoff(
            request,
            source=classified,
            spec_ref=spec.spec_ref,
            approval_ref=scope_ref,
            coverage=scope.coverage,
            planner_result_ref=None,
            plan_ref=None,
            taste_verdict_ref=(
                None if spec.readiness is None else spec.readiness.taste_verdict_ref
            ),
            taste_ledger_ref=(
                None if spec.readiness is None else spec.readiness.taste_ledger_ref
            ),
        )
        return validate_preparation_result(
            ready_result(
                request,
                classified,
                [*refs, approved_scope_ref],
                handoff_ref,
                scope.coverage,
            )
        )
    return approved_scope_ref
