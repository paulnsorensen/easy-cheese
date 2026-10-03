"""Runner approval evidence, planner requests, and plan disposition checks."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from easy_cheese_schemas import (
    ArtifactRef,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    SourcePlanRef,
    require_contract_version,
)
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese_schemas.validate import require_relative_path
from easy_cheese.shared.mold_cook_handoff import validate_mold_cook_approval
from easy_cheese.shared.wheypoint.canonical import digest_bytes

from ._types import (
    CookEvidenceError,
    CookPreparationRequest,
)
from .evidence import (
    is_regular_path,
    load_contract,
    read_path,
)




def approval_value(
    value: MoldCookApproval | ArtifactRef | str | Path | Mapping[str, object],
    *,
    request: CookPreparationRequest,
) -> tuple[MoldCookApproval, ArtifactRef]:
    if isinstance(value, ArtifactRef):
        if (
            value.role not in {"approval", "runner_approval"}
            or value.schema_uri != MOLD_COOK_APPROVAL_SCHEMA_URI
        ):
            raise CookEvidenceError(
                "approval must be a retained MoldCookApproval artifact"
            )
        approval = load_contract(value, MoldCookApproval, request.artifact_root)
        assert isinstance(approval, MoldCookApproval)
        return approval, value
    if isinstance(value, (MoldCookApproval, Mapping)):
        raise CookEvidenceError(
            "raw approval values are not execution authority; pass the host-owned ArtifactRef"
        )
    path = Path(value).expanduser().resolve()
    raw = read_path(path)
    digest = digest_bytes(raw)
    expected = (
        request.artifact_root.resolve() / f"sha256-{digest.removeprefix('sha256:')}"
    )
    if path != expected:
        raise CookEvidenceError("approval must be a retained host artifact reference")
    reference = ArtifactRef(
        artifact_id=f"{request.request_id}/approval",
        role="approval",
        uri=path.as_uri(),
        digest=digest,
        size_bytes=len(raw),
        media_type="application/json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    approval = load_contract(reference, MoldCookApproval, request.artifact_root)
    assert isinstance(approval, MoldCookApproval)
    return approval, reference


def check_approval(
    approval: MoldCookApproval,
    *,
    approval_ref: ArtifactRef,
    request: CookPreparationRequest,
    spec_ref: ArtifactRef,
    expected: MoldCookApprovalKind,
    expected_proposal: bytes | None = None,
) -> None:
    try:
        _ = validate_mold_cook_approval(approval, request.artifact_root)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise CookEvidenceError(str(exc)) from exc
    if approval.request_id != request.request_id:
        raise CookEvidenceError(
            "approval request_id does not match the preparation request"
        )
    if approval.spec_digest != spec_ref.digest:
        raise CookEvidenceError("approval is bound to a different spec")
    if approval.kind is not expected:
        raise CookEvidenceError(
            f"expected {expected.value} approval, got {approval.kind.value}"
        )
    if approval.decision is not MoldCookApprovalDecision.APPROVED:
        raise CookEvidenceError("approval is not an explicit approved response")
    if approval_ref.role not in {"approval", "runner_approval"}:
        raise CookEvidenceError("approval reference has the wrong role")
    # `validate_mold_cook_approval` already resolved the proposal bytes against
    # `proposal_ref.digest`, and the contract binds `proposal_digest` to that
    # same digest, so a second read of the same bytes proves nothing more.
    if expected_proposal is not None and approval.proposal_digest != digest_bytes(
        expected_proposal
    ):
        raise CookEvidenceError(
            "approval proposal is not the canonical envelope for this request"
        )
    if approval.response_source in {
        approval.response_ref.artifact_id,
        approval.response_ref.uri,
    }:
        return
    try:
        source = require_relative_path(
            approval.response_source, "approval response_source"
        )
    except ValueError as exc:
        raise CookEvidenceError(str(exc)) from exc
    response_path = request.artifact_root.resolve() / source
    if not is_regular_path(response_path):
        raise CookEvidenceError("approval response_source is not a host-owned artifact")
    if digest_bytes(read_path(response_path)) != approval.response_ref.digest:
        raise CookEvidenceError(
            "approval response_source is detached from response_ref"
        )


def build_planner_request(
    request: CookPreparationRequest,
    objective: str,
    *,
    source_plan: PlannerResult | None = None,
) -> PlannerRequest:
    if source_plan is None:
        return PlannerRequest(
            contract_version=require_contract_version(PlannerRequest),
            request_id=request.request_id,
            kind=PlannerRequestKind.DECOMPOSE,
            objective=objective[:8192],
        )
    if source_plan.plan is None:
        raise CookEvidenceError("replan request requires a materialized source plan")
    return PlannerRequest(
        contract_version=require_contract_version(PlannerRequest),
        request_id=request.request_id,
        kind=PlannerRequestKind.REPLAN,
        objective=objective[:8192],
        source_plan_ref=SourcePlanRef(
            source_plan.plan.plan_id,
            source_plan.plan.revision,
            source_plan.plan.digest,
        ),
    )


def check_plan_disposition(planner: PlannerResult) -> None:
    if planner.disposition not in {
        PlannerDisposition.COMPLETE,
        PlannerDisposition.PARTIAL,
    }:
        raise CookEvidenceError(
            f"planner disposition {planner.disposition.value} cannot authorize execution"
        )


