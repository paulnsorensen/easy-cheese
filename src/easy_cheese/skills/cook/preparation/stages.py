"""The spec and scope stages of one preparation round."""

from __future__ import annotations

import attrs

from easy_cheese_schemas import ArtifactRef
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    CookPreparationResult,
    CookRequirementKind,
    CookUnmetRequirement,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese.shared.mold_cook_handoff import (
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


def stage_scope(
    ctx: PreparationContext,
    spec: SpecStage,
    resolved: ResolvedPreparationSource,
) -> CookPreparationResult | ArtifactRef | None:
    """Bind the invocation's unchanged spec as the scope; Light publishes here."""

    if resolved.legacy_mode:
        return None
    request = ctx.request
    classified = ctx.classified
    refs = ctx.refs
    if ctx.previous is not None and any(
        ref.role == "spec" and ref.digest != spec.spec_ref.digest
        for ref in ctx.previous.references
    ):
        raise CookEvidenceError("resubmission changed the bound spec")
    scope_ref = attrs.evolve(spec.spec_ref, role="approved_scope")
    refs.append(scope_ref)
    if request.mode is not MoldCookMode.LIGHT:
        return scope_ref
    coverage = host_scope_coverage(spec.readiness, resolved.planner_value)
    if coverage is None:
        return validate_preparation_result(
            hold_result(
                request,
                classified,
                refs,
                requirements=(
                    CookUnmetRequirement(
                        requirement_id=f"light-scope-{request.request_id}",
                        kind=CookRequirementKind.SCOPE,
                        description="Light Cook needs a spec that declares exactly one curd",
                        evidence=(spec.spec_ref,),
                    ),
                ),
            )
        )
    if len(coverage.curd_ids) != 1 or coverage.unresolved_work:
        raise CookEvidenceError("Light scope must name exactly one resolved curd")
    handoff_ref = publish_handoff(
        request,
        source=classified,
        spec_ref=spec.spec_ref,
        coverage=coverage,
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
        ready_result(request, classified, refs, handoff_ref, coverage)
    )
