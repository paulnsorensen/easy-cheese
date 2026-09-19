"""Cook-only, Age, and Cure adapters for accepted fan handoffs."""
# This package adapter composes internal workflow phase primitives.
# pyright: reportPrivateUsage=false
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs

from easy_cheese_schemas import (
    ArtifactRef,
    BoundedScope,
    CurdPlan,
    CurdResult,
    CurdResultWriterView,
    canonical_bytes,
    DiagnosisDisposition,
    DiagnosisRequest,
    EvidenceKind,
    EvidenceRef,
    RemediationCureObservation,
    RemediationScopeKey,
    ReviewRequest,
    ReviewResult,
    SemanticCurd,
    WriterViewKind,
    supported_version_for,
)
from easy_cheese.shared import workflow
from easy_cheese.shared.fanout.run_fan import FanContext, FanExecutionOutcome, run_fan
from easy_cheese.shared.fanout.remediation import finding_key
from easy_cheese.shared.publication import atomic_write


@attrs.define
class _ScopeExecution:
    curd: SemanticCurd
    index: int
    writer: workflow.CurdWriterExecution
    writer_view: CurdResultWriterView
    result: CurdResult
    subject: ArtifactRef
    latest_review: ReviewResult | None = None


@attrs.define
class _PostmergeExecution:
    curd: SemanticCurd
    writer: workflow.CurdWriterExecution
    latest_review: ReviewResult | None = None


def execute_fan(
    plan: CurdPlan,
    *,
    repository_root: str | Path,
    artifact_directory: str | Path,
    dispatch_writer: workflow.WriterDispatch,
    dispatch_review: workflow.ReviewDispatch,
    dispatch_diagnosis: workflow.DiagnosisDispatch,
    evidence: Mapping[str, EvidenceRef] | None,
    selected: Sequence[str],
    execution_id: str | None = None,
    dispatch_press: workflow.PressDispatch | None = None,
) -> FanExecutionOutcome:
    """Run selected curds through the fan state machine with real phase seams."""

    root = Path(repository_root)
    artifacts = Path(artifact_directory)
    indexed = {curd.curd_id: index for index, curd in enumerate(plan.curds, start=1)}
    shared_inputs, resolved_evidence, durable_evidence = workflow._resolve_plan_context(
        plan,
        repository_root=root,
        artifact_directory=artifacts,
        evidence={} if evidence is None else evidence,
    )
    scopes: dict[str, _ScopeExecution] = {}
    postmerge: _PostmergeExecution | None = None
    latest_postmerge_gate_evidence: list[EvidenceRef] = []
    postmerge_gate_evidence: list[EvidenceRef] = []

    def cook_adapter(curd: SemanticCurd) -> CurdResult:
        try:
            writer = workflow.execute_curd_writer(
                plan,
                curd,
                indexed[curd.curd_id],
                repository_root=root,
                artifact_directory=artifacts,
                resolved_evidence=resolved_evidence,
                durable_evidence=durable_evidence,
                shared_inputs=shared_inputs,
                phase="cook",
                provenance_refs=(),
                dispatch_writer=dispatch_writer,
            )
        except Exception as error:
            return workflow._blocked_result(
                plan, curd, indexed[curd.curd_id],
                workflow._failure_reason("fan Cook writer failed", error),
                provenance_refs=(),
            )
        subject_evidence = _subject_evidence(writer)
        writer.host_evidence[subject_evidence.evidence_id] = subject_evidence
        scopes[curd.curd_id] = _ScopeExecution(
            curd=curd,
            index=indexed[curd.curd_id],
            writer=writer,
            writer_view=writer.writer_view,
            result=writer.result,
            subject=writer.subject,
        )
        return writer.result

    def press_adapter(
        scope: RemediationScopeKey, gate_round: int
    ) -> tuple[EvidenceRef, ...]:
        if dispatch_press is None:
            raise RuntimeError("postmerge Press dispatcher is required")
        values = tuple(dispatch_press(scope, gate_round))
        if scope.scope_id == "postmerge":
            latest_postmerge_gate_evidence[:] = values
            known = {item.evidence_id for item in postmerge_gate_evidence}
            postmerge_gate_evidence.extend(
                item for item in values if item.evidence_id not in known
            )
        return values

    def age_adapter(scope: RemediationScopeKey, review_round: int) -> ReviewResult:
        nonlocal postmerge
        if scope.scope_id == "postmerge":
            if postmerge is None:
                subject, evidence_values = _aggregate_subject(plan, scopes, artifacts)
            else:
                subject = postmerge.writer.subject
                evidence_values = workflow._evidence_values(postmerge.writer.host_evidence)
            evidence_values = workflow._evidence_values(
                {item.evidence_id: item for item in (*evidence_values, *latest_postmerge_gate_evidence)}
            )
            request = ReviewRequest(
                contract_version=workflow._version(ReviewRequest),
                review_id=f"{plan.plan_id}/revision/{plan.revision}/postmerge/review/{review_round}",
                subject=subject,
                coverage_targets=[
                    criterion.criterion_id
                    for curd in plan.curds
                    for criterion in curd.criteria
                ],
                evidence=evidence_values,
            )
            review = workflow._review(
                request,
                dispatch_review(request),
                {item.evidence_id: item for item in request.evidence},
            )
            aggregate = _aggregate_curd(plan, scopes)
            postmerge = _PostmergeExecution(
                curd=aggregate,
                writer=workflow.CurdWriterExecution(
                    plan=plan,
                    writer_view=workflow._blocked_writer_view(aggregate, "postmerge review pending"),
                    host_evidence={item.evidence_id: item for item in request.evidence},
                    deliverables={},
                    subject=subject,
                    result=next(iter(scopes.values())).result,
                ),
                latest_review=review,
            )
            return review
        state = scopes.get(scope.scope_id)
        if state is None:
            raise RuntimeError(f"Age requested before Cook for {scope.scope_id}")
        request = ReviewRequest(
            contract_version=workflow._version(ReviewRequest),
            review_id=(
                f"{plan.plan_id}/revision/{plan.revision}/result/"
                f"{state.index}/review/{review_round}"
            ),
            subject=state.subject,
            coverage_targets=[item.criterion_id for item in state.curd.criteria],
            evidence=workflow._evidence_values(state.writer.host_evidence),
        )
        review = workflow._review(
            request,
            dispatch_review(request),
            {item.evidence_id: item for item in request.evidence},
        )
        state.writer_view = workflow._reviewed_result_view(
            state.writer_view, review
        )
        state.result, state.subject = _refresh_result(state, review, artifacts)
        subject_evidence = EvidenceRef(
            evidence_id=f"{state.result.result_id}/subject-evidence",
            kind=EvidenceKind.RUNTIME,
            artifact=state.subject,
        )
        state.writer.host_evidence[subject_evidence.evidence_id] = subject_evidence
        state.latest_review = review
        for finding in review.findings:
            for item in finding.evidence:
                state.writer.host_evidence[item.evidence_id] = item
        return review

    def cure_adapter(
        scope: RemediationScopeKey,
        locked_selection: tuple[str, ...],
        cure_round: int,
    ) -> RemediationCureObservation:
        nonlocal postmerge
        if scope.scope_id == "postmerge":
            if postmerge is None or postmerge.latest_review is None:
                raise RuntimeError("Cure requested before postmerge Age")
            subject = postmerge.writer.subject
            request = DiagnosisRequest(
                contract_version=workflow._version(DiagnosisRequest),
                diagnosis_id=f"{plan.plan_id}/revision/{plan.revision}/postmerge/diagnosis/{cure_round}",
                symptom="Postmerge findings require cure: " + "; ".join(
                    f"{finding.finding_id}: {finding.summary}"
                    for finding in postmerge.latest_review.findings
                    if finding_key(finding) in locked_selection
                ),
                subject=subject,
                evidence=workflow._evidence_values(postmerge.writer.host_evidence),
            )
            diagnosis = workflow._diagnosis(
                request,
                dispatch_diagnosis(request),
                {item.evidence_id: item for item in request.evidence},
            )
            if diagnosis.disposition is not DiagnosisDisposition.CONFIRMED:
                return _cure_observation((), locked_selection)
            writer = workflow.execute_curd_writer(
                plan,
                postmerge.curd,
                1,
                repository_root=root,
                artifact_directory=artifacts,
                resolved_evidence=resolved_evidence,
                durable_evidence=durable_evidence,
                shared_inputs=shared_inputs,
                phase="cure",
                provenance_refs=(diagnosis.diagnosis_id,),
                dispatch_writer=dispatch_writer,
                extra_context={
                    "aggregate_subject": subject,
                    "locked_selection": locked_selection,
                    "normalized_review": postmerge.latest_review,
                    "plan_results": tuple(state.result for state in scopes.values()),
                    "confirmed_diagnosis": diagnosis,
                },
                result_id=f"{plan.plan_id}/revision/{plan.revision}/postmerge-result",
            )
            postmerge.writer = writer
            succeeded = writer.result.disposition.value == "passed"
            return _cure_observation(
                locked_selection if succeeded else (),
                () if succeeded else locked_selection,
                touched_paths=tuple(writer.deliverables),
                gate_evidence=tuple(
                    {
                        item.evidence_id: item
                        for item in (
                            *postmerge_gate_evidence,
                            *writer.host_evidence.values(),
                        )
                    }.values()
                ),
            )
        state = scopes.get(scope.scope_id)
        if state is None:
            raise RuntimeError(f"Cure requested before Cook for {scope.scope_id}")
        request = DiagnosisRequest(
            contract_version=workflow._version(DiagnosisRequest),
            diagnosis_id=(
                f"{plan.plan_id}/revision/{plan.revision}/result/"
                f"{state.index}/diagnosis/{cure_round}"
            ),
            symptom="Review findings require cure: " + "; ".join(
                f"{finding.finding_id}: {finding.summary}"
                for finding in (state.latest_review.findings if state.latest_review else ())
                if finding_key(finding) in locked_selection
            ),
            subject=state.subject,
            evidence=workflow._evidence_values(state.writer.host_evidence),
        )
        diagnosis = workflow._diagnosis(
            request,
            dispatch_diagnosis(request),
            {item.evidence_id: item for item in request.evidence},
        )
        if diagnosis.disposition is not DiagnosisDisposition.CONFIRMED:
            return _cure_observation((), locked_selection)
        binding = workflow.bind_diagnosis(plan, state.curd, diagnosis)
        writer = workflow.execute_curd_writer(
            plan,
            state.curd,
            state.index,
            repository_root=root,
            artifact_directory=artifacts,
            resolved_evidence=resolved_evidence,
            durable_evidence=durable_evidence,
            shared_inputs=shared_inputs,
            phase="cure",
            provenance_refs=(binding.diagnosis.diagnosis_id,),
            dispatch_writer=dispatch_writer,
        )
        state.writer = writer
        state.writer_view = writer.writer_view
        state.result = writer.result
        state.subject = writer.subject
        subject_evidence = _subject_evidence(writer)
        writer.host_evidence[subject_evidence.evidence_id] = subject_evidence
        succeeded = writer.result.disposition.value == "passed"
        applied = locked_selection if succeeded else ()
        deferred = () if succeeded else locked_selection
        return _cure_observation(
            applied,
            deferred,
            touched_paths=tuple(writer.deliverables),
            gate_evidence=tuple(writer.host_evidence.values()),
        )

    context = FanContext(
        run_id=execution_id or f"{plan.plan_id}-execution",
        artifact_directory=artifacts,
        cook=cook_adapter,
        age=age_adapter,
        cure=cure_adapter,
        press=press_adapter if dispatch_press is not None else None,
    )
    return run_fan(plan, context, selected=selected)


def _aggregate_subject(
    plan: CurdPlan, scopes: Mapping[str, _ScopeExecution], artifact_directory: Path
) -> tuple[ArtifactRef, tuple[EvidenceRef, ...]]:
    payload = {
        "plan_id": plan.plan_id,
        "revision": plan.revision,
        "results": [state.result for state in scopes.values()],
    }
    raw = canonical_bytes(payload)
    path = artifact_directory / "remediation" / plan.plan_id / "postmerge-subject.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, raw)
    subject = ArtifactRef(
        artifact_id=f"{plan.plan_id}/postmerge-subject",
        role="subject",
        uri=path.resolve().as_uri(),
        digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        size_bytes=len(raw),
        media_type="application/json",
    )
    return subject, (
        EvidenceRef(
            evidence_id=f"{subject.artifact_id}/evidence",
            kind=EvidenceKind.RUNTIME,
            artifact=subject,
        ),
    )




def _aggregate_curd(plan: CurdPlan, scopes: Mapping[str, _ScopeExecution]) -> SemanticCurd:
    first = next(iter(scopes.values())).curd
    criteria = tuple(item for state in scopes.values() for item in state.curd.criteria)
    paths = tuple(sorted({path for state in scopes.values() for path in state.curd.scope.paths}))
    excluded = tuple(
        sorted(
            {
                path
                for state in scopes.values()
                for path in state.curd.scope.excluded_paths
            }
            - set(paths)
        )
    )
    return attrs.evolve(
        first,
        curd_id="postmerge",
        outcome=f"Apply aggregate remediation for {plan.plan_id}",
        scope=BoundedScope(paths=paths, excluded_paths=excluded),
        inputs=(),
        outputs=("postmerge-result",),
        dependencies=(),
        criteria=criteria,
    )


def _subject_evidence(writer: workflow.CurdWriterExecution) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=f"{writer.result.result_id}/subject-evidence",
        kind=EvidenceKind.RUNTIME,
        artifact=writer.subject,
    )


def _refresh_result(
    state: _ScopeExecution, review: ReviewResult, artifact_directory: Path
) -> tuple[CurdResult, ArtifactRef]:
    invocation = workflow._result_invocation(
        state.writer.plan,
        state.curd,
        state.index,
        evidence=state.writer.host_evidence,
        deliverables=state.writer.deliverables,
        provenance_refs=(review.review_id,),
    )
    canonical = workflow._normalize(
        state.writer_view, WriterViewKind.CURD_RESULT, invocation
    )
    assert isinstance(canonical.value, CurdResult)
    subject = workflow._subject_artifact(
        canonical.value.result_id,
        canonical,
        artifact_directory,
    )
    return canonical.value, subject


def _cure_observation(
    applied: tuple[str, ...],
    deferred: tuple[str, ...],
    *,
    touched_paths: tuple[str, ...] = (),
    gate_evidence: tuple[EvidenceRef, ...] = (),
) -> RemediationCureObservation:
    version = supported_version_for(RemediationCureObservation)
    if version is None:
        raise RuntimeError("remediation cure observation has no supported version")
    return RemediationCureObservation(
        contract_version=version,
        applied_finding_keys=applied,
        deferred_finding_keys=deferred,
        touched_paths=touched_paths,
        gate_evidence=gate_evidence,
        new_gate_failures=(),
    )