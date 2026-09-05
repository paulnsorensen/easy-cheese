from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import attrs
from attrs import Attribute
import pytest

import easy_cheese_schemas.workflow as workflow_module
from easy_cheese_schemas.artifacts import (
    ResolvedAgentArtifact,
    resolve_artifact,
)
from easy_cheese_schemas.contracts import (
    AgentWriterView,
    ArtifactRef,
    BoundedContextWriterView,
    BoundedScope,
    CoverageDisposition,
    CriterionResultWriterView,
    CriterionWriterView,
    CriterionDisposition,
    CurdDisposition,
    CurdPlan,
    CurdPlanWriterView,
    CurdResult,
    CurdResultWriterView,
    DeliverableWriterView,
    DiagnosisCauseWriterView,
    DiagnosisDisposition,
    DiagnosisRequest,
    DiagnosisResult,
    DiagnosisResultWriterView,
    EvidenceKind,
    EvidenceRef,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResultWriterView,
    PlannerUncertaintyWriterView,
    Reproduction,
    ReproductionDisposition,
    ReproductionWriterView,
    ReviewCoverage,
    ReviewDisposition,
    ReviewRequest,
    ReviewResult,
    ReviewResultWriterView,
    SemanticCurdWriterView,
    SourceLocationWriterView,
    UncertaintyScope,
    WriterViewKind,
)
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    supported_version_for,
)
from easy_cheese_schemas.workflow import (
    WriterBudgetExceeded,
    WriterCheckpoint,
    bind_diagnosis,
    cook,
    cure,
    plan,
    run_workflow,
)

HOST_ONLY_FIELDS = {
    "artifact_id",
    "contract_version",
    "coverage",
    "curd_id",
    "criterion_id",
    "digest",
    "diagnosis_id",
    "evidence",
    "expected_criterion_ids",
    "finding_id",
    "hypothesis_id",
    "identity_action",
    "lineage",
    "plan_id",
    "request_id",
    "result_id",
    "review_id",
    "revision",
    "runtime_refs",
    "schema_uri",
    "size_bytes",
    "source_curd_ref",
    "source_plan_ref",
    "uri",
}


def version(contract: type):
    value = supported_version_for(contract)
    assert value is not None
    return value


def digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def source_artifact(root: Path) -> ArtifactRef:
    payload = b"approved workflow contract\n"
    _ = (root / "spec.md").write_bytes(payload)
    return ArtifactRef(
        artifact_id="source-artifact",
        role="source",
        uri="repo://spec.md",
        digest=digest(payload),
        size_bytes=len(payload),
        media_type="text/markdown",
    )


def planner_request(*, evidence: tuple[EvidenceRef, ...] = ()) -> PlannerRequest:
    return PlannerRequest(
        contract_version=version(PlannerRequest),
        request_id="workflow-request",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Implement the workflow contract seam",
        evidence=evidence,
    )


def writer_curd() -> SemanticCurdWriterView:
    return SemanticCurdWriterView(
        key="core",
        outcome="Execute one typed workflow curd",
        scope=BoundedScope(paths=["src/workflow.py"]),
        input_keys=["source"],
        outputs=["A verified workflow artifact"],
        criteria=[
            CriterionWriterView(
                description="The workflow artifact is verified",
                check="pytest tests/test_workflow.py",
            )
        ],
    )


def complete_planner() -> PlannerResultWriterView:
    return PlannerResultWriterView(
        disposition=PlannerDisposition.COMPLETE,
        plan=CurdPlanWriterView(
            objective="Implement the workflow contract seam",
            curds=[writer_curd()],
        ),
    )


def clean_review(_request: ReviewRequest) -> ReviewResultWriterView:
    return ReviewResultWriterView(ReviewDisposition.CLEAN, [])


@pytest.mark.parametrize(
    ("representation", "disposition"),
    [
        (representation, disposition)
        for representation in ("direct", "agent", "mapping")
        for disposition in (
            ReviewDisposition.CLEAN,
            ReviewDisposition.BLOCKED,
            ReviewDisposition.INVALID,
            ReviewDisposition.EXECUTOR_FAILURE,
        )
    ],
)
def test_review_coverage_ledger_is_representation_independent(
    tmp_path: Path,
    representation: str,
    disposition: ReviewDisposition,
) -> None:
    request = ReviewRequest(
        contract_version=version(ReviewRequest),
        review_id="review-coverage",
        subject=source_artifact(tmp_path),
        coverage_targets=("target",),
    )
    reason = f"{disposition.value} review reason"
    view = ReviewResultWriterView(
        disposition=disposition,
        findings=[],
        reason=None if disposition is ReviewDisposition.CLEAN else reason,
    )
    output: object
    if representation == "direct":
        output = view
    elif representation == "agent":
        output = AgentWriterView(WriterViewKind.REVIEW_RESULT, view)
    else:
        output = {
            "kind": "review_result",
            "payload": {
                "disposition": disposition.value,
                "findings": [],
                "reason": None if disposition is ReviewDisposition.CLEAN else reason,
            },
        }

    result = workflow_module._review(request, output, {})  # pyright: ignore[reportPrivateUsage] -- whitebox test of the module-private review path

    expected_disposition = (
        CoverageDisposition.COVERED
        if disposition is ReviewDisposition.CLEAN
        else CoverageDisposition.NOT_COVERED
    )
    expected_reason = (
        None if expected_disposition is CoverageDisposition.COVERED else reason
    )
    assert result.coverage == (
        ReviewCoverage("target", expected_disposition, expected_reason),
    )


def unused_diagnosis(_request: DiagnosisRequest) -> DiagnosisResultWriterView:
    raise AssertionError("diagnosis dispatch must not run for a passing curd")


def run_complete(root: Path, events: list[str], contexts: list[Mapping[str, object]]):
    source = source_artifact(root)

    def dispatch_planner(request: PlannerRequest) -> PlannerResultWriterView:
        assert request == planner_request()
        events.append("planner")
        return complete_planner()

    def dispatch_writer(context: Mapping[str, object]) -> CurdResultWriterView:
        events.append("writer")
        contexts.append(context)
        payload = b"verified workflow output\n"
        _ = (root / "result.txt").write_bytes(payload)
        return CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(
                    CriterionDisposition.PASSED,
                    evidence_keys=["result.txt"],
                )
            ],
            deliverables=[DeliverableWriterView("result", "result.txt", "text/plain")],
        )

    def dispatch_review(request: ReviewRequest) -> ReviewResultWriterView:
        events.append("review")
        return clean_review(request)

    outcome = run_workflow(
        planner_request(),
        repository_root=root,
        artifact_directory=root / "artifacts",
        dispatch_planner=dispatch_planner,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=unused_diagnosis,
        artifacts={"source": source},
    )
    return outcome, source


def field_names(value: object) -> set[str]:
    if attrs.has(type(value)):
        fields = cast("tuple[Attribute[object], ...]", attrs.fields(type(value)))
        names = {attribute.name for attribute in fields}
        return names | set().union(
            *(field_names(cast(object, getattr(value, name))) for name in names)
        )
    if isinstance(value, Mapping):
        mapping = cast("Mapping[str, object]", value)
        return set(mapping) | set().union(
            *(field_names(item) for item in mapping.values())
        )
    if isinstance(value, tuple | list):
        items = cast("tuple[object, ...] | list[object]", value)
        return set[str]().union(*(field_names(item) for item in items))
    return set()


def test_complete_thread_orders_real_callbacks_and_authors_contracts(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    contexts: list[Mapping[str, object]] = []

    (planner, branches, results), _ = run_complete(tmp_path, events, contexts)

    assert events == ["planner", "writer", "review"]
    assert planner.disposition is PlannerDisposition.COMPLETE
    assert planner.plan is not None
    assert planner.plan.plan_id == "workflow-request/plan"
    assert [curd.curd_id for curd in planner.plan.curds] == [
        "workflow-request/plan/curd/1"
    ]
    review_branch = branches[0]
    assert isinstance(review_branch, ReviewResult)
    assert review_branch.disposition is ReviewDisposition.CLEAN
    assert [row.target for row in review_branch.coverage] == [
        "workflow-request/plan/curd/1/criterion/1"
    ]
    assert [row.disposition.value for row in review_branch.coverage] == ["covered"]
    result = results[0]
    assert result.result_id == "workflow-request/plan/revision/1/result/1"
    assert result.disposition is CurdDisposition.PASSED
    assert result.runtime_refs == ("workflow-request/plan/revision/1/result/1/review",)
    assert result.source_plan_ref.digest == planner.plan.digest
    assert result.source_curd_ref.curd_id == planner.plan.curds[0].curd_id
    assert result.deliverables[0].digest == digest(b"verified workflow output\n")
    assert result.criterion_results[0].evidence[0].artifact == result.deliverables[0]


def test_writer_context_excludes_every_host_owned_field(tmp_path: Path) -> None:
    contexts: list[Mapping[str, object]] = []

    _ = run_complete(tmp_path, [], contexts)

    assert len(contexts) == 1
    assert field_names(contexts[0]).isdisjoint(HOST_ONLY_FIELDS)
    inputs = cast(Mapping[str, ResolvedAgentArtifact], contexts[0]["inputs"])
    assert Path(inputs["input-1"].path).read_bytes() == (
        b"approved workflow contract\n"
    )
    assert contexts[0]["criteria"] == (
        CriterionWriterView(
            "The workflow artifact is verified",
            "pytest tests/test_workflow.py",
        ),
    )


def test_complete_thread_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    first, _source = run_complete(tmp_path, [], [])
    second, _source = run_complete(tmp_path, [], [])

    assert first == second
    first_planner, first_branches, first_results = first
    assert first_planner.plan is not None
    assert first_planner.plan.digest.startswith("sha256:")
    first_review_branch = first_branches[0]
    assert isinstance(first_review_branch, ReviewResult)
    assert first_review_branch.review_id == (
        "workflow-request/plan/revision/1/result/1/review"
    )
    assert first_results[0].source_curd_ref.digest.startswith("sha256:")
    assert first_results[0].contract_version == version(CurdResult)


def test_partial_plan_runs_runnable_curd_and_diagnoses_failure(tmp_path: Path) -> None:
    source = source_artifact(tmp_path)
    finding = EvidenceRef(
        evidence_id="omitted-work",
        kind=EvidenceKind.REVIEW,
        artifact=source,
        summary="A later workflow curd remains unbounded",
    )
    events: list[str] = []

    def dispatch_planner(_request: PlannerRequest) -> PlannerResultWriterView:
        events.append("planner")
        return PlannerResultWriterView(
            disposition=PlannerDisposition.PARTIAL,
            plan=CurdPlanWriterView(
                objective="Implement the workflow contract seam",
                curds=[writer_curd()],
            ),
            unresolved_work=[
                PlannerUncertaintyWriterView(
                    description="The publication curd remains to be planned",
                    scope=UncertaintyScope.OMITTED_WORK,
                    evidence_keys=["finding"],
                )
            ],
        )

    def dispatch_writer(_context: Mapping[str, object]) -> CurdResultWriterView:
        events.append("writer")
        return CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(
                    CriterionDisposition.FAILED,
                    evidence_keys=["input-1"],
                )
            ],
            unresolved_work=["Repair the failed verification"],
        )

    def dispatch_review(_request: ReviewRequest) -> ReviewResultWriterView:
        raise AssertionError("review dispatch must not run for a failed curd")

    def dispatch_diagnosis(request: DiagnosisRequest) -> DiagnosisResultWriterView:
        events.append("diagnosis")
        subject_key = next(
            item.evidence_id
            for item in request.evidence
            if item.artifact.artifact_id == request.subject.artifact_id
        )
        return DiagnosisResultWriterView(
            disposition=DiagnosisDisposition.CONFIRMED,
            reproduction=ReproductionWriterView(
                ReproductionDisposition.REPRODUCED,
                ["Run the failed workflow verification"],
                "The workflow criterion failed",
                [subject_key],
            ),
            hypotheses=[],
            confirmed_cause=DiagnosisCauseWriterView(
                "The workflow output did not satisfy its criterion",
                [subject_key],
            ),
            regression_seam=SourceLocationWriterView("src/workflow.py", 1, 1),
        )

    planner, branches, results = run_workflow(
        planner_request(evidence=(finding,)),
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_planner=dispatch_planner,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis,
        artifacts={"source": source},
        evidence={"finding": finding},
    )

    assert events == ["planner", "writer", "diagnosis"]
    assert planner.disposition is PlannerDisposition.PARTIAL
    assert planner.unresolved_work[0].description == (
        "The publication curd remains to be planned"
    )
    diagnosis_branch = branches[0]
    assert isinstance(diagnosis_branch, DiagnosisResult)
    assert diagnosis_branch.disposition is DiagnosisDisposition.CONFIRMED
    assert diagnosis_branch.confirmed_cause is not None
    assert diagnosis_branch.confirmed_cause.summary == (
        "The workflow output did not satisfy its criterion"
    )
    assert diagnosis_branch.regression_seam is not None
    assert diagnosis_branch.regression_seam.path == "src/workflow.py"
    assert results[0].disposition is CurdDisposition.FAILED
    assert results[0].runtime_refs == (
        "workflow-request/plan/revision/1/result/1/diagnosis",
    )
    retained_source = results[0].criterion_results[0].evidence[0].artifact
    assert retained_source.digest == source.digest
    assert retained_source.uri != source.uri
    assert Path(retained_source.uri.removeprefix("file://")).is_file()


def test_multi_curd_branches_keep_subjects_and_evidence_isolated(
    tmp_path: Path,
) -> None:
    source = source_artifact(tmp_path)
    planner_view = complete_planner()
    assert planner_view.plan is not None
    first = writer_curd()
    second = attrs.evolve(
        first,
        key="second",
        outcome="Execute the second typed workflow curd",
        scope=BoundedScope(paths=["src/second-workflow.py"]),
        criteria=[
            CriterionWriterView(
                "The second workflow artifact is verified",
                "pytest tests/test_second_workflow.py",
            )
        ],
    )
    planner_view = attrs.evolve(
        planner_view,
        plan=attrs.evolve(planner_view.plan, curds=[first, second]),
    )
    events: list[str] = []
    diagnosis_requests: list[DiagnosisRequest] = []
    review_requests: list[ReviewRequest] = []

    def dispatch_writer(context: Mapping[str, object]) -> CurdResultWriterView:
        events.append(f"writer:{context['outcome']}")
        disposition = (
            CriterionDisposition.FAILED
            if context["outcome"] == first.outcome
            else CriterionDisposition.PASSED
        )
        return CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(
                    disposition,
                    evidence_keys=["input-1"],
                )
            ]
        )

    def dispatch_diagnosis(
        request: DiagnosisRequest,
    ) -> DiagnosisResultWriterView:
        events.append("diagnosis")
        diagnosis_requests.append(request)
        subject_key = next(
            item.evidence_id
            for item in request.evidence
            if item.artifact.artifact_id == request.subject.artifact_id
        )
        return DiagnosisResultWriterView(
            disposition=DiagnosisDisposition.CONFIRMED,
            reproduction=ReproductionWriterView(
                ReproductionDisposition.REPRODUCED,
                ["Run the failed workflow verification"],
                "The workflow criterion failed",
                [subject_key],
            ),
            hypotheses=[],
            confirmed_cause=DiagnosisCauseWriterView(
                "The workflow output did not satisfy its criterion",
                [subject_key],
            ),
            regression_seam=SourceLocationWriterView("src/workflow.py", 1, 1),
        )

    def dispatch_review(request: ReviewRequest) -> ReviewResultWriterView:
        events.append("review")
        review_requests.append(request)
        return ReviewResultWriterView(ReviewDisposition.CLEAN, [])

    planner, branches, results = run_workflow(
        planner_request(),
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_planner=lambda _request: planner_view,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis,
        artifacts={"source": source},
    )

    first_result_id = "workflow-request/plan/revision/1/result/1"
    second_result_id = "workflow-request/plan/revision/1/result/2"
    assert events == [
        "writer:Execute one typed workflow curd",
        "diagnosis",
        "writer:Execute the second typed workflow curd",
        "review",
    ]
    assert planner.plan is not None
    assert [curd.curd_id for curd in planner.plan.curds] == [
        "workflow-request/plan/curd/1",
        "workflow-request/plan/curd/2",
    ]
    assert [result.result_id for result in results] == [
        first_result_id,
        second_result_id,
    ]
    assert [result.source_curd_ref.curd_id for result in results] == [
        planner.plan.curds[0].curd_id,
        planner.plan.curds[1].curd_id,
    ]
    assert [result.disposition for result in results] == [
        CurdDisposition.FAILED,
        CurdDisposition.PASSED,
    ]
    first_branch, second_branch = branches
    assert isinstance(first_branch, DiagnosisResult)
    assert first_branch.diagnosis_id == f"{first_result_id}/diagnosis"
    assert isinstance(second_branch, ReviewResult)
    assert second_branch.review_id == f"{second_result_id}/review"
    first_evidence_ids = {item.evidence_id for item in diagnosis_requests[0].evidence}
    second_evidence_ids = {item.evidence_id for item in review_requests[0].evidence}
    assert first_evidence_ids == {
        "workflow-request/plan/curd/1/evidence/input-1",
        f"{first_result_id}/subject-evidence",
    }
    assert second_evidence_ids == {
        "workflow-request/plan/curd/2/evidence/input-1",
        f"{second_result_id}/subject-evidence",
    }
    assert first_evidence_ids.isdisjoint(second_evidence_ids)
    assert diagnosis_requests[0].subject.artifact_id == (f"{first_result_id}/subject")
    assert review_requests[0].subject.artifact_id == (f"{second_result_id}/subject")


def test_invalid_writer_host_field_is_rejected_before_branch_dispatch(
    tmp_path: Path,
) -> None:
    source = source_artifact(tmp_path)
    events: list[str] = []

    def dispatch_writer(_context: Mapping[str, object]):
        events.append("writer")
        return {
            "kind": "curd_result",
            "payload": {
                "result_id": "agent-authored-result",
                "criterion_results": [
                    {
                        "disposition": "passed",
                        "evidence_keys": ["input-1"],
                    }
                ],
                "deliverables": [],
                "unresolved_work": [],
            },
        }

    def branch_dispatch(_request: object) -> object:
        events.append("branch")
        raise AssertionError("invalid writer output must stop before a branch")

    planner, branches, results = run_workflow(
        planner_request(),
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_planner=lambda _request: complete_planner(),
        dispatch_writer=dispatch_writer,
        dispatch_review=branch_dispatch,
        dispatch_diagnosis=branch_dispatch,
        artifacts={"source": source},
    )

    assert planner.disposition is PlannerDisposition.COMPLETE
    assert branches == ()
    assert len(results) == 1
    assert results[0].disposition is CurdDisposition.BLOCKED
    assert len(results[0].criterion_results) == 1
    assert results[0].criterion_results[0].disposition is CriterionDisposition.BLOCKED
    reason = results[0].criterion_results[0].reason
    assert reason is not None
    assert "writer output invalid" in reason

    assert events == ["writer"]


@pytest.mark.parametrize("second_role", ["result", "report"])
def test_duplicate_deliverable_path_blocks_the_curd_result(
    tmp_path: Path,
    second_role: str,
) -> None:
    source = source_artifact(tmp_path)
    _ = (tmp_path / "result.txt").write_bytes(b"verified workflow output\n")
    branch_calls: list[str] = []

    def branch_dispatch(_request: object) -> object:
        branch_calls.append("branch")
        raise AssertionError("a duplicate deliverable must stop before a branch")

    def dispatch_writer(_context: Mapping[str, object]) -> CurdResultWriterView:
        return CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(
                    CriterionDisposition.PASSED,
                    evidence_keys=["result.txt"],
                )
            ],
            deliverables=[
                DeliverableWriterView("result", "result.txt", "text/plain"),
                DeliverableWriterView(second_role, "result.txt", "text/plain"),
            ],
        )

    _planner, branches, results = run_workflow(
        planner_request(),
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_planner=lambda _request: complete_planner(),
        dispatch_writer=dispatch_writer,
        dispatch_review=branch_dispatch,
        dispatch_diagnosis=branch_dispatch,
        artifacts={"source": source},
    )

    assert branch_calls == []
    assert branches == ()
    assert results[0].disposition is CurdDisposition.BLOCKED
    assert results[0].deliverables == ()
    assert results[0].criterion_results[0].reason == (
        "writer output invalid: ValueError: duplicate deliverable path: result.txt"
    )


def test_distinct_deliverable_paths_are_all_retained(tmp_path: Path) -> None:
    source = source_artifact(tmp_path)
    _ = (tmp_path / "result.txt").write_bytes(b"verified workflow output\n")
    _ = (tmp_path / "report.txt").write_bytes(b"verified workflow report\n")

    def dispatch_writer(_context: Mapping[str, object]) -> CurdResultWriterView:
        return CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(
                    CriterionDisposition.PASSED,
                    evidence_keys=["result.txt", "report.txt"],
                )
            ],
            deliverables=[
                DeliverableWriterView("result", "result.txt", "text/plain"),
                DeliverableWriterView("report", "report.txt", "text/plain"),
            ],
        )

    _planner, _branches, results = run_workflow(
        planner_request(),
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_planner=lambda _request: complete_planner(),
        dispatch_writer=dispatch_writer,
        dispatch_review=clean_review,
        dispatch_diagnosis=unused_diagnosis,
        artifacts={"source": source},
    )

    result_id = "workflow-request/plan/revision/1/result/1"
    assert results[0].disposition is CurdDisposition.PASSED
    assert [item.artifact_id for item in results[0].deliverables] == [
        f"{result_id}/artifact/1",
        f"{result_id}/artifact/2",
    ]
    assert [item.digest for item in results[0].deliverables] == [
        digest(b"verified workflow output\n"),
        digest(b"verified workflow report\n"),
    ]
    assert [item.evidence_id for item in results[0].criterion_results[0].evidence] == [
        f"{result_id}/evidence/1",
        f"{result_id}/evidence/2",
    ]


def test_wrong_writer_kind_is_rejected_without_review_or_diagnosis(
    tmp_path: Path,
) -> None:
    source = source_artifact(tmp_path)
    branch_calls: list[str] = []

    def branch_dispatch(_request: object) -> object:
        branch_calls.append("branch")
        raise AssertionError("wrong writer kind must stop before a branch")

    planner, branches, results = run_workflow(
        planner_request(),
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_planner=lambda _request: complete_planner(),
        dispatch_writer=lambda _context: AgentWriterView(
            WriterViewKind.REVIEW_RESULT,
            ReviewResultWriterView(ReviewDisposition.CLEAN, []),
        ),
        dispatch_review=branch_dispatch,
        dispatch_diagnosis=branch_dispatch,
        artifacts={"source": source},
    )

    assert planner.disposition is PlannerDisposition.COMPLETE
    assert branches == ()
    assert len(results) == 1
    assert results[0].disposition is CurdDisposition.BLOCKED
    assert results[0].criterion_results[0].disposition is CriterionDisposition.BLOCKED


@pytest.mark.parametrize(
    "disposition",
    [
        DiagnosisDisposition.INCONCLUSIVE,
        DiagnosisDisposition.NOT_REPRODUCED,
        DiagnosisDisposition.BLOCKED,
    ],
)
def test_cure_requires_confirmed_diagnosis_before_dispatch(
    tmp_path: Path,
    disposition: DiagnosisDisposition,
) -> None:
    source = source_artifact(tmp_path)
    planned = plan(
        planner_request(),
        lambda _request: complete_planner(),
        artifacts={"source": source},
    )
    assert planned.plan is not None
    curd = planned.plan.curds[0]
    source_evidence = EvidenceRef(
        evidence_id="diagnosis-source",
        kind=EvidenceKind.SOURCE,
        artifact=source,
        summary="Source-bound diagnosis evidence",
    )
    if disposition is DiagnosisDisposition.INCONCLUSIVE:
        reproduction = Reproduction(
            status=ReproductionDisposition.REPRODUCED,
            steps=["Run the workflow diagnosis"],
            observed="The workflow criterion failed",
            evidence=[source_evidence],
        )
        unresolved_evidence = (source_evidence,)
        reason = None
    elif disposition is DiagnosisDisposition.NOT_REPRODUCED:
        reproduction = Reproduction(
            status=ReproductionDisposition.NOT_REPRODUCED,
            steps=["Run the workflow diagnosis"],
            observed="The workflow criterion did not fail again",
            evidence=[source_evidence],
        )
        unresolved_evidence = ()
        reason = None
    else:
        reproduction = Reproduction(
            status=ReproductionDisposition.BLOCKED,
            steps=["Run the workflow diagnosis"],
            observed="The workflow diagnosis could not run",
            evidence=[source_evidence],
        )
        unresolved_evidence = ()
        reason = "The workflow diagnosis environment was unavailable"
    diagnosis = DiagnosisResult(
        contract_version=version(DiagnosisResult),
        diagnosis_id=f"diagnosis-{disposition.value}",
        disposition=disposition,
        symptom="The workflow criterion failed",
        reproduction=reproduction,
        hypotheses=[],
        unresolved_evidence=unresolved_evidence,
        reason=reason,
    )
    binding = bind_diagnosis(planned.plan, curd, diagnosis)
    events: list[str] = []

    def invoked(_value: object) -> object:
        events.append("invoked")
        raise AssertionError("unconfirmed Cure work must not run")

    with pytest.raises(
        ValueError, match="cure dispatch requires a confirmed diagnosis"
    ):
        _ = run_workflow(
            planner_request(),
            repository_root=tmp_path,
            artifact_directory=tmp_path / "artifacts",
            dispatch_planner=invoked,
            dispatch_writer=invoked,
            dispatch_review=invoked,
            dispatch_diagnosis=invoked,
            phase="cure",
            diagnosis_bindings=(binding,),
        )

    assert events == []


def test_cure_without_bindings_raises_before_any_dispatch(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    def invoked(_value: object) -> object:
        events.append("invoked")
        raise AssertionError("cure without bindings must not dispatch")

    with pytest.raises(ValueError, match="cure requires per-curd diagnosis bindings"):
        _ = run_workflow(
            planner_request(),
            repository_root=tmp_path,
            artifact_directory=tmp_path / "artifacts",
            dispatch_planner=invoked,
            dispatch_writer=invoked,
            dispatch_review=invoked,
            dispatch_diagnosis=invoked,
            phase="cure",
            diagnosis_bindings=None,
        )

    assert events == []


def test_cook_and_cure_reject_tampered_or_unsupported_plans_before_executor(
    tmp_path: Path,
) -> None:
    source = source_artifact(tmp_path)
    planned = plan(
        planner_request(),
        lambda _request: complete_planner(),
        artifacts={"source": source},
    )
    assert planned.plan is not None
    with pytest.raises(ValueError, match="CurdPlan digest mismatch"):
        _ = attrs.evolve(planned.plan, revision=planned.plan.revision + 1)
    unsupported = CurdPlan.signed(
        contract_version=attrs.evolve(planned.plan.contract_version, minor="99"),
        plan_id=planned.plan.plan_id,
        revision=planned.plan.revision + 1,
        objective=planned.plan.objective,
        curds=planned.plan.curds,
        context=planned.plan.context,
        parent_plan_ref=planned.plan.parent_plan_ref,
    )
    events: list[str] = []

    def invoked(_value: object) -> object:
        events.append("executor")
        raise AssertionError("invalid plans must not dispatch executors")

    with pytest.raises(ContractValidationError):
        _ = cook(
            unsupported,
            repository_root=tmp_path,
            artifact_directory=tmp_path / "artifacts",
            dispatch_writer=invoked,
            dispatch_review=invoked,
            dispatch_diagnosis=invoked,
        )
    with pytest.raises(ContractValidationError):
        _ = cure(
            unsupported,
            repository_root=tmp_path,
            artifact_directory=tmp_path / "artifacts",
            diagnosis_bindings={},
            dispatch_writer=invoked,
            dispatch_review=invoked,
            dispatch_diagnosis=invoked,
        )

    assert events == []


def test_plan_wide_shared_inputs_and_evidence_resolve_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = source_artifact(tmp_path)
    base = complete_planner()
    assert base.plan is not None
    first = writer_curd()
    second = attrs.evolve(
        first,
        key="second",
        outcome="Execute the second typed workflow curd",
        scope=BoundedScope(paths=["src/second-workflow.py"]),
        criteria=[
            CriterionWriterView(
                "The second workflow artifact is verified",
                "pytest tests/test_second_workflow.py",
            )
        ],
    )
    plan_view = attrs.evolve(
        base.plan,
        curds=[first, second],
        context=BoundedContextWriterView(
            shared_input_keys=["source"],
            constraints=["Use the source"],
            invariants=["The source remains immutable"],
        ),
    )
    planner_view = attrs.evolve(base, plan=plan_view)
    calls: list[str] = []
    original_resolve = resolve_artifact

    def tracking_resolve(
        artifact: ArtifactRef,
        *,
        repository_root: str | Path = ".",
        artifact_directory: str | Path,
    ) -> ResolvedAgentArtifact:
        calls.append(artifact.uri)
        return original_resolve(
            artifact,
            repository_root=repository_root,
            artifact_directory=artifact_directory,
        )

    monkeypatch.setattr(workflow_module, "resolve_artifact", tracking_resolve)
    contexts: list[Mapping[str, object]] = []

    def writer(context: Mapping[str, object]) -> CurdResultWriterView:
        contexts.append(context)
        return CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(
                    CriterionDisposition.PASSED,
                    evidence_keys=["input-1"],
                )
            ]
        )

    _ = run_workflow(
        planner_request(),
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_planner=lambda _request: planner_view,
        dispatch_writer=writer,
        dispatch_review=clean_review,
        dispatch_diagnosis=unused_diagnosis,
        artifacts={"source": source},
        evidence={
            "source-evidence": EvidenceRef(
                evidence_id="source-evidence",
                kind=EvidenceKind.SOURCE,
                artifact=source,
            )
        },
    )

    assert len(contexts) == 2
    assert calls.count(source.uri) == 4
    assert contexts[0]["shared_inputs"] == contexts[1]["shared_inputs"]
    assert contexts[0]["evidence_inputs"] == contexts[1]["evidence_inputs"]


def overrun_curd() -> SemanticCurdWriterView:
    """A two-criterion curd so a checkpoint can leave real work unfinished."""

    base = writer_curd()
    return attrs.evolve(
        base,
        criteria=[
            base.criteria[0],
            CriterionWriterView(
                description="The second repair is verified",
                check="pytest tests/test_workflow.py::test_second_repair",
            ),
        ],
    )


def overrun_planner(_request: PlannerRequest) -> PlannerResultWriterView:
    return PlannerResultWriterView(
        disposition=PlannerDisposition.COMPLETE,
        plan=CurdPlanWriterView(
            objective="Implement the workflow contract seam",
            curds=[overrun_curd()],
        ),
    )


def run_overrun(
    root: Path,
    events: list[str],
    checkpoint: WriterCheckpoint,
) -> tuple[tuple[ReviewResult | DiagnosisResult, ...], tuple[CurdResult, ...]]:
    source = source_artifact(root)

    def dispatch_planner(request: PlannerRequest) -> PlannerResultWriterView:
        events.append("planner")
        return overrun_planner(request)

    def dispatch_writer(_context: Mapping[str, object]) -> CurdResultWriterView:
        events.append("writer")
        raise WriterBudgetExceeded(checkpoint)

    def dispatch_review(_request: ReviewRequest) -> ReviewResultWriterView:
        raise AssertionError("review dispatch must not run for a budget overrun")

    def dispatch_diagnosis(_request: DiagnosisRequest) -> DiagnosisResultWriterView:
        raise AssertionError("diagnosis dispatch must not run for a budget overrun")

    _planner, branches, results = run_workflow(
        planner_request(),
        repository_root=root,
        artifact_directory=root / "artifacts",
        dispatch_planner=dispatch_planner,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis,
        artifacts={"source": source},
    )
    return branches, results


def test_budget_overrun_retains_completed_repairs_and_next_action(
    tmp_path: Path,
) -> None:
    payload = b"first repair landed\n"
    _ = (tmp_path / "repair.txt").write_bytes(payload)
    events: list[str] = []

    branches, results = run_overrun(
        tmp_path,
        events,
        WriterCheckpoint(
            reason="context budget reached after the first repair",
            completed=[
                CriterionResultWriterView(
                    CriterionDisposition.PASSED,
                    evidence_keys=["repair.txt"],
                )
            ],
            deliverables=[DeliverableWriterView("repair", "repair.txt", "text/plain")],
            remaining=["Apply the second repair in src/workflow.py"],
        ),
    )

    assert events == ["planner", "writer"]
    assert branches == ()
    result = results[0]
    assert result.disposition is CurdDisposition.BLOCKED

    first, second = result.criterion_results
    assert first.disposition is CriterionDisposition.PASSED
    assert first.criterion_id == result.expected_criterion_ids[0]
    assert first.evidence[0].artifact.digest == digest(payload)
    assert second.disposition is CriterionDisposition.BLOCKED
    assert second.criterion_id == result.expected_criterion_ids[1]
    assert second.reason == (
        "writer stopped at its budget: WriterBudgetExceeded: "
        + "context budget reached after the first repair"
    )

    assert [item.role for item in result.deliverables] == ["repair"]
    assert result.deliverables[0].digest == digest(payload)
    assert result.unresolved_work == (
        second.reason,
        "Apply the second repair in src/workflow.py",
    )


def test_budget_overrun_without_progress_still_hands_back_next_action(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    branches, results = run_overrun(
        tmp_path,
        events,
        WriterCheckpoint(
            reason="tool budget reached before any repair",
            remaining=["Start with the first repair in src/workflow.py"],
        ),
    )

    assert events == ["planner", "writer"]
    assert branches == ()
    result = results[0]
    assert result.disposition is CurdDisposition.BLOCKED
    assert [row.disposition for row in result.criterion_results] == [
        CriterionDisposition.BLOCKED,
        CriterionDisposition.BLOCKED,
    ]
    assert result.deliverables == ()
    assert result.unresolved_work == (
        "writer stopped at its budget: WriterBudgetExceeded: "
        + "tool budget reached before any repair",
        "Start with the first repair in src/workflow.py",
    )


def test_full_coverage_budget_checkpoint_is_rejected_without_review(
    tmp_path: Path,
) -> None:
    payload = b"first repair landed\n"
    _ = (tmp_path / "repair.txt").write_bytes(payload)
    events: list[str] = []
    passed = CriterionResultWriterView(
        CriterionDisposition.PASSED,
        evidence_keys=["repair.txt"],
    )

    branches, results = run_overrun(
        tmp_path,
        events,
        WriterCheckpoint(
            reason="budget reached",
            completed=[passed, passed],
            deliverables=[DeliverableWriterView("repair", "repair.txt", "text/plain")],
        ),
    )

    assert events == ["planner", "writer"]
    assert branches == ()
    result = results[0]
    assert result.disposition is CurdDisposition.BLOCKED
    assert [item.role for item in result.deliverables] == ["repair"]
    assert result.deliverables[0].digest == digest(payload)
    assert result.unresolved_work == (
        "budget checkpoint invalid: ValueError: budget checkpoint must leave at "
        + "least one criterion unfinished, not 2 of 2 "
        + "<- WriterBudgetExceeded: budget reached",
    )


def test_invalid_budget_checkpoint_with_an_unreadable_deliverable_stays_blocked(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    passed = CriterionResultWriterView(
        CriterionDisposition.PASSED,
        evidence_keys=["missing.txt"],
    )

    branches, results = run_overrun(
        tmp_path,
        events,
        WriterCheckpoint(
            reason="budget reached",
            completed=[passed, passed],
            deliverables=[DeliverableWriterView("repair", "missing.txt", "text/plain")],
        ),
    )

    assert events == ["planner", "writer"]
    assert branches == ()
    result = results[0]
    assert result.disposition is CurdDisposition.BLOCKED
    assert result.deliverables == ()
    assert len(result.unresolved_work) == 1
    assert result.unresolved_work[0].startswith(
        "budget checkpoint invalid: ValueError: budget checkpoint must leave at "
        + "least one criterion unfinished, not 2 of 2 "
        + "<- WriterBudgetExceeded: budget reached; deliverable salvage failed: "
    )
    assert "missing.txt" in result.unresolved_work[0]


def test_budget_checkpoint_with_an_unfinished_completed_entry_is_rejected(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    branches, results = run_overrun(
        tmp_path,
        events,
        WriterCheckpoint(
            reason="budget reached",
            completed=[
                CriterionResultWriterView(
                    CriterionDisposition.SKIPPED,
                    reason="not attempted yet",
                )
            ],
            remaining=["Apply the first repair"],
        ),
    )

    assert events == ["planner", "writer"]
    assert branches == ()
    result = results[0]
    assert result.disposition is CurdDisposition.BLOCKED
    assert result.deliverables == ()
    assert result.unresolved_work == (
        "budget checkpoint invalid: ValueError: budget checkpoint completed[1] "
        + "must be finished (passed or failed), not skipped "
        + "<- WriterBudgetExceeded: budget reached",
    )


def test_writer_checkpoint_rejects_duplicate_remaining_work() -> None:
    with pytest.raises(ValueError, match="remaining must not contain duplicate"):
        _ = WriterCheckpoint(
            reason="budget reached",
            remaining=["first step", "second step", "first step"],
        )


def test_writer_checkpoint_rejects_a_bare_string_remaining() -> None:
    with pytest.raises(TypeError):
        _ = WriterCheckpoint(reason="budget reached", remaining="Apply the fix")  # pyright: ignore[reportArgumentType]


def test_writer_checkpoint_rejects_a_non_criterion_result_in_completed() -> None:
    with pytest.raises(ValueError, match="completed"):
        _ = WriterCheckpoint(reason="budget reached", completed=["junk"])  # pyright: ignore[reportArgumentType]


def test_writer_checkpoint_rejects_a_non_deliverable_view_in_deliverables() -> None:
    with pytest.raises(ValueError, match="deliverables"):
        _ = WriterCheckpoint(reason="budget reached", deliverables=[42])  # pyright: ignore[reportArgumentType]


def test_writer_checkpoint_rejects_an_empty_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        _ = WriterCheckpoint(reason="")


def test_budget_overrun_is_reported_apart_from_a_plain_writer_failure(
    tmp_path: Path,
) -> None:
    source = source_artifact(tmp_path)

    def dispatch_writer(_context: Mapping[str, object]) -> CurdResultWriterView:
        raise RuntimeError("context budget reached after the first repair")

    _planner, branches, results = run_workflow(
        planner_request(),
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_planner=overrun_planner,
        dispatch_writer=dispatch_writer,
        dispatch_review=clean_review,
        dispatch_diagnosis=unused_diagnosis,
        artifacts={"source": source},
    )

    assert branches == ()
    assert results[0].unresolved_work == (
        "writer callback failed: RuntimeError: "
        + "context budget reached after the first repair",
    )
