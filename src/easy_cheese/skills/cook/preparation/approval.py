"""Explicit approval evidence: proposals, binding checks, and coverage."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from easy_cheese_schemas import (
    ArtifactRef,
    CurdPlan,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    SourcePlanRef,
    require_contract_version,
)
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    CookPreparationResult,
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookCoverage,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese_schemas.validate import require_relative_path
from easy_cheese.shared.mold_cook_handoff import validate_mold_cook_approval
from easy_cheese.shared.wheypoint.canonical import digest_bytes

from ._types import (
    CookEvidenceError,
    CookPreparationRequest,
    DependencyClosureError,
)
from .evidence import (
    is_regular_path,
    load_contract,
    persist_bytes,
    read_path,
    resolve_ref,
)


def persist_proposal(
    request: CookPreparationRequest,
    content: bytes,
    *,
    artifact_id: str,
) -> ArtifactRef:
    return persist_bytes(
        request.artifact_root,
        content=content,
        artifact_id=artifact_id,
        role="proposal",
        media_type="application/json"
        if content.lstrip().startswith(b"{")
        else "text/markdown",
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


def coverage_for_plan(
    planner: PlannerResult,
    plan: CurdPlan,
    approval: MoldCookApproval,
) -> MoldCookCoverage:
    if planner.disposition not in {
        PlannerDisposition.COMPLETE,
        PlannerDisposition.PARTIAL,
    }:
        raise CookEvidenceError(
            f"planner disposition {planner.disposition.value} cannot authorize execution"
        )
    expected_remainder = planner.unresolved_work
    if approval.coverage.unresolved_work != expected_remainder:
        raise CookEvidenceError("approval acknowledges a stale PlannerResult remainder")
    selected = tuple(approval.coverage.curd_ids)
    if len(set(selected)) != len(selected):
        raise CookEvidenceError("approval coverage must not repeat curd IDs")
    declared = {curd.curd_id: curd for curd in plan.curds}
    unknown = set(selected) - declared.keys()
    if unknown:
        raise CookEvidenceError(
            "approval names unknown curd IDs: " + ", ".join(sorted(unknown))
        )
    if planner.disposition is PlannerDisposition.COMPLETE:
        expected = tuple(curd.curd_id for curd in plan.curds)
        if selected != expected:
            raise CookEvidenceError("complete plan approval must cover every curd")
    for curd_id in selected:
        missing = set(declared[curd_id].dependencies) - set(selected)
        if missing:
            raise DependencyClosureError(
                f"approval coverage for {curd_id!r} omits dependencies: "
                + ", ".join(sorted(missing))
            )
    return MoldCookCoverage(
        curd_ids=selected,
        unresolved_work=expected_remainder,
    )


def check_previous_proposal(
    previous_result: CookPreparationResult | None,
    *,
    kind: MoldCookApprovalKind,
    expected_proposal: bytes,
    artifacts: Path,
) -> None:
    """Refuse a resubmission that changes the proposal the host displayed.

    The guard applies only to a previous round that asked for this same
    approval kind; a scope round carried into a plan round proposes different
    bytes by design.
    """

    if previous_result is None or previous_result.proposal_ref is None:
        return
    if previous_result.approval_kind is not kind:
        return
    if resolve_ref(previous_result.proposal_ref, artifacts) != expected_proposal:
        label = "scope" if kind is MoldCookApprovalKind.SCOPE else "plan"
        raise CookEvidenceError(f"resubmission changed the displayed {label} proposal")
