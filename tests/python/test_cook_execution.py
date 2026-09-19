"""Focused regressions for the Cook preparation-to-execution seam."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Never, TypedDict, cast
from urllib.parse import urlsplit

import attrs
import pytest

import easy_cheese.shared.workflow as workflow
from easy_cheese.shared.artifacts import ArtifactResolutionError
from easy_cheese.shared.mold_cook_handoff import (
    canonical_mold_cook_proposal,
    publish_mold_cook_handoff,
)
from easy_cheese.shared.publication import (
    PayloadDigestMismatchError,
    request_digest,
)
from easy_cheese.skills.cook import execute_accepted_handoff
from easy_cheese.skills.cook import contract_handlers
from easy_cheese.skills.cook.preparation import plan_stages
from easy_cheese.skills.cook.preparation import (
    CookEvidenceError,
    CookHoldClearance,
    PreparationEvidence,
    SetupEvidence,
    prepare,
    resubmit,
)
from easy_cheese.skills.cook.preparation.setup import apply_runner_setup
from easy_cheese_schemas import (
    ArtifactRef,
    ContractVersion,
    canonical_bytes,
    supported_version_for,
)
from easy_cheese_schemas.contracts import (
    BoundedScope,
    Criterion,
    CriterionDisposition,
    CriterionResultWriterView,
    CurdResultWriterView,
    CurdPlan,
    IdentityAction,
    EvidenceKind,
    EvidenceRef,
    IdentityLineage,
    PlannerDisposition,
    PlannerResult,
    PlannerUncertainty,
    ReviewDisposition,
    ReviewResultWriterView,
    SemanticCurd,
    UncertaintyScope,
)
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    MOLD_COOK_HANDOFF_SCHEMA_URI,
    CookExecutionHold,
    CookHoldKind,
    CookPreparationOutcome,
    CookSetupAuthorization,
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError

from tests.python.mold_cook_helpers import bind_mold_cook_approval


class _FullFixture(TypedDict):
    pointer: Path
    plan: CurdPlan
    planner: PlannerResult
    handoff: MoldCookHandoff
    spec: Path
    spec_ref: ArtifactRef
    scope_approval_ref: ArtifactRef
    plan_approval_ref: ArtifactRef
    proposal_ref: ArtifactRef
    response_ref: ArtifactRef
    scope_approval: MoldCookApproval
    plan_approval: MoldCookApproval
    taste_verdict_ref: ArtifactRef
    taste_ledger_ref: ArtifactRef


def _version(contract: type) -> ContractVersion:
    value = supported_version_for(contract)
    assert value is not None
    return value


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _write_ref(
    root: Path,
    value: object,
    *,
    artifact_id: str,
    role: str,
    filename: str,
    media_type: str = "application/json",
    schema_uri: str | None = None,
) -> ArtifactRef:
    content = value if isinstance(value, bytes) else canonical_bytes(value)
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(content)
    return ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=path.as_uri(),
        digest=_digest(content),
        size_bytes=len(content),
        media_type=media_type,
        schema_uri=schema_uri,
    )


def _runner_approval_ref(
    root: Path,
    *,
    spec_ref: ArtifactRef,
    response_ref: ArtifactRef,
    coverage: MoldCookCoverage,
    authorization: CookSetupAuthorization,
) -> ArtifactRef:
    runner_proposal_ref = _write_ref(
        root,
        canonical_mold_cook_proposal(
            request_id="cook-request",
            kind=MoldCookApprovalKind.RUNNER,
            spec_digest=spec_ref.digest,
            coverage=coverage,
            setup_authorization=authorization,
        ),
        artifact_id="runner-proposal",
        role="proposal",
        filename="runner-proposal.json",
    )
    runner_approval = bind_mold_cook_approval(
        request_id="cook-request",
        kind=MoldCookApprovalKind.RUNNER,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=spec_ref.digest,
        proposal_ref=runner_proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source="response.txt",
        coverage=coverage,
        setup_authorization=authorization,
    )
    return _write_ref(
        root,
        runner_approval,
        artifact_id="runner-approval",
        role="runner_approval",
        filename="runner-approval.json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )


def _curd(curd_id: str, *, dependencies: tuple[str, ...] = ()) -> SemanticCurd:
    return SemanticCurd(
        curd_id=curd_id,
        outcome=f"Implement {curd_id}",
        scope=BoundedScope(paths=[f"src/{curd_id}.py"]),
        inputs=(),
        outputs=(f"{curd_id}-result",),
        dependencies=dependencies,
        criteria=(
            Criterion(
                criterion_id=f"{curd_id}-criterion",
                description=f"{curd_id} passes",
                check="the focused Cook regression passes",
            ),
        ),
        lineage=IdentityLineage(IdentityAction.NEW),
    )


def _full_fixture(
    root: Path,
    *,
    coverage_ids: tuple[str, ...] = ("root",),
    partial: bool = True,
) -> _FullFixture:
    root.mkdir(parents=True, exist_ok=True)
    spec_content = (
        Path(__file__).parent / "fixtures" / "spec_format" / "valid_spec.md"
    ).read_bytes()
    spec_ref = _write_ref(
        root,
        spec_content,
        artifact_id="spec",
        role="spec",
        filename="spec.md",
        media_type="text/markdown",
    )
    curds = (_curd("root"), _curd("leaf", dependencies=("root",)))
    plan = CurdPlan.signed(
        contract_version=_version(CurdPlan),
        plan_id="cook-plan",
        revision=1,
        objective="Execute the approved Cook boundary",
        curds=curds,
    )
    remainder = (
        (
            PlannerUncertainty(
                description="one independent remainder remains",
                scope=UncertaintyScope.OMITTED_WORK,
            ),
        )
        if partial
        else ()
    )
    planner = PlannerResult(
        contract_version=_version(PlannerResult),
        request_id="cook-request",
        disposition=PlannerDisposition.PARTIAL
        if partial
        else PlannerDisposition.COMPLETE,
        plan=plan,
        unresolved_work=remainder,
    )
    planner_ref = _write_ref(
        root,
        planner,
        artifact_id="planner",
        role="planner_result",
        filename="planner.json",
        schema_uri="https://schemas.easy-cheese.dev/planner-result",
    )
    plan_ref = _write_ref(
        root,
        plan,
        artifact_id="plan",
        role="curd_plan",
        filename="plan.json",
        schema_uri="https://schemas.easy-cheese.dev/curd-plan",
    )
    coverage = MoldCookCoverage(
        curd_ids=coverage_ids,
        unresolved_work=remainder,
    )
    scope_coverage = MoldCookCoverage(
        curd_ids=("root",),
    )
    scope_proposal_ref = _write_ref(
        root,
        canonical_mold_cook_proposal(
            request_id="cook-request",
            kind=MoldCookApprovalKind.SCOPE,
            spec_digest=spec_ref.digest,
            coverage=scope_coverage,
        ),
        artifact_id="scope-proposal",
        role="proposal",
        filename="scope-proposal.md",
        media_type="text/markdown",
    )
    proposal_ref = _write_ref(
        root,
        canonical_mold_cook_proposal(
            request_id="cook-request",
            kind=(
                MoldCookApprovalKind.PARTIAL_PLAN
                if partial
                else MoldCookApprovalKind.PLAN
            ),
            spec_digest=spec_ref.digest,
            coverage=coverage,
            planner_result=planner,
            plan_digest=plan.digest,
        ),
        artifact_id="plan-proposal",
        role="proposal",
        filename="plan-proposal.json",
    )
    response_ref = _write_ref(
        root,
        b"Approve",
        artifact_id="response",
        role="response",
        filename="response.txt",
        media_type="text/plain",
    )
    scope_approval = bind_mold_cook_approval(
        request_id="cook-request",
        kind=MoldCookApprovalKind.SCOPE,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=spec_ref.digest,
        proposal_ref=scope_proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source="response.txt",
        coverage=scope_coverage,
    )
    approval = bind_mold_cook_approval(
        request_id="cook-request",
        kind=(
            MoldCookApprovalKind.PARTIAL_PLAN if partial else MoldCookApprovalKind.PLAN
        ),
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=spec_ref.digest,
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source="response.txt",
        coverage=coverage,
        plan_digest=plan.digest,
    )
    scope_approval_ref = _write_ref(
        root,
        scope_approval,
        artifact_id="scope-approval",
        role="approval",
        filename="scope-approval.json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    approval_ref = _write_ref(
        root,
        approval,
        artifact_id="approval",
        role="approval",
        filename="approval.json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    taste_verdict_ref = _write_ref(
        root,
        b'{"verdict":"pass"}',
        artifact_id="taste-verdict",
        role="taste_verdict",
        filename="taste-verdict.json",
        schema_uri="https://schemas.easy-cheese.dev/fork-taste-verdict",
    )
    taste_ledger_ref = _write_ref(
        root,
        b"[]",
        artifact_id="taste-ledger",
        role="taste_ledger",
        filename="taste-ledger.json",
        schema_uri="https://schemas.easy-cheese.dev/taste-ledger",
    )
    handoff = MoldCookHandoff(
        contract_version=_version(MoldCookHandoff),
        request_id="cook-request",
        input_kind=MoldCookInputKind.DIRECT_SPEC,
        mode=MoldCookMode.FULL,
        spec_ref=spec_ref,
        approval_ref=approval_ref,
        coverage=coverage,
        planner_result_ref=planner_ref,
        plan_ref=plan_ref,
        taste_verdict_ref=taste_verdict_ref,
        taste_ledger_ref=taste_ledger_ref,
    )
    operation_id = "cook-full-fixture"
    _ = publish_mold_cook_handoff(
        handoff,
        request_digest=request_digest(
            "raw",
            {"request_id": handoff.request_id},
            source_phase="mold",
            destination_phase="cook",
            payload_schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI,
        ),
        operation_id=operation_id,
        artifact_root=root,
    )
    return {
        "pointer": root / "pointers" / f"{operation_id}.json",
        "plan": plan,
        "planner": planner,
        "handoff": handoff,
        "spec": root / "spec.md",
        "spec_ref": spec_ref,
        "scope_approval_ref": scope_approval_ref,
        "plan_approval_ref": approval_ref,
        "proposal_ref": proposal_ref,
        "response_ref": response_ref,
        "scope_approval": scope_approval,
        "plan_approval": approval,
        "taste_verdict_ref": taste_verdict_ref,
        "taste_ledger_ref": taste_ledger_ref,
    }


def test_full_preparation_is_scope_first_and_reuses_unchanged_approval(
    tmp_path: Path,
) -> None:
    root = tmp_path / "scope-first"
    fixture = _full_fixture(root)
    planner = fixture["planner"]
    scope_approval = fixture["scope_approval_ref"]
    plan_approval = fixture["plan_approval_ref"]
    dispatches: list[object] = []

    def forbidden_planner(request: object) -> object:
        dispatches.append(request)
        raise AssertionError("scope approval must precede planning")

    before_scope = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(planner_dispatch=forbidden_planner),
    )
    assert before_scope.outcome is CookPreparationOutcome.NEEDS_APPROVAL
    assert not dispatches

    after_scope = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(scope_approval=scope_approval),
    )
    assert after_scope.outcome is CookPreparationOutcome.NEEDS_PLANNING

    after_plan = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=scope_approval,
            planner_result=planner,
        ),
    )
    assert after_plan.outcome is CookPreparationOutcome.NEEDS_APPROVAL

    ready = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=scope_approval,
            planner_result=planner,
            plan_approval=plan_approval,
        ),
    )
    resumed = resubmit(
        ready,
        source=fixture["spec"],
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=scope_approval,
            planner_result=planner,
            plan_approval=plan_approval,
        ),
    )
    assert ready.outcome is CookPreparationOutcome.READY
    assert resumed.outcome is CookPreparationOutcome.READY
    assert resumed.coverage == ready.coverage


def test_plan_approval_must_match_displayed_plan_proposal(
    tmp_path: Path,
) -> None:
    root = tmp_path / "detached-plan-approval"
    fixture = _full_fixture(root)
    scope_approval = fixture["scope_approval_ref"]
    planner = fixture["planner"]

    proposed = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=fixture["scope_approval_ref"],
            planner_result=planner,
        ),
    )
    detached_proposal_ref = _write_ref(
        root,
        b'{"proposal":"detached"}',
        artifact_id="detached-plan-proposal",
        role="proposal",
        filename="detached-plan-proposal.json",
    )
    approved = fixture["plan_approval"]
    detached_approval = bind_mold_cook_approval(
        request_id="cook-request",
        kind=approved.kind,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=fixture["spec_ref"].digest,
        proposal_ref=detached_proposal_ref,
        response_ref=fixture["response_ref"],
        response_text="Approve",
        response_source="response.txt",
        coverage=approved.coverage,
        plan_digest=fixture["plan"].digest,
    )
    assert proposed.outcome is CookPreparationOutcome.NEEDS_APPROVAL
    assert proposed.proposal_digest is not None
    assert detached_approval.proposal_digest != proposed.proposal_digest

    detached_approval_ref = _write_ref(
        root,
        detached_approval,
        artifact_id="detached-approval",
        role="approval",
        filename="detached-approval.json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    detached = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=scope_approval,
            planner_result=planner,
            plan_approval=detached_approval_ref,
        ),
    )

    assert detached.outcome is CookPreparationOutcome.INVALID
    assert [item.code for item in detached.findings] == ["invalid-evidence"]
    assert detached.handoff_ref is None


def _writer(context: Mapping[str, object]) -> CurdResultWriterView:
    criteria = cast("tuple[Criterion, ...]", context["criteria"])
    return CurdResultWriterView(
        criterion_results=[
            CriterionResultWriterView(
                criterion_id=item.criterion_id,
                disposition=CriterionDisposition.PASSED,
                evidence_keys=("result.txt",),
            )
            for item in criteria
        ],
    )


def _review(_request: object) -> ReviewResultWriterView:
    return ReviewResultWriterView(ReviewDisposition.CLEAN, ())


def _diagnosis(_request: object):
    raise AssertionError("diagnosis must not run after a passing writer and review")


def test_execute_full_handoff_forwards_exact_coverage_and_keeps_remainder(
    tmp_path: Path,
) -> None:
    result_artifact = _write_ref(
        tmp_path,
        b"verified\n",
        artifact_id="result",
        role="evidence",
        filename="result.txt",
        media_type="text/plain",
    )
    evidence = EvidenceRef(
        evidence_id="result.txt",
        kind=EvidenceKind.SOURCE,
        artifact=result_artifact,
        summary="Verified Cook execution result",
    )
    fixture = _full_fixture(tmp_path / "full")
    result = execute_accepted_handoff(
        fixture["pointer"],
        artifact_root=tmp_path / "full",
        repository_root=tmp_path,
        dispatch_writer=_writer,
        dispatch_review=_review,
        dispatch_diagnosis=_diagnosis,
        evidence={"result.txt": evidence},
    )

    assert result.completed_curds == ("root",)
    branches, curd_results = result.execution_results
    assert len(branches) == 1
    assert len(curd_results) == 1
    assert curd_results[0].source_curd_ref.curd_id == "root"
    planner = fixture["planner"]
    assert result.coverage.unresolved_work == planner.unresolved_work
    assert len(result.coverage.unresolved_work) == 1


def test_execute_light_handoff_stops_before_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _full_fixture(tmp_path / "light")
    light_handoff = MoldCookHandoff(
        contract_version=_version(MoldCookHandoff),
        request_id="cook-request",
        input_kind=MoldCookInputKind.DIRECT_SPEC,
        mode=MoldCookMode.LIGHT,
        spec_ref=fixture["spec_ref"],
        approval_ref=fixture["scope_approval_ref"],
        coverage=MoldCookCoverage(curd_ids=("root",)),
        taste_verdict_ref=fixture["taste_verdict_ref"],
        taste_ledger_ref=fixture["taste_ledger_ref"],
    )
    operation_id = "cook-light-fixture"
    root = tmp_path / "light"
    _ = publish_mold_cook_handoff(
        light_handoff,
        request_digest=request_digest(
            "raw",
            {"request_id": light_handoff.request_id},
            source_phase="mold",
            destination_phase="cook",
            payload_schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI,
        ),
        operation_id=operation_id,
        artifact_root=root,
    )

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Light handoffs must not execute through workflow.cook")

    monkeypatch.setattr(workflow, "cook", forbidden)
    with pytest.raises(
        ContractValidationError,
        match="workflow execution requires a Full handoff with an approved plan",
    ):
        _ = execute_accepted_handoff(
            root / "pointers" / f"{operation_id}.json",
            artifact_root=root,
            dispatch_writer=_writer,
            dispatch_review=_review,
            dispatch_diagnosis=_diagnosis,
        )


def test_setup_authorization_requires_bounded_passing_evidence(tmp_path: Path) -> None:
    fixture = _full_fixture(tmp_path / "setup")
    root = tmp_path / "setup"
    plan = fixture["plan"]
    spec_ref = fixture["spec_ref"]
    response_ref = fixture["response_ref"]
    coverage = MoldCookCoverage(
        curd_ids=("root",),
        unresolved_work=fixture["planner"].unresolved_work,
    )
    authorization = CookSetupAuthorization(
        prerequisite_curd_id="root",
        allowed_paths=("tests/",),
        allowed_commands=("python -m pytest tests/setup.py",),
    )
    runner_approval_ref = _runner_approval_ref(
        root,
        spec_ref=spec_ref,
        response_ref=response_ref,
        coverage=coverage,
        authorization=authorization,
    )
    without_evidence = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=fixture["scope_approval_ref"],
            planner_result=fixture["planner"],
            plan_approval=fixture["plan_approval_ref"],
            runner_approval=runner_approval_ref,
        ),
    )
    assert without_evidence.outcome is CookPreparationOutcome.NEEDS_PREPARATION

    setup_output = b"setup passed\n"
    setup_output_digest = _digest(setup_output)
    _ = (root / f"sha256-{setup_output_digest.removeprefix('sha256:')}").write_bytes(
        setup_output
    )
    valid_evidence = SetupEvidence(
        prerequisite_curd_id="root",
        plan_digest=plan.digest,
        authorization_digest=_digest(canonical_bytes(authorization)),
        runner_command="python -m pytest tests/setup.py",
        fixture_path="tests/setup.py",
        environment_id="test-env",
        exit_code=0,
        captured_output_digest=setup_output_digest,
    )

    def retain_setup_evidence(evidence: SetupEvidence, artifact_id: str) -> ArtifactRef:
        content = canonical_bytes(evidence)
        digest = _digest(content)
        path = root / f"sha256-{digest.removeprefix('sha256:')}"
        _ = path.write_bytes(content)
        return ArtifactRef(
            artifact_id=artifact_id,
            role="setup_evidence",
            uri=path.as_uri(),
            digest=digest,
            size_bytes=len(content),
            media_type="application/json",
            schema_uri="https://schemas.easy-cheese.dev/setup-evidence",
        )

    ready = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=fixture["scope_approval_ref"],
            planner_result=fixture["planner"],
            plan_approval=fixture["plan_approval_ref"],
            runner_approval=runner_approval_ref,
            setup_evidence=retain_setup_evidence(
                valid_evidence,
                "setup-evidence-passed",
            ),
        ),
    )
    assert ready.outcome is CookPreparationOutcome.READY

    failed_evidence = attrs.evolve(valid_evidence, exit_code=1)
    held = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=fixture["scope_approval_ref"],
            planner_result=fixture["planner"],
            plan_approval=fixture["plan_approval_ref"],
            runner_approval=runner_approval_ref,
            setup_evidence=retain_setup_evidence(
                failed_evidence,
                "setup-evidence-failed",
            ),
        ),
    )
    assert held.outcome is CookPreparationOutcome.BLOCKED


def test_execute_rejects_a_pointer_outside_the_configured_artifact_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 41: the configured root contains the pointer, never the reverse."""
    fixture = _full_fixture(tmp_path / "outside")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()

    def fail_workflow(*_args: object, **_kwargs: object) -> Never:
        pytest.fail("a pointer outside the artifact root executed")

    monkeypatch.setattr(workflow, "cook", fail_workflow)

    with pytest.raises(ContractValidationError, match="outside artifact root"):
        _ = execute_accepted_handoff(
            fixture["pointer"],
            artifact_root=trusted_root,
            dispatch_writer=_writer,
            dispatch_review=_review,
            dispatch_diagnosis=_diagnosis,
        )


def test_execute_rejects_a_pointer_uri_outside_the_configured_artifact_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 59: a caller-supplied `file:` URI cannot widen the trusted root."""
    fixture = _full_fixture(tmp_path / "uri-outside")
    pointer = fixture["pointer"]
    content = pointer.read_bytes()
    pointer_ref = ArtifactRef(
        artifact_id="pointer",
        role="handoff_pointer",
        uri=pointer.as_uri(),
        digest=_digest(content),
        size_bytes=len(content),
        media_type="application/json",
    )
    trusted_root = tmp_path / "uri-trusted"
    trusted_root.mkdir()

    def fail_workflow(*_args: object, **_kwargs: object) -> Never:
        pytest.fail("a pointer URI outside the artifact root executed")

    monkeypatch.setattr(workflow, "cook", fail_workflow)

    with pytest.raises(ArtifactResolutionError, match="escapes allowed root"):
        _ = execute_accepted_handoff(
            pointer_ref,
            artifact_root=trusted_root,
            dispatch_writer=_writer,
            dispatch_review=_review,
            dispatch_diagnosis=_diagnosis,
        )


def test_execute_rejects_stale_pointer_before_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _full_fixture(tmp_path / "stale")
    pointer = fixture["pointer"]
    pointer_payload = cast(object, json.loads(pointer.read_text(encoding="utf-8")))
    assert isinstance(pointer_payload, dict)
    payload = cast(dict[str, object], pointer_payload)["payload"]
    assert isinstance(payload, dict)
    payload_uri = cast(dict[str, object], payload)["uri"]
    assert isinstance(payload_uri, str)
    payload_path = Path(urlsplit(payload_uri).path)
    _ = payload_path.write_bytes(
        payload_path.read_bytes().replace(b"cook-request", b"cook-reqXest")
    )

    def fail_workflow(*_args: object, **_kwargs: object) -> Never:
        pytest.fail("stale handoff executed")

    monkeypatch.setattr(workflow, "cook", fail_workflow)

    with pytest.raises(PayloadDigestMismatchError, match="digest"):
        _ = execute_accepted_handoff(
            pointer,
            artifact_root=tmp_path / "stale",
            dispatch_writer=_writer,
            dispatch_review=_review,
            dispatch_diagnosis=_diagnosis,
        )


def test_partial_approval_omitting_dependency_returns_replan_request(
    tmp_path: Path,
) -> None:
    fixture = _full_fixture(tmp_path / "partial", coverage_ids=("root",))
    planner = fixture["planner"]
    spec_ref = fixture["spec_ref"]
    coverage = MoldCookCoverage(
        curd_ids=("leaf",),
        unresolved_work=planner.unresolved_work,
    )
    proposal_ref = _write_ref(
        tmp_path / "partial",
        canonical_mold_cook_proposal(
            request_id="cook-request",
            kind=MoldCookApprovalKind.PARTIAL_PLAN,
            spec_digest=spec_ref.digest,
            coverage=coverage,
            planner_result=planner,
            plan_digest=fixture["plan"].digest,
        ),
        artifact_id="invalid-partial-proposal",
        role="proposal",
        filename="invalid-partial-proposal.json",
    )
    response_ref = fixture["response_ref"]
    bad_approval = bind_mold_cook_approval(
        request_id="cook-request",
        kind=MoldCookApprovalKind.PARTIAL_PLAN,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=spec_ref.digest,
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source="response.txt",
        coverage=coverage,
        plan_digest=fixture["plan"].digest,
    )
    bad_approval_ref = _write_ref(
        tmp_path / "partial",
        bad_approval,
        artifact_id="invalid-partial-approval",
        role="approval",
        filename="invalid-partial-approval.json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    result = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=tmp_path / "partial",
        evidence=PreparationEvidence(
            scope_approval=fixture["scope_approval_ref"],
            planner_result=planner,
            plan_approval=bad_approval_ref,
        ),
    )

    assert result.outcome is CookPreparationOutcome.NEEDS_PLANNING
    assert result.planner_request is not None
    assert result.planner_request.kind.value == "replan"


def test_resubmit_retains_existing_holds(tmp_path: Path) -> None:
    hold = CookExecutionHold(
        hold_id="user-hold",
        kind=CookHoldKind.USER_INTENT,
        reason="User requested a pause",
    )
    first = prepare(
        "implement the approved change",
        request_id="held-request",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        evidence=PreparationEvidence(holds=(hold,)),
    )
    second = resubmit(
        first,
        source="implement the approved change",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    assert first.outcome is CookPreparationOutcome.BLOCKED
    assert second.outcome is CookPreparationOutcome.BLOCKED
    assert second.request_id == first.request_id
    assert second.holds == (hold,)


def test_resubmit_rejects_clearance_without_bound_dialogue(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    hold = CookExecutionHold(
        hold_id="user-hold",
        kind=CookHoldKind.USER_INTENT,
        reason="User requested a pause",
    )
    first = prepare(
        "implement the approved change",
        request_id="held-request",
        repository_root=tmp_path,
        artifact_root=artifact_root,
        evidence=PreparationEvidence(holds=(hold,)),
    )
    arbitrary_ref = _write_ref(
        artifact_root,
        b"approved",
        artifact_id="unbound-response",
        role="response",
        filename="unbound-response.txt",
        media_type="text/plain",
    )

    with pytest.raises(CookEvidenceError, match="local dialogue"):
        _ = resubmit(
            first,
            source="implement the approved change",
            repository_root=tmp_path,
            artifact_root=artifact_root,
            evidence=PreparationEvidence(
                clearances=(
                    CookHoldClearance(
                        hold_id="user-hold",
                        response_ref=arbitrary_ref,
                        response_text="approved",
                    ),
                ),
            ),
        )


def test_resubmit_clears_hold_with_named_user_response(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    hold = CookExecutionHold(
        hold_id="user-hold",
        kind=CookHoldKind.USER_INTENT,
        reason="User requested a pause",
    )
    first = prepare(
        "implement the approved change",
        request_id="held-request",
        repository_root=tmp_path,
        artifact_root=artifact_root,
        evidence=PreparationEvidence(holds=(hold,)),
    )
    response = "Resume the approved work."
    dialogue_ref = _write_ref(
        artifact_root,
        {
            "response": response,
            "clear_holds": ["user-hold"],
            "execution_authorized": True,
        },
        artifact_id="user-hold-dialogue",
        role="dialogue",
        filename="user-hold-dialogue.json",
    )

    second = resubmit(
        first,
        source="implement the approved change",
        repository_root=tmp_path,
        artifact_root=artifact_root,
        evidence=PreparationEvidence(
            clearances=(
                CookHoldClearance(
                    hold_id="user-hold",
                    response_ref=dialogue_ref,
                    response_text=response,
                ),
            ),
        ),
    )

    assert "user-hold" in {item.hold_id for item in first.holds}
    assert tuple(item.hold_id for item in second.holds) == (
        "missing-spec-held-request",
    )
    assert second.outcome is CookPreparationOutcome.BLOCKED


def test_resubmit_cli_forwards_approval_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}
    previous = prepare(
        "implement the approved change",
        request_id="cli-resubmit",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    def fake_resubmit(value: object, **kwargs: object) -> object:
        assert value is previous
        captured.update(kwargs)
        return previous

    def fake_load(*_args: object, **_kwargs: object) -> object:
        return previous

    monkeypatch.setattr(
        contract_handlers,
        "load_preparation_result",
        fake_load,
    )
    monkeypatch.setattr(contract_handlers, "resubmit", fake_resubmit)
    scope = tmp_path / "scope.json"
    plan = tmp_path / "plan.json"
    runner = tmp_path / "runner.json"
    authorization = tmp_path / "authorization.json"

    status = contract_handlers.resubmit_main(
        [
            str(tmp_path / "previous.json"),
            "--scope-approval",
            str(scope),
            "--plan-approval",
            str(plan),
            "--runner-approval",
            str(runner),
            "--setup-authorization",
            str(authorization),
        ]
    )
    emitted = cast("dict[str, object]", json.loads(capsys.readouterr().out))

    assert status == 0
    assert emitted["request_id"] == "cli-resubmit"
    assert emitted["outcome"] == previous.outcome.value
    assert emitted["input_kind"] == MoldCookInputKind.TASK.value
    forwarded = cast(PreparationEvidence, captured["evidence"])
    assert forwarded.scope_approval == scope
    assert forwarded.plan_approval == plan
    assert forwarded.runner_approval == runner
    assert forwarded.setup_authorization == authorization


def test_prepare_cli_emits_validated_preparation_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = contract_handlers.prepare_main(
        [
            "--task",
            "implement the approved change",
            "--request-id",
            "cli-prepare",
            "--repository-root",
            str(tmp_path),
            "--artifact-root",
            str(tmp_path / "artifacts"),
        ]
    )
    emitted = cast("dict[str, object]", json.loads(capsys.readouterr().out))

    assert status == 0
    assert emitted["request_id"] == "cli-prepare"
    assert emitted["input_kind"] == MoldCookInputKind.TASK.value
    assert emitted["outcome"] == CookPreparationOutcome.BLOCKED.value
    assert emitted["references"]
    holds = cast("list[dict[str, object]]", emitted["holds"])
    assert [item["hold_id"] for item in holds] == ["missing-spec-cli-prepare"]


def test_corrupt_historical_pointer_fails_closed(tmp_path: Path) -> None:
    pointer = tmp_path / "historical.json"
    _ = pointer.write_text('{"operation_id":"old"}', encoding="utf-8")

    result = prepare(
        pointer,
        request_id="historical-request",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    assert result.outcome is CookPreparationOutcome.INVALID
    assert result.input_kind is MoldCookInputKind.CANONICAL_POINTER
    assert result.findings
    assert result.findings[0].code == "invalid-pointer"


def test_prepare_routes_runner_setup_through_the_shared_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "routed"
    fixture = _full_fixture(root)
    coverage = MoldCookCoverage(
        curd_ids=("root",),
        unresolved_work=fixture["planner"].unresolved_work,
    )
    authorization = CookSetupAuthorization(
        prerequisite_curd_id="root",
        allowed_paths=("tests/",),
        allowed_commands=("python -m pytest tests/setup.py",),
    )
    runner_approval_ref = _runner_approval_ref(
        root,
        spec_ref=fixture["spec_ref"],
        response_ref=fixture["response_ref"],
        coverage=coverage,
        authorization=authorization,
    )
    original = apply_runner_setup
    plan_refs: list[ArtifactRef] = []

    def spy(*args: object, **kwargs: object) -> object:
        plan_refs.append(cast(ArtifactRef, kwargs["plan_ref"]))
        return cast("Callable[..., object]", original)(*args, **kwargs)

    monkeypatch.setattr(plan_stages, "apply_runner_setup", spy)

    result = prepare(
        fixture["spec"],
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=fixture["scope_approval_ref"],
            planner_result=fixture["planner"],
            plan_approval=fixture["plan_approval_ref"],
            runner_approval=runner_approval_ref,
        ),
    )

    assert len(plan_refs) == 1
    assert result.outcome is CookPreparationOutcome.NEEDS_PREPARATION


def test_hold_clearance_ref_uses_the_shared_digest_helper(tmp_path: Path) -> None:
    dialogue = tmp_path / "hold-dialogue.json"
    content = canonical_bytes(
        {
            "response": "Resume the approved work.",
            "clear_holds": ["user-hold"],
            "execution_authorized": True,
        }
    )
    _ = dialogue.write_bytes(content)

    clearances = contract_handlers._hold_clearances(  # pyright: ignore[reportPrivateUsage]
        argparse.Namespace(clear_hold=[f"user-hold={dialogue}"])
    )

    digest = contract_handlers._digest_of(content)  # pyright: ignore[reportPrivateUsage]
    assert len(clearances) == 1
    ref = clearances[0].response_ref
    assert ref.digest == digest
    assert ref.artifact_id == f"hold-clearance-{digest.removeprefix('sha256:')[:16]}"


def test_hold_clearance_rejects_a_blank_cleared_hold_id(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    hold = CookExecutionHold(
        hold_id="user-hold",
        kind=CookHoldKind.USER_INTENT,
        reason="User requested a pause",
    )
    first = prepare(
        "implement the approved change",
        request_id="held-request",
        repository_root=tmp_path,
        artifact_root=artifact_root,
        evidence=PreparationEvidence(holds=(hold,)),
    )
    response = "Resume the approved work."
    dialogue_ref = _write_ref(
        artifact_root,
        {
            "response": response,
            "clear_holds": ["user-hold", "   "],
            "execution_authorized": True,
        },
        artifact_id="user-hold-dialogue",
        role="dialogue",
        filename="user-hold-dialogue.json",
    )

    with pytest.raises(CookEvidenceError, match="does not authorize execution"):
        _ = resubmit(
            first,
            source="implement the approved change",
            repository_root=tmp_path,
            artifact_root=artifact_root,
            evidence=PreparationEvidence(
                clearances=(
                    CookHoldClearance(
                        hold_id="user-hold",
                        response_ref=dialogue_ref,
                        response_text=response,
                    ),
                ),
            ),
        )
