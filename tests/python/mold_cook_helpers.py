"""Test-only builders for Mold-to-Cook approval contracts.

Production code binds approvals through the Mold producer and the Cook
preparation pipeline. Only tests need a direct constructor, so it lives here
rather than on the host seam.
"""

from __future__ import annotations

from easy_cheese_schemas.contracts import ArtifactRef, ContractVersion
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    CookSetupAuthorization,
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
    MoldCookCoverage,
)

__all__ = ["bind_mold_cook_approval"]


def bind_mold_cook_approval(
    *,
    request_id: str,
    kind: MoldCookApprovalKind,
    decision: MoldCookApprovalDecision,
    source: MoldCookApprovalSource,
    spec_digest: str,
    proposal_ref: ArtifactRef,
    response_ref: ArtifactRef,
    response_text: str,
    response_source: str,
    coverage: MoldCookCoverage,
    plan_digest: str | None = None,
    setup_authorization: CookSetupAuthorization | None = None,
) -> MoldCookApproval:
    """Bind explicit response evidence to stable proposal and response refs."""

    version = ContractVersion(
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
        major="1",
        minor="0",
    )
    return MoldCookApproval(
        contract_version=version,
        request_id=request_id,
        kind=kind,
        decision=decision,
        source=source,
        spec_digest=spec_digest,
        proposal_ref=proposal_ref,
        proposal_digest=proposal_ref.digest,
        response_ref=response_ref,
        response_digest=response_ref.digest,
        response_text=response_text,
        response_source=response_source,
        coverage=coverage,
        plan_digest=plan_digest,
        setup_authorization=setup_authorization,
    )
