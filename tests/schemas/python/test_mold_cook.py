from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import cast

import pytest

from easy_cheese_schemas import mold_cook
from easy_cheese_schemas.contracts import (
    ArtifactRef,
    ContractVersion,
    PlannerRequest,
    PlannerRequestKind,
    contract,
)
from easy_cheese_schemas.mold_cook import (
    COOK_PREPARATION_RESULT_SCHEMA_URI,
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    MOLD_COOK_CONTRACTS,
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
    registered_contracts,
)
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    canonical_bytes,
    schema_bytes,
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
    proposal_ref: ArtifactRef | None = None,
    proposal_digest: str = DIGEST,
    response_ref: ArtifactRef | None = None,
    setup_authorization: CookSetupAuthorization | None = None,
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
        proposal_ref=ref("proposal") if proposal_ref is None else proposal_ref,
        proposal_digest=proposal_digest,
        response_ref=ref(response_role) if response_ref is None else response_ref,
        response_digest=DIGEST,
        response_text="Approve",
        response_source="local-dialogue-1",
        coverage=coverage("curd-1"),
        plan_digest=plan_digest,
        setup_authorization=setup_authorization,
    )


def light_handoff(
    *,
    curd_ids: tuple[str, ...] = ("curd-1",),
    setup_evidence_refs: tuple[ArtifactRef, ...] = (),
    taste_verdict_ref: ArtifactRef | None = None,
    taste_ledger_ref: ArtifactRef | None = None,
) -> MoldCookHandoff:
    return MoldCookHandoff(
        contract_version=version(MOLD_COOK_HANDOFF_SCHEMA_URI),
        request_id="request-1",
        input_kind=MoldCookInputKind.DIRECT_SPEC,
        mode=MoldCookMode.LIGHT,
        spec_ref=ref("spec"),
        approval_ref=ref("approval", schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI),
        coverage=coverage(*curd_ids),
        setup_evidence_refs=setup_evidence_refs,
        taste_verdict_ref=taste_verdict_ref,
        taste_ledger_ref=taste_ledger_ref,
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


PLANNER_REQUEST = PlannerRequest(
    contract_version=version("https://schemas.easy-cheese.dev/planner-request"),
    request_id="planner-request-1",
    kind=PlannerRequestKind.DECOMPOSE,
    objective="Plan the approved work",
)
REQUIREMENT = CookUnmetRequirement(
    requirement_id="runner-1",
    kind=CookRequirementKind.RUNNER,
    description="A runner decision is required",
)
FINDING = CookValidationFinding(
    code="invalid-reference",
    message="The proposal reference is not readable",
)
HOLD = CookExecutionHold(
    hold_id="hold-1",
    kind=CookHoldKind.PREPARATION,
    reason="Runner setup is not approved",
)
SETUP_AUTHORIZATION = CookSetupAuthorization(
    prerequisite_curd_id="curd-1",
    allowed_paths=["tests/"],
    allowed_commands=["python -m pytest tests/"],
)

NON_READY_OUTCOMES = (
    CookPreparationOutcome.NEEDS_PLANNING,
    CookPreparationOutcome.NEEDS_APPROVAL,
    CookPreparationOutcome.NEEDS_PREPARATION,
    CookPreparationOutcome.BLOCKED,
    CookPreparationOutcome.INVALID,
)


def valid_result(
    outcome: CookPreparationOutcome,
    *,
    requirements: tuple[CookUnmetRequirement, ...] = (),
    findings: tuple[CookValidationFinding, ...] = (),
    handoff_ref: ArtifactRef | None = None,
) -> CookPreparationResult:
    """Build the minimal valid payload for ``outcome`` plus any foreign field."""
    if outcome is CookPreparationOutcome.READY:
        return result(
            outcome,
            references=[ref("handoff")],
            handoff_ref=ref("handoff"),
            coverage=coverage("curd-1"),
            requirements=requirements,
            findings=findings,
        )
    if outcome is CookPreparationOutcome.NEEDS_PLANNING:
        return result(
            outcome,
            approved_scope_ref=ref("approved_scope"),
            planner_request=PLANNER_REQUEST,
            handoff_ref=handoff_ref,
            requirements=requirements,
            findings=findings,
        )
    if outcome is CookPreparationOutcome.NEEDS_APPROVAL:
        return result(
            outcome,
            approval_kind=MoldCookApprovalKind.PLAN,
            proposal_ref=ref("proposal"),
            proposal_digest=DIGEST,
            missing_decision="plan approval",
            handoff_ref=handoff_ref,
            requirements=requirements,
            findings=findings,
        )
    if outcome is CookPreparationOutcome.NEEDS_PREPARATION:
        return result(
            outcome,
            references=[ref("curd_plan")],
            approved_plan_ref=ref("curd_plan"),
            coverage=coverage("curd-1"),
            setup_authorization=SETUP_AUTHORIZATION,
            handoff_ref=handoff_ref,
            requirements=requirements,
            findings=findings,
        )
    if outcome is CookPreparationOutcome.BLOCKED:
        return result(
            outcome,
            holds=[HOLD],
            handoff_ref=handoff_ref,
            requirements=requirements,
            findings=findings,
        )
    return result(
        outcome,
        findings=(FINDING, *findings),
        handoff_ref=handoff_ref,
        requirements=requirements,
    )


def as_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def outcome_branches() -> dict[object, dict[str, object]]:
    """Return the emitted ``then`` branch of the result schema, keyed by outcome."""
    schema = as_dict(
        cast(object, json.loads(schema_bytes(COOK_PREPARATION_RESULT_SCHEMA_URI)))
    )
    definition = as_dict(as_dict(schema["$defs"])["CookPreparationResult"])
    branches = cast("list[dict[str, object]]", definition["allOf"])
    return {
        as_dict(as_dict(as_dict(branch["if"])["properties"])["outcome"])["const"]: (
            as_dict(branch["then"])
        )
        for branch in branches
    }


def remove_field(raw: dict[str, object], name: str) -> None:
    del raw[name]


def replace_field(raw: dict[str, object], name: str, value: object) -> None:
    raw[name] = value


def replace_version_field(raw: dict[str, object], name: str, value: str) -> None:
    as_dict(raw["contract_version"])[name] = value


def _remove(name: str) -> Callable[[dict[str, object]], None]:
    def mutate(raw: dict[str, object]) -> None:
        remove_field(raw, name)

    return mutate


def _replace(name: str, value: object) -> Callable[[dict[str, object]], None]:
    def mutate(raw: dict[str, object]) -> None:
        replace_field(raw, name, value)

    return mutate


def _replace_version(name: str, value: str) -> Callable[[dict[str, object]], None]:
    def mutate(raw: dict[str, object]) -> None:
        replace_version_field(raw, name, value)

    return mutate


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


def test_mold_cook_contracts_is_the_derived_alias() -> None:
    assert MOLD_COOK_CONTRACTS == registered_contracts()


def test_registered_contracts_follow_the_contract_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = contract("mold-cook-probe")(type("_ProbeContract", (), {}))
    probe.__module__ = mold_cook.__name__
    monkeypatch.setattr(mold_cook, "_ProbeContract", probe, raising=False)

    assert ("mold-cook-probe", probe) in registered_contracts()


@pytest.mark.parametrize(
    ("construct", "message"),
    [
        pytest.param(
            lambda: approval(proposal_digest="sha256:" + "b" * 64),
            "proposal_digest must match proposal_ref.digest",
            id="proposal-digest-mismatch",
        ),
        pytest.param(
            lambda: approval(
                proposal_ref=ref("proposal", schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI)
            ),
            "approval proposal must not be an approval artifact",
            id="proposal-is-an-approval",
        ),
        pytest.param(
            lambda: approval(
                response_source=MoldCookApprovalSource.LOCAL_DIALOGUE,
                response_ref=ref("response"),
            ),
            "local_dialogue approval requires a dialogue artifact",
            id="dialogue-source-with-response-artifact",
        ),
        pytest.param(
            lambda: approval(kind=MoldCookApprovalKind.PLAN),
            "plan approval requires plan_digest",
            id="plan-without-digest",
        ),
        pytest.param(
            lambda: approval(plan_digest=DIGEST),
            "scope approval must not carry plan_digest",
            id="scope-with-plan-digest",
        ),
        pytest.param(
            lambda: approval(kind=MoldCookApprovalKind.RUNNER),
            "runner approval requires setup_authorization",
            id="runner-without-setup-authorization",
        ),
        pytest.param(
            lambda: approval(setup_authorization=SETUP_AUTHORIZATION),
            "scope approval must not carry setup_authorization",
            id="scope-with-setup-authorization",
        ),
        pytest.param(
            lambda: light_handoff(
                setup_evidence_refs=(
                    ref("spec", schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI),
                )
            ),
            "setup_evidence_refs must use artifact role 'setup_evidence'",
            id="setup-evidence-wrong-role",
        ),
        pytest.param(
            lambda: light_handoff(setup_evidence_refs=(ref("setup_evidence"),)),
            "setup_evidence_refs must carry a schema_uri",
            id="setup-evidence-without-schema-uri",
        ),
        pytest.param(
            lambda: light_handoff(curd_ids=("curd-1", "curd-2")),
            "light handoff coverage must contain exactly one curd",
            id="light-handoff-with-two-curds",
        ),
        pytest.param(
            lambda: light_handoff(
                taste_verdict_ref=ref(
                    "taste_verdict", schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI
                )
            ),
            "taste_verdict_ref and taste_ledger_ref must be supplied together",
            id="taste-verdict-without-ledger",
        ),
    ],
)
def test_contract_invariants_reject_inconsistent_values(
    construct: Callable[[], object], message: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        _ = construct()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        pytest.param(
            _remove("request_id"),
            "$.request_id is required",
            id="missing-request-id",
        ),
        pytest.param(
            _remove("coverage"),
            "$.coverage is required",
            id="missing-coverage",
        ),
        pytest.param(
            _replace("unknown", "rejected"),
            "$ contains unknown fields: unknown",
            id="unknown-field",
        ),
        pytest.param(
            _replace_version("major", "2"),
            "unsupported contract version 2.0",
            id="unsupported-major",
        ),
        pytest.param(
            _replace_version("minor", "9"),
            "unsupported contract version 1.9",
            id="unsupported-minor",
        ),
        pytest.param(
            _replace_version("schema_uri", COOK_PREPARATION_RESULT_SCHEMA_URI),
            "contract_version.schema_uri does not match the registered contract",
            id="foreign-schema-uri",
        ),
    ],
)
def test_handoff_rejects_missing_unknown_and_unsupported_fields(
    mutate: Callable[[dict[str, object]], None], message: str
) -> None:
    raw = as_dict(cast(object, json.loads(canonical_bytes(light_handoff()))))
    mutate(raw)

    with pytest.raises(ContractValidationError, match=re.escape(message)):
        _ = validate_contract(
            raw,
            MoldCookHandoff,
            supported_version_for(MoldCookHandoff),
        )


def test_preparation_outcomes_are_closed_and_reject_mixed_payloads() -> None:
    ready = valid_result(CookPreparationOutcome.READY)
    raw = as_dict(cast(object, json.loads(canonical_bytes(ready))))
    raw["proposal_ref"] = cast(object, json.loads(canonical_bytes(ref("proposal"))))
    raw["proposal_digest"] = DIGEST
    raw["missing_decision"] = "approval"

    with pytest.raises(ContractValidationError):
        _ = validate_contract(
            raw,
            CookPreparationResult,
            supported_version_for(CookPreparationResult),
        )


@pytest.mark.parametrize("outcome", NON_READY_OUTCOMES)
def test_every_non_ready_preparation_outcome_round_trips(
    outcome: CookPreparationOutcome,
) -> None:
    value = valid_result(outcome)
    encoded = canonical_bytes(value)
    validated = validate_contract(
        encoded,
        CookPreparationResult,
        supported_version_for(CookPreparationResult),
    )

    assert validated.value == value


@pytest.mark.parametrize("outcome", NON_READY_OUTCOMES)
def test_non_ready_preparation_outcome_rejects_a_foreign_payload_field(
    outcome: CookPreparationOutcome,
) -> None:
    message = (
        f"{outcome.value} preparation carries fields for another outcome: handoff_ref"
    )

    with pytest.raises(ValueError, match=re.escape(message)):
        _ = valid_result(outcome, handoff_ref=ref("handoff"))


@pytest.mark.parametrize(
    ("outcome", "field_name"),
    [
        (CookPreparationOutcome.READY, "requirements"),
        (CookPreparationOutcome.READY, "findings"),
        (CookPreparationOutcome.NEEDS_PLANNING, "requirements"),
        (CookPreparationOutcome.NEEDS_PLANNING, "findings"),
        (CookPreparationOutcome.NEEDS_APPROVAL, "requirements"),
        (CookPreparationOutcome.NEEDS_APPROVAL, "findings"),
        (CookPreparationOutcome.NEEDS_PREPARATION, "requirements"),
        (CookPreparationOutcome.NEEDS_PREPARATION, "findings"),
        (CookPreparationOutcome.BLOCKED, "findings"),
        (CookPreparationOutcome.INVALID, "requirements"),
    ],
)
def test_constructor_rejects_every_sequence_its_schema_forbids(
    outcome: CookPreparationOutcome, field_name: str
) -> None:
    forbidden = cast(
        "list[dict[str, object]]",
        as_dict(outcome_branches()[outcome.value]["not"])["anyOf"],
    )
    assert field_name in {
        cast("list[str]", branch["required"])[0] for branch in forbidden
    }

    message = (
        f"{outcome.value} preparation carries fields for another outcome: {field_name}"
    )
    with pytest.raises(ValueError, match=re.escape(message)):
        _ = valid_result(
            outcome,
            requirements=(REQUIREMENT,) if field_name == "requirements" else (),
            findings=(FINDING,) if field_name == "findings" else (),
        )


def test_blocked_and_invalid_schema_branches_require_their_evidence() -> None:
    branches = outcome_branches()

    assert len(branches) == 6
    assert branches[CookPreparationOutcome.BLOCKED.value]["anyOf"] == [
        {"required": ["holds"], "properties": {"holds": {"minItems": 1}}},
        {"required": ["requirements"], "properties": {"requirements": {"minItems": 1}}},
    ]
    invalid = branches[CookPreparationOutcome.INVALID.value]
    assert invalid["required"] == ["findings"]
    assert invalid["properties"] == {"findings": {"minItems": 1}}


def test_blocked_and_invalid_cannot_carry_execution_authority() -> None:
    with pytest.raises(ValueError, match="another outcome"):
        _ = result(
            CookPreparationOutcome.BLOCKED,
            holds=[HOLD],
            handoff_ref=ref("handoff"),
            coverage=coverage("curd-1"),
        )

    with pytest.raises(ValueError, match="another outcome: coverage, handoff_ref"):
        _ = result(
            CookPreparationOutcome.INVALID,
            findings=[FINDING],
            handoff_ref=ref("handoff"),
            coverage=coverage("curd-1"),
        )

    with pytest.raises(ValueError, match="another outcome: holds"):
        _ = result(
            CookPreparationOutcome.INVALID,
            findings=[FINDING],
            holds=[HOLD],
        )
