"""Request classification and the processing source each ingress resolves."""

from __future__ import annotations

from pathlib import Path

import attrs

from easy_cheese_schemas import require_contract_version
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    CookPreparationResult,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese.shared.mold_cook_handoff import evaluate_mold_cook_spec
from easy_cheese.shared.wheypoint.resolve import ResolutionOutcome, resolve

from ._types import (
    ClassifiedCookInput,
    CookInputError,
    CookPreparationRequest,
    PreparationContext,
    PreparationEvidence,
    PreparationFailure,
    ResolvedPreparationSource,
)
from .classify import classify_input, coerce_kind, derive_request_id
from .evidence import as_path, persist_request, persist_value, resolve_ref, source_ref
from .outcomes import hold_result, invalid_result
from .pointer import resolve_canonical_pointer
from .results import validate_preparation_result
from .spec import resolve_spec_ref, spec_readiness


def classify_request(
    source: str | Path | ClassifiedCookInput,
    *,
    request_id: str | None,
    root: Path,
    artifacts: Path,
    mode: MoldCookMode,
    explicit_kind: MoldCookInputKind | str | None,
    evidence: PreparationEvidence,
) -> PreparationContext | CookPreparationResult:
    """Classify the host input and persist the request that records it."""

    try:
        classified = (
            source
            if isinstance(source, ClassifiedCookInput)
            else classify_input(source, explicit_kind=explicit_kind)
        )
    except CookInputError as exc:
        fallback = ClassifiedCookInput(
            coerce_kind(explicit_kind) or MoldCookInputKind.TASK,
            str(source),
            as_path(source) if isinstance(source, (str, Path)) else None,
            explicit_kind is not None,
        )
        request = CookPreparationRequest(
            request_id=request_id or derive_request_id(fallback, None),
            source=fallback,
            repository_root=root,
            artifact_root=artifacts,
            mode=mode,
            explicit_kind=coerce_kind(explicit_kind),
            holds=tuple(evidence.holds),
        )
        return invalid_result(
            request,
            fallback,
            [persist_request(request)],
            PreparationFailure("invalid-input", str(exc)),
        )

    request = CookPreparationRequest(
        request_id=request_id or derive_request_id(classified, None),
        source=classified,
        repository_root=root,
        artifact_root=artifacts,
        mode=mode,
        explicit_kind=coerce_kind(explicit_kind),
        holds=tuple(evidence.holds),
    )
    return PreparationContext(
        request=request,
        classified=classified,
        refs=[persist_request(request)],
        evidence=evidence,
        root=root,
        artifacts=artifacts,
        previous=evidence.previous,
    )


def bind_previous_result(ctx: PreparationContext) -> PreparationContext:
    """Validate and persist the previous round this resubmission carries."""

    if ctx.previous is None:
        return ctx
    previous_result = validate_preparation_result(ctx.previous)
    ctx.refs.append(
        persist_value(
            ctx.artifacts,
            previous_result,
            artifact_id=f"{ctx.request.request_id}/previous-result",
            role="preparation_result",
            schema_uri=require_contract_version(CookPreparationResult).schema_uri,
        )
    )
    return attrs.evolve(ctx, previous=previous_result)


def _resolve_pointer_source(
    ctx: PreparationContext,
) -> ResolvedPreparationSource | CookPreparationResult:
    """Resolve a canonical publication index."""

    classified = ctx.classified
    if classified.path is None:
        raise PreparationFailure("missing-pointer", "canonical pointer input must name a file")
    result = resolve_canonical_pointer(
        classified,
        ctx.request,
        runner_approval=ctx.evidence.runner_approval,
        setup_authorization=ctx.evidence.setup_authorization,
        setup_evidence=ctx.evidence.setup_evidence,
    )
    return validate_preparation_result(
        attrs.evolve(result, references=tuple((*ctx.refs, *result.references)))
    )


def _resolve_continuation_source(
    ctx: PreparationContext,
) -> ResolvedPreparationSource | CookPreparationResult:
    """Resolve a continuation, adapting or holding on a legacy one."""

    classified = ctx.classified
    request = ctx.request
    artifacts = ctx.artifacts
    refs = ctx.refs
    refs.append(source_ref(classified, artifacts, request.request_id))
    resolution = resolve(classified.source, workspace_root=ctx.root)
    if resolution.outcome in {
        ResolutionOutcome.AUTHORITATIVE,
        ResolutionOutcome.NOT_FOUND,
    }:
        return ResolvedPreparationSource(
            processing_source=ClassifiedCookInput(
                MoldCookInputKind.TASK,
                classified.source,
            ),
            objective=classified.source,
        )
    if resolution.outcome is ResolutionOutcome.LEGACY:
        raise PreparationFailure(
            "legacy-continuation",
            resolution.detail or "legacy continuation is not supported",
        )
    hold_kind = (
        CookHoldKind.INTEGRITY
        if resolution.outcome is ResolutionOutcome.ERROR
        else CookHoldKind.BLOCKED
    )
    return validate_preparation_result(
        hold_result(
            request,
            classified,
            refs,
            (
                CookExecutionHold(
                    hold_id=f"continuation-{request.request_id}",
                    kind=hold_kind,
                    reason=resolution.detail
                    or f"continuation is {resolution.outcome.value}",
                ),
            ),
        )
    )


def resolve_preparation_source(
    ctx: PreparationContext,
) -> ResolvedPreparationSource | CookPreparationResult:
    """Resolve the processing source and any spec the input already names."""

    classified = ctx.classified
    artifacts = ctx.artifacts
    if classified.kind is MoldCookInputKind.DIRECT_SPEC:
        if classified.path is None:
            raise PreparationFailure(
                "missing-spec",
                "direct spec input must name a file",
            )
        spec_ref, objective = resolve_spec_ref(
            classified, artifacts, ctx.request.request_id
        )
        return ResolvedPreparationSource(
            processing_source=classified,
            objective=objective,
            spec_ref=spec_ref,
            readiness=evaluate_mold_cook_spec(
                resolve_ref(spec_ref, artifacts),
                spec_ref=spec_ref,
            ),
        )
    if classified.kind is MoldCookInputKind.SLUG:
        spec_ref, objective = resolve_spec_ref(
            classified, artifacts, ctx.request.request_id
        )
        return ResolvedPreparationSource(
            processing_source=classified,
            objective=objective,
            spec_ref=spec_ref,
            readiness=spec_readiness(
                classified,
                spec_ref=spec_ref,
                raw=resolve_ref(spec_ref, artifacts),
            ),
        )
    if classified.kind is MoldCookInputKind.CANONICAL_POINTER:
        return _resolve_pointer_source(ctx)
    if classified.kind is MoldCookInputKind.CONTINUATION:
        return _resolve_continuation_source(ctx)
    return ResolvedPreparationSource(
        processing_source=classified,
        objective=classified.source,
    )
