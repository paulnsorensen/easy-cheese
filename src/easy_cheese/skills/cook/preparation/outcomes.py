"""Closed preparation outcomes and the canonical handoff Cook publishes."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from easy_cheese_schemas import (
    SCHEMA_ROOT,
    ArtifactRef,
    canonical_bytes,
    require_contract_version,
)
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookPreparationOutcome,
    CookPreparationResult,
    CookUnmetRequirement,
    CookValidationFinding,
    MoldCookCoverage,
    MoldCookHandoff,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared.mold_cook_handoff import (
    publish_mold_cook_handoff,
    validate_mold_cook_handoff,
)
from easy_cheese.shared.publication import pointer_path
from easy_cheese.shared.wheypoint.canonical import digest_bytes

from ._types import (
    ClassifiedCookInput,
    CookEvidenceError,
    CookPreparationRequest,
    PreparationFailure,
)
from .evidence import read_path, source_ref


def hold_result(
    request: CookPreparationRequest,
    source: ClassifiedCookInput,
    refs: Sequence[ArtifactRef],
    holds: Sequence[CookExecutionHold] = (),
    requirements: Sequence[CookUnmetRequirement] = (),
) -> CookPreparationResult:
    if not holds and not requirements:
        raise CookEvidenceError("blocked preparation requires a hold or requirement")
    return CookPreparationResult(
        contract_version=require_contract_version(CookPreparationResult),
        request_id=request.request_id,
        input_kind=source.kind,
        outcome=CookPreparationOutcome.BLOCKED,
        references=tuple(refs)
        or (source_ref(source, request.artifact_root, request.request_id),),
        holds=tuple(holds),
        requirements=tuple(requirements),
    )


def invalid_result(
    request: CookPreparationRequest,
    source: ClassifiedCookInput,
    refs: Sequence[ArtifactRef],
    failure: PreparationFailure | Exception,
) -> CookPreparationResult:
    if isinstance(failure, PreparationFailure):
        code, message, path = failure.code, str(failure), failure.path
    else:
        code, message, path = "invalid-input", str(failure), None
    return CookPreparationResult(
        contract_version=require_contract_version(CookPreparationResult),
        request_id=request.request_id,
        input_kind=source.kind,
        outcome=CookPreparationOutcome.INVALID,
        references=tuple(refs)
        or (source_ref(source, request.artifact_root, request.request_id),),
        findings=(CookValidationFinding(code=code, message=message, path=path),),
    )


def build_pointer_ref(
    path: Path, *, request_id: str, raw: bytes | None = None
) -> ArtifactRef:
    """Describe one pointer file, reusing bytes the caller already read."""

    content = read_path(path) if raw is None else raw
    return ArtifactRef(
        artifact_id=f"{request_id}/handoff-pointer",
        role="handoff",
        uri=path.resolve().as_uri(),
        digest=digest_bytes(content),
        size_bytes=len(content),
        media_type="application/json",
        schema_uri=f"{SCHEMA_ROOT}/handoff-pointer",
    )


def publish_handoff(
    request: CookPreparationRequest,
    *,
    source: ClassifiedCookInput,
    spec_ref: ArtifactRef,
    approval_ref: ArtifactRef,
    coverage: MoldCookCoverage,
    planner_result_ref: ArtifactRef | None,
    plan_ref: ArtifactRef | None,
    taste_verdict_ref: ArtifactRef | None = None,
    taste_ledger_ref: ArtifactRef | None = None,
    runner_approval_ref: ArtifactRef | None = None,
    setup_evidence_refs: Sequence[ArtifactRef] = (),
) -> ArtifactRef:
    handoff = MoldCookHandoff(
        contract_version=require_contract_version(MoldCookHandoff),
        request_id=request.request_id,
        input_kind=source.kind,
        mode=request.mode,
        spec_ref=spec_ref,
        approval_ref=approval_ref,
        coverage=coverage,
        planner_result_ref=planner_result_ref,
        plan_ref=plan_ref,
        taste_verdict_ref=taste_verdict_ref,
        taste_ledger_ref=taste_ledger_ref,
        runner_approval_ref=runner_approval_ref,
        setup_evidence_refs=tuple(setup_evidence_refs),
    )
    # Every caller checks the runner approval and the setup evidence before it
    # builds this handoff, so publication validates the canonical payload only.
    try:
        validated = validate_mold_cook_handoff(handoff, request.artifact_root)
        canonical = canonical_bytes(validated)
        request_digest = digest_bytes(canonical)
        operation_id = (
            "cook-"
            + hashlib.sha256(
                f"{request.request_id}:{request_digest}".encode()
            ).hexdigest()[:24]
        )
        _ = publish_mold_cook_handoff(
            validated,
            request_digest=request_digest,
            operation_id=operation_id,
            artifact_root=request.artifact_root,
        )
        return build_pointer_ref(
            pointer_path(request.artifact_root, operation_id),
            request_id=request.request_id,
        )
    except (ContractValidationError, CookEvidenceError, ValueError, OSError) as exc:
        raise CookEvidenceError(f"handoff could not be published: {exc}") from exc


def ready_result(
    request: CookPreparationRequest,
    source: ClassifiedCookInput,
    refs: Sequence[ArtifactRef],
    handoff_ref: ArtifactRef,
    coverage: MoldCookCoverage,
) -> CookPreparationResult:
    return CookPreparationResult(
        contract_version=require_contract_version(CookPreparationResult),
        request_id=request.request_id,
        input_kind=source.kind,
        outcome=CookPreparationOutcome.READY,
        references=tuple((*refs, handoff_ref)),
        handoff_ref=handoff_ref,
        coverage=coverage,
    )
