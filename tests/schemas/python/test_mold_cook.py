from __future__ import annotations

import json
from typing import cast

import pytest

from easy_cheese_schemas.contracts import (
    ArtifactRef,
    ContractVersion,
    PlannerRequest,
    PlannerRequestKind,
)
from easy_cheese_schemas.mold_cook import (
    COOK_PREPARATION_RESULT_SCHEMA_URI,
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    MOLD_COOK_HANDOFF_SCHEMA_URI,
    CookExecutionHold,
    CookHoldKind,
    CookPreparationOutcome,
    CookPreparationResult,
    CookRequirementKind,
    CookSetupAuthorization,
    CookUnmetRequirement,
    CookValidationFinding,
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    canonical_bytes,
    supported_version_for,
    validate_contract,
)


DIGEST = "sha256:" + "a" * 64


def version(schema_uri: str) -> ContractVersion:
    return ContractVersion(schema_uri=schema_uri, major="1", minor="0")


def ref(role: str, *, schema_uri: str | None = None) -> ArtifactRef:
    suffix = "json" if schema_uri else "txt"
    return ArtifactRef(
        artifact_id=f"{role}-1",
        role=role,
        uri=f"file:///tmp/{role}.{suffix}",
        digest=DIGEST,
        size_bytes=1,
        media_type="application/json" if suffix == "json" else "text/plain",
        schema_uri=schema_uri,
    )


def coverage(*curd_ids: str) -> MoldCookCoverage:
    ids = list(curd_ids)
    return MoldCookCoverage(curd_ids=ids)


def approval(
    *,
    kind: MoldCookApprovalKind = MoldCookApprovalKind.SCOPE,
    response_source: MoldCookApprovalSource = MoldCookApprovalSource.USER_RESPONSE,
    plan_digest: str | None = None,
) -> MoldCookApproval:
    response_role = (
        "dialogue"
        if response_source is MoldCookApprovalSource.LOCAL_DIALOGUE
        else "response"
    )
    return MoldCookApproval(
        contract_version=version(MOLD_COOK_APPROVAL_SCHEMA_URI),
        request_id="request-1",
        kind=kind,
        decision=MoldCookApprovalDecision.APPROVED,
        source=response_source,
        spec_digest=DIGEST,
        proposal_ref=ref("proposal"),
        proposal_digest=DIGEST,
        response_ref=ref(response_role),
        response_digest=DIGEST,
        response_text="Approve",
        response_source="local-dialogue-1",
        coverage=coverage("curd-1"),
        plan_digest=plan_digest,
    )


def light_handoff() -> MoldCookHandoff:
    return MoldCookHandoff(
        contract_version=version(MOLD_COOK_HANDOFF_SCHEMA_URI),
        request_id="request-1",
        input_kind=MoldCookInputKind.DIRECT_SPEC,
        mode=MoldCookMode.LIGHT,
        spec_ref=ref("spec"),
        approval_ref=ref("approval", schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI),
        coverage=coverage("curd-1"),
    )


def result(
    outcome: CookPreparationOutcome,
    *,
    references: list[ArtifactRef] | tuple[ArtifactRef, ...] | None = None,
    holds: list[CookExecutionHold] | tuple[CookExecutionHold, ...] = (),
    handoff_ref: ArtifactRef | None = None,
    coverage: MoldCookCoverage | None = None,
    approved_scope_ref: ArtifactRef | None = None,
    planner_request: PlannerRequest | None = None,
    approval_kind: MoldCookApprovalKind | None = None,
    proposal_ref: ArtifactRef | None = None,
    proposal_digest: str | None = None,
    missing_decision: str | None = None,
    approved_plan_ref: ArtifactRef | None = None,
    setup_authorization: CookSetupAuthorization | None = None,
    requirements: list[CookUnmetRequirement] | tuple[CookUnmetRequirement, ...] = (),
    findings: list[CookValidationFinding] | tuple[CookValidationFinding, ...] = (),
) -> CookPreparationResult:
    return CookPreparationResult(
        contract_version=version(COOK_PREPARATION_RESULT_SCHEMA_URI),
        request_id="request-1",
        input_kind=MoldCookInputKind.DIRECT_SPEC,
        outcome=outcome,
        references=[ref("spec")] if references is None else references,
        holds=holds,
        handoff_ref=handoff_ref,
        coverage=coverage,
        approved_scope_ref=approved_scope_ref,
        planner_request=planner_request,
        approval_kind=approval_kind,
        proposal_ref=proposal_ref,
        proposal_digest=proposal_digest,
        missing_decision=missing_decision,
        approved_plan_ref=approved_plan_ref,
        setup_authorization=setup_authorization,
        requirements=requirements,
        findings=findings,
    )


def test_light_handoff_round_trips_without_planner_artifacts() -> None:
    handoff = light_handoff()
    encoded = canonical_bytes(handoff)
    validated = validate_contract(
        encoded,
        MoldCookHandoff,
        supported_version_for(MoldCookHandoff),
    )

    assert validated.value == handoff
    assert validated.canonical_bytes == encoded
    assert handoff.planner_result_ref is None
    assert handoff.plan_ref is None


def test_approval_round_trips_with_local_dialogue_reference() -> None:
    value = approval(response_source=MoldCookApprovalSource.LOCAL_DIALOGUE)
    validated = validate_contract(
        canonical_bytes(value),
        MoldCookApproval,
        supported_version_for(MoldCookApproval),
    )

    assert validated.value == value
    assert value.response_ref.role == "dialogue"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("request_id", None),
        ("coverage", None),
        ("unknown", "rejected"),
    ],
)
def test_handoff_rejects_missing_and_unknown_fields(
    field: str, replacement: object
) -> None:
    parsed = cast(object, json.loads(canonical_bytes(light_handoff())))
    assert isinstance(parsed, dict)
    raw = cast(dict[str, object], parsed)
    if replacement is None:
        del raw[field]
    else:
        raw[field] = replacement

    with pytest.raises(ContractValidationError):
        _ = validate_contract(
            raw,
            MoldCookHandoff,
            supported_version_for(MoldCookHandoff),
        )


def test_preparation_outcomes_are_closed_and_reject_mixed_payloads() -> None:
    ready = result(
        CookPreparationOutcome.READY,
        references=[ref("handoff")],
        handoff_ref=ref("handoff"),
        coverage=coverage("curd-1"),
    )
    parsed = cast(object, json.loads(canonical_bytes(ready)))
    assert isinstance(parsed, dict)
    raw = cast(dict[str, object], parsed)
    raw["proposal_ref"] = cast(object, json.loads(canonical_bytes(ref("proposal"))))
    raw["proposal_digest"] = DIGEST
    raw["missing_decision"] = "approval"

    with pytest.raises(ContractValidationError):
        _ = validate_contract(
            raw,
            CookPreparationResult,
            supported_version_for(CookPreparationResult),
        )


def test_every_non_ready_preparation_outcome_has_only_its_payload() -> None:
    planner_request = PlannerRequest(
        contract_version=version("https://schemas.easy-cheese.dev/planner-request"),
        request_id="planner-request-1",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Plan the approved work",
    )
    outcomes = (
        result(
            CookPreparationOutcome.NEEDS_PLANNING,
            approved_scope_ref=ref("approved_scope"),
            planner_request=planner_request,
        ),
        result(
            CookPreparationOutcome.NEEDS_APPROVAL,
            approval_kind=MoldCookApprovalKind.PLAN,
            proposal_ref=ref("proposal"),
            proposal_digest=DIGEST,
            missing_decision="plan approval",
        ),
        result(
            CookPreparationOutcome.NEEDS_PREPARATION,
            references=[ref("curd_plan")],
            approved_plan_ref=ref("curd_plan"),
            coverage=coverage("curd-1"),
            setup_authorization=CookSetupAuthorization(
                prerequisite_curd_id="curd-1",
                allowed_paths=["tests/"],
                allowed_commands=["python -m pytest tests/"],
            ),
        ),
        result(
            CookPreparationOutcome.BLOCKED,
            holds=[
                CookExecutionHold(
                    hold_id="hold-1",
                    kind=CookHoldKind.PREPARATION,
                    reason="Runner setup is not approved",
                )
            ],
        ),
        result(
            CookPreparationOutcome.INVALID,
            findings=[
                CookValidationFinding(
                    code="invalid-reference",
                    message="The proposal reference is not readable",
                )
            ],
        ),
    )

    for value in outcomes:
        encoded = canonical_bytes(value)
        validated = validate_contract(
            encoded,
            CookPreparationResult,
            supported_version_for(CookPreparationResult),
        )
        assert validated.value == value


def test_blocked_and_invalid_cannot_carry_execution_authority() -> None:
    with pytest.raises(ValueError, match="another outcome"):
        _ = result(
            CookPreparationOutcome.BLOCKED,
            holds=[
                CookExecutionHold(
                    hold_id="hold-1",
                    kind=CookHoldKind.BLOCKED,
                    reason="Explicit user hold",
                )
            ],
            handoff_ref=ref("handoff"),
            coverage=coverage("curd-1"),
        )

    requirement = CookUnmetRequirement(
        requirement_id="runner-1",
        kind=CookRequirementKind.RUNNER,
        description="A runner decision is required",
    )
    assert requirement.kind is CookRequirementKind.RUNNER
