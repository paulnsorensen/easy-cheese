from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

import attrs
import pytest

import easy_cheese_schemas.workflow as workflow_module
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
    ReviewResultWriterView,
    SemanticCurdWriterView,
    SourceLocationWriterView,
    UncertaintyScope,
    WriterViewKind,
)
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    curd_plan_digest,
    supported_version_for,
)
from easy_cheese_schemas.workflow import (
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
    (root / "spec.md").write_bytes(payload)
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

    result = workflow_module._review(request, output, {})

    expected_disposition = (
        CoverageDisposition.COVERED
        if disposition is ReviewDisposition.CLEAN
        else CoverageDisposition.NOT_COVERED
    )
    expected_reason = (
        None
        if expected_disposition is CoverageDisposition.COVERED
        else reason
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
        (root / "result.txt").write_bytes(payload)
        return CurdResultWriterView(
            criterion_results=[
                CriterionResultWriterView(
                    CriterionDisposition.PASSED,
                    evidence_keys=["result.txt"],
                )
            ],
            deliverables=[
                DeliverableWriterView("result", "result.txt", "text/plain")
            ],
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
        names = {attribute.name for attribute in attrs.fields(type(value))}
        return names | set().union(
            *(field_names(getattr(value, name)) for name in names)
        )
    if isinstance(value, Mapping):
        return set(value) | set().union(*(field_names(item) for item in value.values()))
    if isinstance(value, tuple | list):
        return set().union(*(field_names(item) for item in value))
    return set()


def test_complete_thread_orders_real_callbacks_and_authors_contracts(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    contexts: list[Mapping[str, object]] = []

    (planner, branches, results), _source = run_complete(tmp_path, events, contexts)

    assert events == ["planner", "writer", "review"]
    assert planner.disposition is PlannerDisposition.COMPLETE
    assert planner.plan is not None
    assert planner.plan.plan_id == "workflow-request/plan"
    assert [curd.curd_id for curd in planner.plan.curds] == [
        "workflow-request/plan/curd/1"
    ]
    assert branches[0].disposition is ReviewDisposition.CLEAN
    assert [row.target for row in branches[0].coverage] == [
        "workflow-request/plan/curd/1/criterion/1"
    ]
    assert [row.disposition.value for row in branches[0].coverage] == ["covered"]
    result = results[0]
    assert result.result_id == "workflow-request/plan/revision/1/result/1"
    assert result.disposition is CurdDisposition.PASSED
    assert result.runtime_refs == (
        "workflow-request/plan/revision/1/result/1/review",
    )
    assert result.source_plan_ref.digest == planner.plan.digest
    assert result.source_curd_ref.curd_id == planner.plan.curds[0].curd_id
    assert result.deliverables[0].digest == digest(b"verified workflow output\n")
    assert result.criterion_results[0].evidence[0].artifact == result.deliverables[0]


def test_writer_context_excludes_every_host_owned_field(tmp_path: Path) -> None:
    contexts: list[Mapping[str, object]] = []

    run_complete(tmp_path, [], contexts)

    assert len(contexts) == 1
    assert field_names(contexts[0]).isdisjoint(HOST_ONLY_FIELDS)
    assert Path(contexts[0]["inputs"]["input-1"].path).read_bytes() == (
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
    assert first_branches[0].review_id == (
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
            regression_seam=SourceLocationWriterView(
                "src/workflow.py", 1, 1
            ),
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
    assert branches[0].disposition is DiagnosisDisposition.CONFIRMED
    assert branches[0].confirmed_cause is not None
    assert branches[0].confirmed_cause.summary == (
        "The workflow output did not satisfy its criterion"
    )
    assert branches[0].regression_seam is not None
    assert branches[0].regression_seam.path == "src/workflow.py"
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
    assert [branch.diagnosis_id for branch in branches[:1]] == [
        f"{first_result_id}/diagnosis"
    ]
    assert [branch.review_id for branch in branches[1:]] == [
        f"{second_result_id}/review"
    ]
    first_evidence_ids = {
        item.evidence_id for item in diagnosis_requests[0].evidence
    }
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
    assert diagnosis_requests[0].subject.artifact_id == (
        f"{first_result_id}/subject"
    )
    assert review_requests[0].subject.artifact_id == (
        f"{second_result_id}/subject"
    )

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

    def branch_dispatch(_request):
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
    assert "writer output invalid" in results[0].criterion_results[0].reason

    assert events == ["writer"]


def test_wrong_writer_kind_is_rejected_without_review_or_diagnosis(
    tmp_path: Path,
) -> None:
    source = source_artifact(tmp_path)
    branches: list[str] = []

    def branch_dispatch(_request):
        branches.append("branch")
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

    def invoked(_value):
        events.append("invoked")
        raise AssertionError("unconfirmed Cure work must not run")

    with pytest.raises(
        ValueError, match="cure dispatch requires a confirmed diagnosis"
    ):
        run_workflow(
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


def test_cook_and_cure_reject_stale_or_unsupported_plans_before_executor(
    tmp_path: Path,
) -> None:
    source = source_artifact(tmp_path)
    planned = plan(
        planner_request(),
        lambda _request: complete_planner(),
        artifacts={"source": source},
    )
    assert planned.plan is not None
    stale = attrs.evolve(planned.plan, revision=planned.plan.revision + 1)
    future_version = attrs.evolve(stale.contract_version, minor="99")
    unsigned_future = attrs.evolve(stale, contract_version=future_version)
    unsupported = attrs.evolve(
        unsigned_future,
        digest=curd_plan_digest(unsigned_future),
    )
    events: list[str] = []

    def invoked(_value):
        events.append("executor")
        raise AssertionError("invalid plans must not dispatch executors")

    for invalid in (stale, unsupported):
        with pytest.raises(ContractValidationError):
            cook(
                invalid,
                repository_root=tmp_path,
                artifact_directory=tmp_path / "artifacts",
                dispatch_writer=invoked,
                dispatch_review=invoked,
                dispatch_diagnosis=invoked,
            )
        with pytest.raises(ContractValidationError):
            cure(
                invalid,
                repository_root=tmp_path,
                artifact_directory=tmp_path / "artifacts",
                diagnosis_bindings={},
                dispatch_writer=invoked,
                dispatch_review=invoked,
                dispatch_diagnosis=invoked,
            )

    assert events == []


def test_plan_wide_shared_inputs_and_evidence_resolve_once(
    tmp_path: Path, monkeypatch
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
    original_resolve = workflow_module.resolve_artifact

    def tracking_resolve(artifact, **kwargs):
        calls.append(artifact.uri)
        return original_resolve(artifact, **kwargs)

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

    run_workflow(
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
