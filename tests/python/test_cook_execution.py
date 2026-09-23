"""Focused regressions for the Cook preparation-to-execution seam."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Never, NotRequired, TypedDict, cast
from types import SimpleNamespace
from urllib.parse import urlsplit

import attrs
import pytest

import easy_cheese.shared.workflow as workflow
from easy_cheese.shared.fanout.press_types import PressGateResult
from easy_cheese.shared.fanout.run_fan import PressDispatcher
from easy_cheese.shared.artifacts import ArtifactResolutionError
from easy_cheese.shared.mold_cook_handoff import (
    canonical_mold_cook_proposal,
    publish_mold_cook_handoff,
)
from easy_cheese.shared.publication import (
    PayloadDigestMismatchError,
    PublicationError,
    atomic_write,
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
    validate_contract,
)
from easy_cheese_schemas.contracts import (
    BoundedScope,
    Criterion,
    CriterionDisposition,
    CriterionResultWriterView,
    CurdDisposition,
    CurdResultWriterView,
    DeliverableWriterView,
    RemediationCureWriterView,
    DiagnosisCauseWriterView,
    DiagnosisRequest,
    DiagnosisDisposition,
    DiagnosisResultWriterView,
    CurdPlan,
    IdentityAction,
    EvidenceKind,
    EvidenceRef,
    IdentityLineage,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    PlannerUncertainty,
    FixCostNow,
    ReproductionDisposition,
    ReproductionWriterView,
    ReviewDimension,
    ReviewFindingWriterView,
    ReviewRequest,
    ReviewSeverity,
    SourceLocationWriterView,
    ReviewDisposition,
    ReviewResultWriterView,
    RemediationScopeKey,
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


class ExecuteAcceptedHandoffKwargs(TypedDict):
    artifact_root: str | Path | None
    repository_root: str | Path
    dispatch_writer: workflow.WriterDispatch
    dispatch_review: workflow.ReviewDispatch
    dispatch_diagnosis: workflow.DiagnosisDispatch
    dispatch_press: NotRequired[PressDispatcher | None]
    evidence: NotRequired[Mapping[str, EvidenceRef] | None]


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


def _git(root: Path, *args: str) -> None:
    _ = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )


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
    curds: tuple[SemanticCurd, ...] | None = None,
    scope_coverage_ids: tuple[str, ...] = ("root",),
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
    if curds is None:
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
    scope_coverage = MoldCookCoverage(curd_ids=scope_coverage_ids)
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
    # Fan execution records phase artifacts in durable scope state.
    assert branches == ()
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
        SimpleNamespace(clear_hold=[f"user-hold={dialogue}"])
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



def _route_fan_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    result_artifact = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(
        evidence_id="result.txt", kind=EvidenceKind.SOURCE,
        artifact=result_artifact, summary="Verified Cook execution result",
    )
    fixture = _full_fixture(tmp_path / "fan", coverage_ids=("root", "leaf"), partial=False)
    calls: list[str] = []
    review_subjects: list[ArtifactRef] = []
    review_evidence: list[tuple[str, ...]] = []
    press_evidence = attrs.evolve(evidence, evidence_id="press-gate")

    def traced_review(request: object) -> ReviewResultWriterView:
        review_request = cast("ReviewRequest", request)
        review_subjects.append(review_request.subject)
        review_evidence.append(tuple(item.evidence_id for item in review_request.evidence))
        return _review(request)

    def traced_run_fan(*args: object, **kwargs: object) -> object:
        calls.append("run_fan")
        from easy_cheese.shared.fanout.run_fan import FanContext, run_fan_locked
        return run_fan_locked(
            cast(CurdPlan, args[0]), cast(FanContext, args[1]),
            selected=cast(Sequence[str], kwargs["selected"]),
        )

    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute
    monkeypatch.setattr(fan_execute, "run_fan_locked", traced_run_fan)
    return (
        fixture, evidence, press_evidence, calls, review_subjects, review_evidence, traced_review
    )


def test_execute_full_fan_handoff_routes_through_run_fan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, evidence, press_evidence, calls, review_subjects, review_evidence, traced_review = (
        _route_fan_setup(tmp_path, monkeypatch)
    )
    result = execute_accepted_handoff(
        fixture["pointer"], artifact_root=tmp_path / "fan", repository_root=tmp_path,
        dispatch_writer=_writer, dispatch_review=traced_review,
        dispatch_diagnosis=_diagnosis,
        dispatch_press=lambda _scope, _round: PressGateResult(
            True, "baseline-1", evidence=(press_evidence,)
        ),
        evidence={"result.txt": evidence},
    )
    assert calls == ["run_fan"]
    assert result.completed_curds == ("root", "leaf")
    assert len(review_subjects) == 3
    assert review_subjects[-1].artifact_id == "cook-plan/postmerge-subject"
    assert "press-gate" in review_evidence[-1]


def _install_manifest_write_spy(
    root: Path, monkeypatch: pytest.MonkeyPatch,
) -> list[int]:
    import easy_cheese.shared.fanout.remediation_store as remediation_store
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute

    real_write = cast(
        Callable[..., ArtifactRef], getattr(fan_execute, "_write_checkpoint_manifest")
    )
    writes: list[int] = [0]

    def traced_write(*args: object, **kwargs: object) -> ArtifactRef:
        writes[0] += 1
        with pytest.raises(remediation_store.StateStoreError):
            with remediation_store.run_lock(root, "cook-plan-cook-request"):
                pass
        return real_write(*args, **kwargs)

    monkeypatch.setattr(fan_execute, "_write_checkpoint_manifest", traced_write)
    return writes


def _concurrent_resume_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    evidence_ref = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef("result.txt", EvidenceKind.SOURCE, evidence_ref)
    root = tmp_path / "locked"
    fixture = _full_fixture(root, coverage_ids=("root", "leaf"), partial=False)
    from easy_cheese.shared.fanout.remediation_store import StateStoreError
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute
    manifest_path = cast(Callable[[Path, str], Path], getattr(fan_execute, "_manifest_path"))
    manifest = manifest_path(root, "cook-plan-cook-request")
    writes = _install_manifest_write_spy(root, monkeypatch)
    return evidence, root, fixture, StateStoreError, manifest, writes


def test_execute_fan_rejects_concurrent_resume_before_manifest_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence, root, fixture, state_store_error, manifest, writes = _concurrent_resume_setup(
        tmp_path, monkeypatch
    )
    attempted = False

    def writer(context: Mapping[str, object]) -> CurdResultWriterView:
        nonlocal attempted
        if not attempted:
            attempted = True
            before = manifest.read_bytes()
            before_writes = writes[0]
            with pytest.raises(state_store_error):
                _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
            assert writes[0] == before_writes
            assert manifest.read_bytes() == before
        return _writer(context)

    kwargs: ExecuteAcceptedHandoffKwargs = {
        "artifact_root": root, "repository_root": tmp_path,
        "dispatch_writer": _writer, "dispatch_review": _review,
        "dispatch_diagnosis": _diagnosis, "dispatch_press": _passing_press(evidence),
        "evidence": {"result.txt": evidence},
    }
    result = execute_accepted_handoff(
        fixture["pointer"], artifact_root=root, repository_root=tmp_path,
        dispatch_writer=writer, dispatch_review=_review,
        dispatch_diagnosis=_diagnosis, dispatch_press=_passing_press(evidence),
        evidence={"result.txt": evidence},
    )
    assert result.fan_next_step == "done"
    assert attempted
    assert writes[0] > 1



def test_execute_fan_stops_closed_when_state_publication_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    fixture = _full_fixture(tmp_path / "fan-failure", coverage_ids=("root", "leaf"), partial=False)
    calls: list[str] = []

    def fail_review(_request: object) -> ReviewResultWriterView:
        calls.append("review")
        return _review(_request)

    def fail_diagnosis(_request: object) -> object:
        calls.append("diagnosis")
        return _diagnosis(_request)

    import easy_cheese.shared.fanout.remediation_store as remediation_store

    def fail_publish(*_args: object, **_kwargs: object) -> object:
        raise PublicationError("state publication failed")

    monkeypatch.setattr(remediation_store, "atomic_write", fail_publish)
    with pytest.raises(remediation_store.StateStoreError, match="state publication failed"):
        _ = execute_accepted_handoff(
            fixture["pointer"],
            artifact_root=tmp_path / "fan-failure",
            repository_root=tmp_path,
            dispatch_writer=_writer,
            dispatch_review=fail_review,
            dispatch_diagnosis=fail_diagnosis,
            evidence={"result.txt": evidence},
        )

    assert calls == []



def _postmerge_writer(
    writer_calls: list[Mapping[str, object]],
) -> Callable[[Mapping[str, object]], object]:
    def writer(context: Mapping[str, object]) -> object:
        writer_calls.append(context)
        criteria = cast("tuple[Criterion, ...]", context["criteria"])
        locked = tuple(cast("tuple[str, ...]", context.get("locked_selection", ())))
        view = CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(item.criterion_id, CriterionDisposition.PASSED, ("result.txt",))
                for item in criteria
            ],
        )
        if not locked:
            return view
        return RemediationCureWriterView(result=view, applied_finding_keys=locked)

    return writer


def _postmerge_review(
    review_calls: list[int], review_subjects: list[ArtifactRef],
) -> Callable[[object], ReviewResultWriterView]:
    def review(request: object) -> ReviewResultWriterView:
        review_calls[0] += 1
        review_subjects.append(cast("ReviewRequest", request).subject)
        if review_calls[0] != 3:
            return _review(request)
        return ReviewResultWriterView(ReviewDisposition.FINDINGS, [ReviewFindingWriterView(
            ReviewSeverity.MEDIUM, ReviewDimension.CORRECTNESS, "Aggregate defect",
            ("cook-plan/postmerge-subject/evidence",), FixCostNow.CONTAINED,
        )])

    return review


def _postmerge_diagnosis(
    diagnosis_calls: list[int],
) -> Callable[[object], DiagnosisResultWriterView]:
    def diagnosis(request: object) -> DiagnosisResultWriterView:
        diagnosis_calls[0] += 1
        diagnosis_request = cast(DiagnosisRequest, request)
        subject_key = next(
            item.evidence_id for item in diagnosis_request.evidence
            if item.artifact.artifact_id == diagnosis_request.subject.artifact_id
        )
        return DiagnosisResultWriterView(
            DiagnosisDisposition.CONFIRMED,
            ReproductionWriterView(
                ReproductionDisposition.REPRODUCED, ("Run aggregate verification",),
                "Aggregate defect", (subject_key,),
            ),
            (), DiagnosisCauseWriterView("Aggregate defect cause", (subject_key,)),
            SourceLocationWriterView("src/postmerge.py", 1, 1),
        )

    return diagnosis


def test_execute_full_fan_handoff_runs_postmerge_cure_writer(tmp_path: Path) -> None:
    result_artifact = _write_ref(
        tmp_path, b"verified\\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    fixture = _full_fixture(tmp_path / "postmerge-cure", coverage_ids=("root", "leaf"), partial=False)
    writer_calls: list[Mapping[str, object]] = []
    review_calls = [0]
    review_subjects: list[ArtifactRef] = []
    diagnosis_calls = [0]
    result = execute_accepted_handoff(
        fixture["pointer"], artifact_root=tmp_path / "postmerge-cure", repository_root=tmp_path,
        dispatch_writer=_postmerge_writer(writer_calls),
        dispatch_review=_postmerge_review(review_calls, review_subjects),
        dispatch_diagnosis=_postmerge_diagnosis(diagnosis_calls),
        dispatch_press=lambda _scope, _round: PressGateResult(True, "baseline-1", evidence=(evidence,)),
        evidence={"result.txt": evidence},
    )
    assert result.fan_next_step == "done"
    assert result.whole_task_complete
    assert diagnosis_calls[0] == 1
    assert len(writer_calls) == 3
    assert len(review_subjects) == 4
    assert review_subjects[2].artifact_id == "cook-plan/postmerge-subject"
    assert review_subjects[3].artifact_id == "cook-plan/revision/1/postmerge-result/subject"
    assert review_subjects[3] != review_subjects[2]
    assert "confirmed_diagnosis" in writer_calls[-1]


def test_postmerge_writer_budget_checkpoint_preserves_blocked_result(
    tmp_path: Path,
) -> None:
    fixture = _full_fixture(tmp_path / "postmerge-budget", coverage_ids=("root", "leaf"), partial=False)
    curd = attrs.evolve(
        fixture["plan"].curds[0],
        curd_id="postmerge",
        outcome="Apply aggregate remediation",
    )
    checkpoint = workflow.WriterCheckpoint(
        reason="writer budget reached",
        remaining=("finish aggregate validation",),
    )

    def writer(_context: Mapping[str, object]) -> CurdResultWriterView:
        raise workflow.WriterBudgetExceeded(checkpoint)

    execution = workflow.execute_curd_writer(
        fixture["plan"],
        curd,
        1,
        repository_root=tmp_path,
        artifact_directory=tmp_path / "postmerge-budget",
        resolved_evidence={},
        durable_evidence={},
        shared_inputs=(),
        phase="cure",
        provenance_refs=("diagnosis-1",),
        dispatch_writer=writer,
        extra_context={"aggregate_subject": "postmerge-subject"},
        result_id="cook-plan/revision/1/postmerge-result",
    )

    assert execution.result.disposition is CurdDisposition.BLOCKED
    assert execution.result.result_id == "cook-plan/revision/1/result/1"
    assert execution.result.unresolved_work == (
        "writer stopped at its budget: WriterBudgetExceeded: writer budget reached",
        "finish aggregate validation",
    )


def test_execute_fan_writer_failure_blocks_without_review_or_diagnosis(tmp_path: Path) -> None:
    result_artifact = _write_ref(tmp_path, b"verified\\n", artifact_id="result", role="evidence", filename="result.txt", media_type="text/plain")
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    fixture = _full_fixture(tmp_path / "writer-failure", coverage_ids=("root", "leaf"), partial=False)
    events: list[str] = []

    def fail_writer(_context: Mapping[str, object]) -> CurdResultWriterView:
        raise RuntimeError("writer unavailable")

    def review(_request: object) -> ReviewResultWriterView:
        events.append("review")
        return _review(_request)

    def diagnosis(_request: object) -> object:
        events.append("diagnosis")
        raise AssertionError("diagnosis must not run")

    result = execute_accepted_handoff(fixture["pointer"], artifact_root=tmp_path / "writer-failure", repository_root=tmp_path, dispatch_writer=fail_writer, dispatch_review=review, dispatch_diagnosis=diagnosis, evidence={"result.txt": evidence})
    assert result.fan_next_step == "mold"
    assert not result.whole_task_complete
    assert events == []
    assert result.execution_results[1]
    assert all(item.disposition is CurdDisposition.BLOCKED for item in result.execution_results[1])


def _fan_recovery_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[_FullFixture, EvidenceRef]:
    caller = tmp_path / "caller"
    caller.mkdir()
    monkeypatch.chdir(caller)
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "wheypoint"))
    monkeypatch.delenv("EASY_CHEESE_PROJECT", raising=False)
    grounded = tmp_path / "src" / "workflow.py"
    grounded.parent.mkdir()
    _ = grounded.write_text("def repair():\n    pass\n", encoding="utf-8")
    root = attrs.evolve(
        _curd("root"),
        criteria=(
            Criterion("root-first", "The first repair is verified", "pytest first"),
            Criterion("root-second", "The second repair is verified", "pytest second"),
        ),
    )
    fixture = _full_fixture(
        tmp_path / "fan-recovery",
        coverage_ids=("root",),
        partial=True,
        curds=(root, _curd("leaf", dependencies=("root",))),
    )
    result_artifact = _write_ref(
        tmp_path,
        b"verified\n",
        artifact_id="result",
        role="evidence",
        filename="result.txt",
        media_type="text/plain",
    )
    return fixture, EvidenceRef("result.txt", EvidenceKind.SOURCE, result_artifact)


def test_execute_accepted_fan_handoff_recovers_writer_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, evidence = _fan_recovery_fixture(tmp_path, monkeypatch)
    attempts = 0
    contexts: list[Mapping[str, object]] = []

    def writer(context: Mapping[str, object]) -> object:
        nonlocal attempts
        attempts += 1
        contexts.append(context)
        if attempts == 1:
            _ = (tmp_path / "repair.txt").write_bytes(b"first repair\n")
            raise workflow.WriterBudgetExceeded(
                workflow.WriterCheckpoint(
                    reason="context budget reached",
                    completed=[
                        CriterionResultWriterView(
                            "root-first",
                            CriterionDisposition.PASSED,
                            evidence_keys=["repair.txt"],
                        )
                    ],
                    deliverables=[
                        DeliverableWriterView("repair", "repair.txt", "text/plain")
                    ],
                    remaining=["Finish the second repair"],
                    grounded=["src/workflow.py#1-2"],
                )
            )
        return _writer(context)
    executions: list[workflow.CurdWriterExecution] = []
    execute_writer = cast(
        "Callable[..., workflow.CurdWriterExecution]", workflow.execute_curd_writer
    )

    def traced_execute(*args: object, **kwargs: object) -> workflow.CurdWriterExecution:
        execution = execute_writer(*args, **kwargs)
        executions.append(execution)
        return execution

    monkeypatch.setattr(workflow, "execute_curd_writer", traced_execute)

    result = execute_accepted_handoff(
        fixture["pointer"],
        artifact_root=tmp_path / "fan-recovery",
        repository_root=tmp_path,
        dispatch_writer=writer,
        dispatch_review=_review,
        dispatch_diagnosis=_diagnosis,
        evidence={"result.txt": evidence},
    )

    assert attempts == 2
    assert contexts[1]["working_context"] == ("src/workflow.py#1-2",)
    assert contexts[1]["retry_count"] == 1
    assert len(executions) == 1
    assert executions[0].writer_context_digest == workflow._canonical_digest(  # pyright: ignore[reportPrivateUsage]
        contexts[1]
    )
    assert executions[0].writer_context_digest != workflow._canonical_digest(  # pyright: ignore[reportPrivateUsage]
        contexts[0]
    )
    assert result.fan_next_step == "mold"
    assert not result.whole_task_complete
    assert result.execution_results[1][0].disposition is CurdDisposition.PASSED


def test_execute_accepted_fan_handoff_preserves_checkpoint_on_retry_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, evidence = _fan_recovery_fixture(tmp_path, monkeypatch)
    attempts = 0
    contexts: list[Mapping[str, object]] = []

    def writer(context: Mapping[str, object]) -> object:
        nonlocal attempts
        attempts += 1
        contexts.append(context)
        if attempts == 1:
            _ = (tmp_path / "repair.txt").write_bytes(b"first repair\n")
            raise workflow.WriterBudgetExceeded(
                workflow.WriterCheckpoint(
                    reason="context budget reached",
                    completed=[
                        CriterionResultWriterView(
                            "root-first",
                            CriterionDisposition.PASSED,
                            evidence_keys=["repair.txt"],
                        )
                    ],
                    deliverables=[
                        DeliverableWriterView("repair", "repair.txt", "text/plain")
                    ],
                    remaining=["Finish the second repair"],
                    grounded=["src/workflow.py#1-2"],
                )
            )
        _ = (tmp_path / "repair.txt").write_bytes(b"overwritten on retry\n")
        return object()

    executions: list[workflow.CurdWriterExecution] = []
    execute_writer = cast(
        "Callable[..., workflow.CurdWriterExecution]", workflow.execute_curd_writer
    )

    def traced_execute(*args: object, **kwargs: object) -> workflow.CurdWriterExecution:
        execution = execute_writer(*args, **kwargs)
        executions.append(execution)
        return execution

    monkeypatch.setattr(workflow, "execute_curd_writer", traced_execute)

    result = execute_accepted_handoff(
        fixture["pointer"],
        artifact_root=tmp_path / "fan-recovery",
        repository_root=tmp_path,
        dispatch_writer=writer,
        dispatch_review=_review,
        dispatch_diagnosis=_diagnosis,
        evidence={"result.txt": evidence},
    )

    curd_result = result.execution_results[1][0]
    assert attempts == 2
    assert len(executions) == 1
    assert executions[0].writer_context_digest == workflow._canonical_digest(  # pyright: ignore[reportPrivateUsage]
        contexts[0]
    )
    assert result.fan_next_step == "mold"
    assert not result.whole_task_complete
    assert curd_result.disposition is CurdDisposition.BLOCKED
    assert curd_result.criterion_results[0].disposition is CriterionDisposition.PASSED
    assert curd_result.criterion_results[0].evidence[0].artifact.digest == _digest(
        b"first repair\n"
    )
    assert curd_result.deliverables[0].digest == _digest(b"first repair\n")


def _passing_press(evidence: EvidenceRef) -> PressDispatcher:

    def press(_scope: RemediationScopeKey, _round: int) -> PressGateResult:
        return PressGateResult(True, "baseline-1", evidence=(evidence,))

    return press


def test_execute_accepted_handoff_resumes_from_persisted_results(
    tmp_path: Path,
) -> None:
    result_artifact = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    fixture = _full_fixture(tmp_path / "resume", coverage_ids=("root", "leaf"), partial=False)
    counts = {"cook": 0, "age": 0, "press": 0}

    def writer(context: Mapping[str, object]) -> CurdResultWriterView:
        counts["cook"] += 1
        return _writer(context)

    def review(request: object) -> ReviewResultWriterView:
        counts["age"] += 1
        return _review(request)

    def press(scope: RemediationScopeKey, round_number: int) -> PressGateResult:
        counts["press"] += 1
        return _passing_press(evidence)(scope, round_number)

    kwargs: ExecuteAcceptedHandoffKwargs = {
        "artifact_root": tmp_path / "resume", "repository_root": tmp_path,
        "dispatch_writer": writer, "dispatch_review": review,
        "dispatch_diagnosis": _diagnosis, "dispatch_press": press,
        "evidence": {"result.txt": evidence},
    }
    first = execute_accepted_handoff(fixture["pointer"], **kwargs)
    first_counts = counts.copy()
    second = execute_accepted_handoff(fixture["pointer"], **kwargs)

    assert first.fan_next_step == "done"
    assert second.fan_next_step == "done"
    assert second.execution_result_refs
    assert counts == first_counts


def _linear_rerun_kwargs(tmp_path: Path, root: Path, writer: object) -> ExecuteAcceptedHandoffKwargs:
    result_artifact = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    return cast(ExecuteAcceptedHandoffKwargs, cast(object, {
        "artifact_root": root, "repository_root": tmp_path,
        "dispatch_writer": writer, "dispatch_review": _review,
        "dispatch_diagnosis": _diagnosis, "evidence": {"result.txt": evidence},
    }))


def test_linear_rerun_redispatches_a_cached_blocked_result(tmp_path: Path) -> None:
    root = tmp_path / "blocked"
    fixture = _full_fixture(root, partial=False, curds=(_curd("root"),))
    calls: list[CriterionDisposition] = []

    def writer(context: Mapping[str, object]) -> CurdResultWriterView:
        disposition = CriterionDisposition.PASSED if calls else CriterionDisposition.BLOCKED
        calls.append(disposition)
        view = _writer(context)
        return CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(
                    criterion_id=item.criterion_id,
                    disposition=disposition,
                    evidence_keys=item.evidence_keys,
                )
                for item in view.criterion_results
            ],
        )

    kwargs = _linear_rerun_kwargs(tmp_path, root, writer)
    first = execute_accepted_handoff(fixture["pointer"], **kwargs)
    assert first.completed_curds == ()
    second = execute_accepted_handoff(fixture["pointer"], **kwargs)

    assert len(calls) == 2
    assert second.completed_curds == ("root",)
    third = execute_accepted_handoff(fixture["pointer"], **kwargs)
    assert len(calls) == 2
    assert third.completed_curds == ("root",)
    assert [item.source_curd_ref.curd_id for item in third.execution_results[1]] == ["root"]


def test_linear_rerun_ignores_a_cached_result_outside_coverage(tmp_path: Path) -> None:
    root = tmp_path / "outside"
    fixture = _full_fixture(root, partial=False, curds=(_curd("root"),))
    calls: list[int] = []

    def writer(context: Mapping[str, object]) -> CurdResultWriterView:
        calls.append(1)
        return _writer(context)

    kwargs = _linear_rerun_kwargs(tmp_path, root, writer)
    _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
    import easy_cheese.skills.cook.preparation.execute as execute_module
    record_path = cast(Callable[[Path, str], Path], getattr(execute_module, "_execution_record_path"))(
        root, "cook-plan-cook-request"
    )
    payload = cast(dict[str, list[dict[str, dict[str, object]]]], json.loads(record_path.read_text()))
    stranger = cast(dict[str, dict[str, object]], json.loads(json.dumps(payload["results"][0])))
    stranger["source_curd_ref"]["curd_id"] = "stranger"
    payload["results"].append(stranger)
    _ = record_path.write_bytes(canonical_bytes(payload))

    rerun = execute_accepted_handoff(fixture["pointer"], **kwargs)

    assert len(calls) == 1
    assert [item.source_curd_ref.curd_id for item in rerun.execution_results[1]] == ["root"]
    assert rerun.completed_curds == ("root",)


def test_execute_partial_coverage_routes_to_mold(tmp_path: Path) -> None:
    result_artifact = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    fixture = _full_fixture(tmp_path / "partial-execution", coverage_ids=("root",), partial=True)
    result = execute_accepted_handoff(
        fixture["pointer"], artifact_root=tmp_path / "partial-execution",
        repository_root=tmp_path, dispatch_writer=_writer,
        dispatch_review=_review, dispatch_diagnosis=_diagnosis,
        evidence={"result.txt": evidence},
    )
    assert result.fan_next_step == "mold"
    assert not result.whole_task_complete


def test_execute_persisted_stall_exposes_validated_remediation_request(
    tmp_path: Path,
) -> None:
    fixture = _full_fixture(tmp_path / "stall", coverage_ids=("root", "leaf"), partial=False)

    def failing_writer(_context: Mapping[str, object]) -> CurdResultWriterView:
        raise RuntimeError("writer unavailable")

    result = execute_accepted_handoff(
        fixture["pointer"], artifact_root=tmp_path / "stall",
        repository_root=tmp_path, dispatch_writer=failing_writer,
        dispatch_review=_review, dispatch_diagnosis=_diagnosis,
    )
    assert result.fan_next_step == "mold"
    assert result.remediation_request_ref is not None
    payload = Path(urlsplit(result.remediation_request_ref.uri).path).read_bytes()
    request = cast("PlannerRequest", validate_contract(
        payload, PlannerRequest, _version(PlannerRequest)
    ).value)
    assert request.kind is PlannerRequestKind.REMEDIATE
    assert request.source_plan_ref is not None
    assert request.source_plan_ref.plan_id == fixture["plan"].plan_id
    assert {item.artifact.role for item in request.evidence} >= {"remediation_state", "curd-result"}


def _corrupt_resume_inputs(tmp_path: Path):
    result_artifact = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    root = tmp_path / "corrupt"
    fixture = _full_fixture(root, coverage_ids=("root", "leaf"), partial=False)
    kwargs: ExecuteAcceptedHandoffKwargs = {
        "artifact_root": root, "repository_root": tmp_path,
        "dispatch_writer": _writer, "dispatch_review": _review,
        "dispatch_diagnosis": _diagnosis, "dispatch_press": _passing_press(evidence),
        "evidence": {"result.txt": evidence},
    }
    _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
    return fixture, kwargs


def test_execute_rejects_corrupt_resume_context_and_cross_plan_cache(
    tmp_path: Path,
) -> None:
    fixture, kwargs = _corrupt_resume_inputs(tmp_path)
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute
    context_path = cast(Callable[[Path, str, str], Path], getattr(fan_execute, "_context_path"))(
        tmp_path / "corrupt", "cook-plan-cook-request", "root"
    )
    _ = context_path.write_text("not-json")
    with pytest.raises(ContractValidationError, match="checkpoint artifact digest mismatch"):
        _ = execute_accepted_handoff(fixture["pointer"], **kwargs)

    other_root = tmp_path / "cross-plan"
    other_fixture = _full_fixture(other_root, coverage_ids=("root", "leaf"), partial=False)
    other_kwargs = cast(ExecuteAcceptedHandoffKwargs, cast(object, dict(kwargs)))
    other_kwargs["artifact_root"] = other_root
    _ = execute_accepted_handoff(other_fixture["pointer"], **other_kwargs)
    import easy_cheese.skills.cook.preparation.execute as execute_module
    record_path = cast(Callable[[Path, str], Path], getattr(execute_module, "_execution_record_path"))(
        other_root, "cook-plan-cook-request"
    )
    payload = cast(object, json.loads(record_path.read_text()))
    assert isinstance(payload, dict)
    payload = cast(dict[str, object], payload)
    results_payload = payload["results"]
    assert isinstance(results_payload, list)
    results_payload = cast(list[object], results_payload)
    first_result = results_payload[0]
    assert isinstance(first_result, dict)
    first_result = cast(dict[str, object], first_result)
    source_plan_ref = first_result["source_plan_ref"]
    assert isinstance(source_plan_ref, dict)
    source_plan_ref = cast(dict[str, object], source_plan_ref)
    source_plan_ref["plan_id"] = "other-plan"
    _ = record_path.write_bytes(canonical_bytes(payload))
    with pytest.raises(ContractValidationError, match="another plan"):
        _ = execute_accepted_handoff(other_fixture["pointer"], **other_kwargs)

def test_execute_rejects_missing_checkpoint_commit_marker(tmp_path: Path) -> None:
    result_artifact = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    root = tmp_path / "missing-marker"
    fixture = _full_fixture(root, coverage_ids=("root", "leaf"), partial=False)
    kwargs: ExecuteAcceptedHandoffKwargs = {
        "artifact_root": root, "repository_root": tmp_path,
        "dispatch_writer": _writer, "dispatch_review": _review,
        "dispatch_diagnosis": _diagnosis, "dispatch_press": _passing_press(evidence),
        "evidence": {"result.txt": evidence},
    }
    _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute
    manifest_path = cast(Callable[[Path, str], Path], getattr(fan_execute, "_manifest_path"))(
        root, "cook-plan-cook-request"
    )
    payload = cast(dict[str, object], json.loads(manifest_path.read_text()))
    _ = payload.pop("commit_marker")
    atomic_write(manifest_path, canonical_bytes(payload))
    with pytest.raises(ContractValidationError, match="commit marker mismatch"):
        _ = execute_accepted_handoff(fixture["pointer"], **kwargs)


def test_execute_rejects_invalid_checkpoint_commit_marker(tmp_path: Path) -> None:
    result_artifact = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    root = tmp_path / "invalid-marker"
    fixture = _full_fixture(root, coverage_ids=("root", "leaf"), partial=False)
    kwargs: ExecuteAcceptedHandoffKwargs = {
        "artifact_root": root, "repository_root": tmp_path,
        "dispatch_writer": _writer, "dispatch_review": _review,
        "dispatch_diagnosis": _diagnosis, "dispatch_press": _passing_press(evidence),
        "evidence": {"result.txt": evidence},
    }
    _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute
    manifest_path = cast(Callable[[Path, str], Path], getattr(fan_execute, "_manifest_path"))(
        root, "cook-plan-cook-request"
    )
    payload = cast(dict[str, object], json.loads(manifest_path.read_text()))
    payload["commit_marker"] = "invalid"
    atomic_write(manifest_path, canonical_bytes(payload))
    with pytest.raises(ContractValidationError, match="commit marker mismatch"):
        _ = execute_accepted_handoff(fixture["pointer"], **kwargs)





def _productive_cure_fixture(tmp_path: Path):
    result_artifact = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef(evidence_id="result.txt", kind=EvidenceKind.SOURCE, artifact=result_artifact)
    fixture = _full_fixture(tmp_path / "awaiting", coverage_ids=("root", "leaf"), partial=False)
    counts = {"cook": 0, "age": 0, "cure": 0}

    def writer(context: Mapping[str, object]) -> CurdResultWriterView:
        counts["cure" if context.get("locked_selection") else "cook"] += 1
        return _writer(context)

    def review(request: object) -> ReviewResultWriterView:
        counts["age"] += 1
        return _review(request)

    kwargs: ExecuteAcceptedHandoffKwargs = {
        "artifact_root": tmp_path / "awaiting", "repository_root": tmp_path,
        "dispatch_writer": writer, "dispatch_review": review,
        "dispatch_diagnosis": _diagnosis,
        "dispatch_press": lambda _scope, _round: PressGateResult(
            True, "baseline-1", evidence=(evidence,)
        ),
        "evidence": {"result.txt": evidence},
    }
    first = execute_accepted_handoff(fixture["pointer"], **kwargs)
    assert first.fan_next_step == "done"
    return fixture, evidence, counts, kwargs


def _productive_cure_review(evidence: EvidenceRef):
    from easy_cheese_schemas import (
        CoverageDisposition, FixCostNow, ReviewCoverage, ReviewDimension,
        ReviewFinding, ReviewResult, ReviewSeverity,
    )
    return ReviewResult(
        contract_version=_version(ReviewResult), review_id="resume-findings",
        disposition=ReviewDisposition.FINDINGS,
        findings=(ReviewFinding(
            finding_id="resume-finding", dimension=ReviewDimension.CORRECTNESS,
            severity=ReviewSeverity.MEDIUM, summary="resume finding", evidence=(evidence,),
            fix_cost_now=FixCostNow.CONTAINED, location=None,
        ),),
        coverage=(ReviewCoverage(target="root", disposition=CoverageDisposition.COVERED),),
    )


def _rewrite_productive_cure_manifest(
    tmp_path: Path, fixture: _FullFixture, state_path: Path,
) -> None:
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute
    manifest_path = cast(Callable[[Path, str], Path], getattr(fan_execute, "_manifest_path"))(
        tmp_path / "awaiting", "cook-plan-cook-request"
    )
    manifest = cast(dict[str, object], json.loads(manifest_path.read_text()))
    raw_references = cast(list[object], manifest["references"])
    artifact_from_json = cast(Callable[[object], ArtifactRef], getattr(fan_execute, "_artifact_from_json"))
    path_ref = cast(Callable[..., ArtifactRef], getattr(fan_execute, "_path_ref"))
    write_manifest = cast(Callable[..., ArtifactRef], getattr(fan_execute, "_write_checkpoint_manifest"))
    references: list[ArtifactRef] = []
    for raw_reference in raw_references:
        reference = artifact_from_json(raw_reference)
        if reference.uri == state_path.resolve().as_uri():
            reference = path_ref(state_path, artifact_id=reference.artifact_id, role=reference.role)
        references.append(reference)
    _ = write_manifest(
        tmp_path / "awaiting", "cook-plan-cook-request", fixture["plan"], tmp_path, tuple(references)
    )


def _prepare_productive_cure_resume(
    tmp_path: Path, fixture: _FullFixture, evidence: EvidenceRef,
) -> Path:
    from easy_cheese.shared.fanout.remediation_store import load_state, publish_state, scope_state_path
    from easy_cheese.shared.fanout import remediation
    from easy_cheese_schemas import (
        RemediationCursor, RemediationDisposition, RemediationScopeKey,
        RemediationScopeKind, SourcePlanRef,
    )
    scope = RemediationScopeKey(
        run_id="cook-plan-cook-request",
        source_plan_ref=SourcePlanRef(fixture["plan"].plan_id, fixture["plan"].revision, fixture["plan"].digest),
        scope_kind=RemediationScopeKind.CURD, scope_id="root",
    )
    state_path = scope_state_path(tmp_path / "awaiting", scope)
    state = load_state(tmp_path / "awaiting", state_path)
    state = attrs.evolve(
        state, cursor=RemediationCursor.AWAITING_REVIEW,
        disposition=RemediationDisposition.ACTIVE, locked_selection=(), receipts=(),
    )
    state, _ = remediation.decide_review(state, _productive_cure_review(evidence), evidence.artifact)
    state, _ = remediation.decide_cure(
        state, evidence.artifact, state.locked_selection, (), (), ("src/root.py",), new_gate_failures=False
    )
    assert state.cursor is RemediationCursor.AWAITING_REVIEW
    assert state.receipts[-1].cure_result_ref is not None
    _ = publish_state(tmp_path / "awaiting", state_path, state)
    _rewrite_productive_cure_manifest(tmp_path, fixture, state_path)
    return state_path


def test_execute_resume_from_productive_cure_skips_cure(
    tmp_path: Path,
) -> None:
    fixture, evidence, counts, kwargs = _productive_cure_fixture(tmp_path)
    _ = _prepare_productive_cure_resume(tmp_path, fixture, evidence)
    before = counts.copy()
    second = execute_accepted_handoff(fixture["pointer"], **kwargs)
    assert second.fan_next_step == "done"
    assert counts["cook"] == before["cook"]
    assert counts["cure"] == before["cure"]
    assert counts["age"] == before["age"] + 1


def test_fan_context_path_isolated_by_scope_kind(tmp_path: Path) -> None:
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute
    from easy_cheese_schemas import RemediationScopeKind

    context_path = cast(Callable[..., Path], getattr(fan_execute, "_context_path"))
    curd = context_path(tmp_path, "run-1", RemediationScopeKind.CURD, "postmerge")
    postmerge = context_path(tmp_path, "run-1", RemediationScopeKind.POSTMERGE, "postmerge")

    assert curd != postmerge


def test_press_resume_requires_manifest_refs(tmp_path: Path) -> None:
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute

    loader = cast(Callable[..., tuple[object, ...]], getattr(fan_execute, "_load_persisted_press_results"))
    with pytest.raises(TypeError):
        _ = loader(tmp_path, "run-1")



def _manifest_artifact_ids(root: Path, run_id: str) -> set[str]:
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute

    manifest_path = cast(Callable[[Path, str], Path], getattr(fan_execute, "_manifest_path"))(
        root, run_id
    )
    payload = cast(dict[str, object], json.loads(manifest_path.read_text()))
    references = cast(list[object], payload["references"])
    return {
        cast(str, cast(dict[str, object], item)["artifact_id"])
        for item in references
    }


def test_manifest_reload_separates_curd_named_postmerge_from_postmerge(
    tmp_path: Path,
) -> None:
    evidence_ref = _write_ref(
        tmp_path, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    evidence = EvidenceRef("result.txt", EvidenceKind.SOURCE, evidence_ref)
    root = tmp_path / "manifest"
    fixture = _full_fixture(
        root,
        coverage_ids=("postmerge", "leaf"),
        scope_coverage_ids=("root",),
        partial=False,
        curds=(_curd("postmerge"), _curd("leaf", dependencies=("postmerge",))),
    )
    kwargs: ExecuteAcceptedHandoffKwargs = {
        "artifact_root": root, "repository_root": tmp_path,
        "dispatch_writer": _writer, "dispatch_review": _review,
        "dispatch_diagnosis": _diagnosis, "dispatch_press": _passing_press(evidence),
        "evidence": {"result.txt": evidence},
    }
    _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
    run_id = "cook-plan-cook-request"
    ids = _manifest_artifact_ids(root, run_id)
    assert f"{run_id}/curd/postmerge/state" in ids
    assert f"{run_id}/postmerge/postmerge/state" in ids
    assert "postmerge-press-1" in ids
    assert execute_accepted_handoff(fixture["pointer"], **kwargs).fan_next_step == "done"
    assert "postmerge-press-1" in _manifest_artifact_ids(root, run_id)
    assert execute_accepted_handoff(fixture["pointer"], **kwargs).fan_next_step == "done"
    assert "postmerge-press-1" in _manifest_artifact_ids(root, run_id)


def _tracked_resume_setup(
    root: Path,
) -> tuple[Path, _FullFixture, Path, EvidenceRef]:
    artifact_root = root / "artifacts"
    fixture = _full_fixture(artifact_root, coverage_ids=("root", "leaf"), partial=False)
    tracked = root / "src" / "root.py"
    tracked.parent.mkdir()
    _ = tracked.write_text("baseline\n")
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Cook Test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    evidence_ref = _write_ref(
        root, b"verified\n", artifact_id="result", role="evidence",
        filename="result.txt", media_type="text/plain",
    )
    return artifact_root, fixture, tracked, EvidenceRef(
        "result.txt", EvidenceKind.SOURCE, evidence_ref
    )


def test_resume_accepts_writer_snapshot_then_rejects_external_edit(
    tmp_path: Path,
) -> None:
    root = tmp_path
    artifact_root, fixture, tracked, evidence = _tracked_resume_setup(root)
    calls = 0

    def writer(context: Mapping[str, object]) -> CurdResultWriterView:
        nonlocal calls
        calls += 1
        _ = tracked.write_text(f"writer-{calls}\n")
        return _writer(context)

    kwargs: ExecuteAcceptedHandoffKwargs = {
        "artifact_root": artifact_root, "repository_root": root,
        "dispatch_writer": writer, "dispatch_review": _review,
        "dispatch_diagnosis": _diagnosis, "dispatch_press": _passing_press(evidence),
        "evidence": {"result.txt": evidence},
    }
    _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
    before = calls
    _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
    assert calls == before
    _ = tracked.write_text("external-edit\n")
    with pytest.raises(ContractValidationError, match="repository identity mismatch"):
        _ = execute_accepted_handoff(fixture["pointer"], **kwargs)
    assert calls == before


def test_repository_identity_ignores_ignored_entries_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path
    tracked = root / "tracked.py"
    _ = tracked.write_text("tracked\n")
    ignored = root / "ignored"
    ignored.mkdir()
    ignored_file = ignored / "value.txt"
    _ = ignored_file.write_text("ignored\n")
    outside = tmp_path.parent / "outside.txt"
    _ = outside.write_text("outside\n")
    (root / "ignored-link").symlink_to(outside)
    _ = (root / ".gitignore").write_text("ignored/\nignored-link\n")
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Cook Test")
    _git(root, "add", "tracked.py", ".gitignore")
    _git(root, "commit", "-m", "baseline")
    import easy_cheese.skills.cook.preparation.fan_execute as fan_execute

    identity_fn = cast(
        Callable[[Path], str], getattr(fan_execute, "_repository_identity")
    )
    identity = identity_fn(root)
    _ = ignored_file.write_text("changed\n")
    _ = outside.write_text("changed\n")
    assert identity_fn(root) == identity
    _ = (root / "untracked.py").write_text("untracked\n")
    assert identity_fn(root) != identity
    with monkeypatch.context() as patch:
        def fail_git(*_args: object, **_kwargs: object) -> Never:
            raise subprocess.TimeoutExpired("git", 1)

        patch.setattr(fan_execute, "run_git", fail_git)
        with pytest.raises(ContractValidationError):
            _ = identity_fn(root)
