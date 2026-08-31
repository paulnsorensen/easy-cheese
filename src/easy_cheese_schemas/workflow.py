from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Literal, TypeVar, cast
from urllib.parse import quote, urlsplit

import attrs
from attrs import Attribute
from .artifacts import (
    MAX_ARTIFACT_BYTES,
    read_repository_artifact,
    resolve_verified_bytes,
    resolve_artifact,
)
from .contracts import (
    AgentWriterView,
    ArtifactRef,
    ContractVersion,
    CoverageDisposition,
    CriterionDisposition,
    CriterionResultWriterView,
    CriterionWriterView,
    CurdPlan,
    CurdResult,
    CurdResultWriterView,
    DeliverableWriterView,
    DiagnosisDisposition,
    DiagnosisRequest,
    DiagnosisResult,
    DiagnosisResultWriterView,
    EvidenceKind,
    EvidenceRef,
    IdentityAction,
    IdentityLineage,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    PlannerResultWriterView,
    ReproductionDisposition,
    ReproductionWriterView,
    ReviewCoverage,
    ReviewDisposition,
    ReviewRequest,
    ReviewResult,
    ReviewResultWriterView,
    SemanticCurd,
    SourceCurdRef,
    SourcePlanRef,
    WriterViewKind,
)
from .planner import materialize_planner_result
from .schema_runtime import (
    CanonicalArtifact,
    ContractValidationError,
    curd_plan_digest,
    normalize_agent_output,
    supported_version_for,
    validate_curd_plan,
)

PlannerDispatch = Callable[[PlannerRequest], object]
WriterDispatch = Callable[[Mapping[str, object]], object]
ReviewDispatch = Callable[[ReviewRequest], object]
DiagnosisDispatch = Callable[[DiagnosisRequest], object]
BranchResult = ReviewResult | DiagnosisResult
ExecutionResults = tuple[tuple[BranchResult, ...], tuple[CurdResult, ...]]
WorkflowResults = tuple[PlannerResult, tuple[BranchResult, ...], tuple[CurdResult, ...]]


_ItemT = TypeVar("_ItemT")


def _tuple_sequence(value: Sequence[_ItemT]) -> tuple[_ItemT, ...]:
    return tuple(value)


@attrs.define(frozen=True)
class WriterCheckpoint:
    """Progress a writer completed before it stopped at its own budget.

    A coder that runs out of context or tool calls mid-curd holds work the host
    cannot see: criteria it already verified, files it already wrote, and the
    exact next action. Without this the host only sees the raised exception and
    the whole curd is blocked, so a redispatch repeats repairs that already
    landed.
    """

    # Why the writer stopped: the budget it hit, plus any environment blocker.
    reason: str = attrs.field()
    # Criteria the writer finished, in curd-criteria order. A writer that
    # completed nothing still checkpoints for its deliverables and next action.
    completed: tuple[CriterionResultWriterView, ...] = attrs.field(
        factory=tuple, converter=_tuple_sequence
    )
    # Files the writer already wrote — the changed-file ownership a redispatch
    # must not re-derive.
    deliverables: tuple[DeliverableWriterView, ...] = attrs.field(
        factory=tuple, converter=_tuple_sequence
    )
    # Unfinished work and the exact next action, in the writer's own words.
    remaining: tuple[str, ...] = attrs.field(factory=tuple, converter=_tuple_sequence)


class WriterBudgetExceeded(Exception):
    """Raised by a writer dispatch stopping at its context or tool budget.

    Distinct from every other writer failure so a run ledger can tell an
    overrun apart from a correctness, environment, or tool-call error.
    """

    def __init__(self, checkpoint: WriterCheckpoint) -> None:
        super().__init__(checkpoint.reason)
        self.checkpoint: WriterCheckpoint = checkpoint


@attrs.define(frozen=True)
class CureDiagnosisBinding:
    """Host-owned authorization for one exact plan curd."""

    source_plan_ref: SourcePlanRef = attrs.field(
        validator=attrs.validators.instance_of(SourcePlanRef)
    )
    source_curd_ref: SourceCurdRef = attrs.field(
        validator=attrs.validators.instance_of(SourceCurdRef)
    )
    diagnosis: DiagnosisResult = attrs.field(
        validator=attrs.validators.instance_of(DiagnosisResult)
    )


CureDiagnosisBindings = Mapping[str, CureDiagnosisBinding] | tuple[
    CureDiagnosisBinding, ...
]


def _canonical_value(value: object) -> object:
    if attrs.has(type(value)):
        fields = cast("tuple[Attribute[object], ...]", attrs.fields(type(value)))
        return {
            field.name: _canonical_value(cast(object, getattr(value, field.name)))
            for field in fields
        }
    if isinstance(value, Enum):
        return cast(object, value.value)
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _canonical_value(item) for key, item in mapping.items()}
    if isinstance(value, (tuple, list)):
        sequence = cast(tuple[object, ...] | list[object], value)
        return [_canonical_value(item) for item in sequence]
    return value


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            _canonical_value(value),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _canonical_digest(value: object) -> str:
    return _artifact_digest(_canonical_bytes(value))


def _version(contract: type) -> ContractVersion:
    version = supported_version_for(contract)
    if version is None:
        raise TypeError(f"{contract.__name__} does not carry a contract version")
    return version




def _planner_view(output: object) -> PlannerResultWriterView:
    if isinstance(output, PlannerResultWriterView):
        return output
    if isinstance(output, AgentWriterView):
        writer = output
    else:
        raise TypeError("planner dispatch must return a planner writer view")
    if writer.kind is not WriterViewKind.PLANNER_RESULT:
        raise ContractValidationError("planner dispatch returned the wrong writer kind")
    assert isinstance(writer.payload, PlannerResultWriterView)
    return writer.payload


def _plan_identity(
    request: PlannerRequest,
    view: PlannerResultWriterView,
    source_plan: CurdPlan | None,
    lineages: Mapping[str, IdentityLineage],
) -> tuple[str | None, dict[str, str]]:
    if view.plan is None:
        return None, {}
    if request.kind is PlannerRequestKind.REPLAN:
        if source_plan is None:
            raise ValueError("replan workflow requires its source CurdPlan")
        plan_id = source_plan.plan_id
    else:
        plan_id = f"{request.request_id}/plan"
    curd_ids: dict[str, str] = {}
    for index, curd in enumerate(view.plan.curds, start=1):
        lineage = lineages.get(curd.key)
        if lineage is not None and lineage.identity_action is IdentityAction.RETAIN:
            curd_ids[curd.key] = lineage.source_curd_ids[0]
        else:
            curd_ids[curd.key] = f"{plan_id}/curd/{index}"
    return plan_id, curd_ids


def _materialize_plan(
    request: PlannerRequest,
    dispatch: PlannerDispatch,
    *,
    artifacts: Mapping[str, ArtifactRef],
    evidence: Mapping[str, EvidenceRef],
    lineages: Mapping[str, IdentityLineage],
    source_plan: CurdPlan | None,
) -> PlannerResult:
    view = _planner_view(dispatch(request))
    plan_id, curd_ids = _plan_identity(request, view, source_plan, lineages)
    return materialize_planner_result(
        request,
        view,
        plan_id=plan_id,
        curd_ids=curd_ids,
        artifacts=artifacts,
        evidence=evidence,
        lineages=lineages,
        source_plan=source_plan,
    )


def plan(
    request: PlannerRequest,
    dispatch: PlannerDispatch,
    *,
    artifacts: Mapping[str, ArtifactRef] | None = None,
    evidence: Mapping[str, EvidenceRef] | None = None,
    lineages: Mapping[str, IdentityLineage] | None = None,
    source_plan: CurdPlan | None = None,
) -> PlannerResult:
    return _materialize_plan(
        request,
        dispatch,
        artifacts={} if artifacts is None else artifacts,
        evidence={} if evidence is None else evidence,
        lineages={} if lineages is None else lineages,
        source_plan=source_plan,
    )


def _retained_artifact(
    artifact: ArtifactRef,
    resolved_path: str,
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact.artifact_id,
        role=artifact.role,
        uri=Path(resolved_path).resolve(strict=True).as_uri(),
        digest=artifact.digest,
        size_bytes=artifact.size_bytes,
        media_type=artifact.media_type,
        schema_uri=artifact.schema_uri,
    )


def _resolve_verified_artifact(
    artifact: ArtifactRef,
    repository_root: Path,
    artifact_directory: Path,
) -> tuple[object, ArtifactRef]:
    resolved = resolve_artifact(
        artifact,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
    )
    return resolved, _retained_artifact(artifact, resolved.path)


def _resolve_plan_context(
    plan: CurdPlan,
    *,
    repository_root: Path,
    artifact_directory: Path,
    evidence: Mapping[str, EvidenceRef],
) -> tuple[tuple[object, ...], dict[str, object], dict[str, EvidenceRef]]:
    shared_inputs = (
        ()
        if plan.context is None
        else tuple(
            resolve_artifact(
                artifact,
                repository_root=repository_root,
                artifact_directory=artifact_directory,
            )
            for artifact in plan.context.shared_inputs
        )
    )
    resolved_evidence: dict[str, object] = {}
    durable_evidence: dict[str, EvidenceRef] = {}
    for key, item in evidence.items():
        resolved, retained = _resolve_verified_artifact(
            item.artifact,
            repository_root,
            artifact_directory,
        )
        resolved_evidence[key] = resolved
        durable_evidence[key] = EvidenceRef(
            evidence_id=item.evidence_id,
            kind=item.kind,
            artifact=retained,
            location=item.location,
            summary=item.summary,
        )
    return shared_inputs, resolved_evidence, durable_evidence


def _writer_context(
    curd: SemanticCurd,
    plan: CurdPlan,
    *,
    repository_root: Path,
    artifact_directory: Path,
    resolved_evidence: Mapping[str, object],
    durable_evidence: Mapping[str, EvidenceRef],
    shared_inputs: tuple[object, ...],
    phase: Literal["cook", "cure"],
) -> tuple[dict[str, object], dict[str, EvidenceRef]]:
    input_pairs = tuple(
        _resolve_verified_artifact(artifact, repository_root, artifact_directory)
        for artifact in curd.inputs
    )
    resolved_inputs = {
        f"input-{index}": resolved
        for index, (resolved, _retained) in enumerate(input_pairs, start=1)
    }
    input_evidence = {
        key: EvidenceRef(
            evidence_id=f"{curd.curd_id}/evidence/{key}",
            kind=EvidenceKind.SOURCE,
            artifact=retained,
        )
        for key, (_resolved, retained) in zip(resolved_inputs, input_pairs)
    }
    collision = set(input_evidence) & set(durable_evidence)
    if collision:
        names = ", ".join(sorted(collision))
        raise ValueError(f"evidence keys collide with curd inputs: {names}")
    context: dict[str, object] = {
        "phase": phase,
        "outcome": curd.outcome,
        "scope": curd.scope,
        "inputs": resolved_inputs,
        "outputs": curd.outputs,
        "criteria": tuple(
            CriterionWriterView(item.description, item.check)
            for item in curd.criteria
        ),
        "shared_inputs": shared_inputs,
        "constraints": () if plan.context is None else plan.context.constraints,
        "invariants": () if plan.context is None else plan.context.invariants,
        "evidence_inputs": dict(resolved_evidence),
    }
    return context, input_evidence | dict(durable_evidence)


def _artifact_digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _deliverables(
    result_id: str,
    view: CurdResultWriterView,
    *,
    repository_root: Path,
    artifact_directory: Path,
) -> tuple[dict[str, ArtifactRef], dict[str, EvidenceRef]]:
    artifacts: dict[str, ArtifactRef] = {}
    evidence: dict[str, EvidenceRef] = {}
    for index, item in enumerate(view.deliverables, start=1):
        if item.path in artifacts:
            raise ValueError(f"duplicate deliverable path: {item.path}")
        source_uri = f"repo://{quote(item.path, safe='/-._~')}"
        parsed = urlsplit(source_uri)
        payload, detected_type = read_repository_artifact(
            parsed.netloc,
            parsed.path,
            repository_root,
            None,
        )
        source = ArtifactRef(
            artifact_id=f"{result_id}/artifact/{index}",
            role=item.role,
            uri=source_uri,
            digest=_artifact_digest(payload),
            size_bytes=len(payload),
            media_type=item.media_type,
        )
        resolved = resolve_verified_bytes(
            source,
            payload,
            detected_type,
            artifact_directory,
        )
        artifact = _retained_artifact(source, resolved.path)
        artifacts[item.path] = artifact
        evidence[item.path] = EvidenceRef(
            evidence_id=f"{result_id}/evidence/{index}",
            kind=EvidenceKind.RUNTIME,
            artifact=artifact,
        )
    return artifacts, evidence


def _source_curd_ref(_plan: CurdPlan, curd: SemanticCurd) -> SourceCurdRef:
    return SourceCurdRef(curd.curd_id, _canonical_digest(curd))


def bind_diagnosis(
    plan: CurdPlan,
    curd: SemanticCurd,
    diagnosis: DiagnosisResult,
) -> CureDiagnosisBinding:
    """Bind a confirmed diagnosis to the exact plan curd it authorizes."""

    return CureDiagnosisBinding(
        SourcePlanRef(plan.plan_id, plan.revision, plan.digest),
        _source_curd_ref(plan, curd),
        diagnosis,
    )


def _normalize(
    output: object,
    kind: WriterViewKind,
    invocation: Mapping[str, object],
) -> CanonicalArtifact:
    if isinstance(output, AgentWriterView):
        writer = output
    elif kind is WriterViewKind.CURD_RESULT and isinstance(
        output, CurdResultWriterView
    ):
        writer = AgentWriterView(kind, output)
    elif kind is WriterViewKind.REVIEW_RESULT and isinstance(
        output, ReviewResultWriterView
    ):
        writer = AgentWriterView(kind, output)
    elif kind is WriterViewKind.DIAGNOSIS_RESULT and isinstance(
        output, DiagnosisResultWriterView
    ):
        writer = AgentWriterView(kind, output)
    else:
        writer = output
    canonical = normalize_agent_output(writer, invocation)
    expected = {
        WriterViewKind.CURD_RESULT: CurdResult,
        WriterViewKind.REVIEW_RESULT: ReviewResult,
        WriterViewKind.DIAGNOSIS_RESULT: DiagnosisResult,
    }[kind]
    if not isinstance(canonical.value, expected):
        raise ContractValidationError(f"dispatch returned {canonical.value.__class__.__name__}")
    return canonical


def _subject_artifact(
    result_id: str,
    canonical: CanonicalArtifact,
    artifact_directory: Path,
) -> ArtifactRef:
    if len(canonical.canonical_bytes) > MAX_ARTIFACT_BYTES:
        raise ValueError(
            f"artifact exceeds maximum size of {MAX_ARTIFACT_BYTES} bytes"
        )
    artifact_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = ArtifactRef(
        artifact_id=f"{result_id}/subject",
        role="curd-result",
        uri="file:///placeholder",
        digest=_artifact_digest(canonical.canonical_bytes),
        size_bytes=len(canonical.canonical_bytes),
        media_type="application/json",
    )
    fd, temporary_name = tempfile.mkstemp(
        prefix=".curd-result-subject-",
        suffix=".json",
        dir=str(artifact_directory),
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as writer:
            os.fchmod(writer.fileno(), 0o600)
            _ = writer.write(canonical.canonical_bytes)
            writer.flush()
            os.fsync(writer.fileno())
        descriptor = attrs.evolve(descriptor, uri=temporary_path.resolve().as_uri())
        resolved = resolve_artifact(
            descriptor,
            repository_root=artifact_directory,
            artifact_directory=artifact_directory,
        )
        return _retained_artifact(descriptor, resolved.path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _evidence_values(evidence: Mapping[str, EvidenceRef]) -> tuple[EvidenceRef, ...]:
    unique: dict[str, EvidenceRef] = {}
    for item in evidence.values():
        _ = unique.setdefault(item.evidence_id, item)
    return tuple(unique.values())


def _review(
    request: ReviewRequest,
    output: object,
    evidence: Mapping[str, EvidenceRef],
) -> ReviewResult:
    def coverage(
        disposition: ReviewDisposition, reason: str | None
    ) -> tuple[ReviewCoverage, ...]:
        if disposition in {
            ReviewDisposition.BLOCKED,
            ReviewDisposition.INVALID,
            ReviewDisposition.EXECUTOR_FAILURE,
        }:
            return tuple(
                ReviewCoverage(
                    target,
                    CoverageDisposition.NOT_COVERED,
                    reason or "Review did not cover the target",
                )
                for target in request.coverage_targets
            )
        return tuple(
            ReviewCoverage(target, CoverageDisposition.COVERED)
            for target in request.coverage_targets
        )

    initial_coverage = tuple(
        ReviewCoverage(target, CoverageDisposition.COVERED)
        for target in request.coverage_targets
    )
    invocation = {
        "review_id": request.review_id,
        "coverage": initial_coverage,
        "evidence": evidence,
        "contract_version": _version(ReviewResult),
    }
    provisional = _normalize(
        output,
        WriterViewKind.REVIEW_RESULT,
        invocation,
    )
    assert isinstance(provisional.value, ReviewResult)
    review = provisional.value
    normalized_coverage = coverage(review.disposition, review.reason)
    if review.coverage != normalized_coverage:
        invocation["coverage"] = normalized_coverage
        provisional = _normalize(
            output,
            WriterViewKind.REVIEW_RESULT,
            invocation,
        )
    assert isinstance(provisional.value, ReviewResult)
    return provisional.value


def _reviewed_result_view(
    view: CurdResultWriterView,
    review: ReviewResult,
) -> CurdResultWriterView:
    if review.disposition is ReviewDisposition.CLEAN:
        return view
    if review.disposition is ReviewDisposition.FINDINGS:
        evidence_keys = tuple(
            dict.fromkeys(
                item.evidence_id
                for finding in review.findings
                for item in finding.evidence
            )
        )
        rows = tuple(
            CriterionResultWriterView(
                CriterionDisposition.FAILED,
                evidence_keys=evidence_keys,
            )
            for _ in view.criterion_results
        )
        return CurdResultWriterView(rows, view.deliverables, view.unresolved_work)
    reason = review.reason or "Review did not cover the curd result"
    rows = tuple(
        CriterionResultWriterView(CriterionDisposition.BLOCKED, reason=reason)
        for _ in view.criterion_results
    )
    return CurdResultWriterView(
        rows,
        view.deliverables,
        (*view.unresolved_work, reason),
    )


def _diagnosis(
    request: DiagnosisRequest,
    output: object,
    evidence: Mapping[str, EvidenceRef],
) -> DiagnosisResult:
    canonical = _normalize(
        output,
        WriterViewKind.DIAGNOSIS_RESULT,
        {
            "diagnosis_id": request.diagnosis_id,
            "symptom": request.symptom,
            "subject_artifact_id": request.subject.artifact_id,
            "evidence": evidence,
            "contract_version": _version(DiagnosisResult),
        },
    )
    assert isinstance(canonical.value, DiagnosisResult)
    return canonical.value


_MAX_REASON_LENGTH = 4096
_MAX_REASON_CAUSES = 4
_MAX_CAUSE_MESSAGE_LENGTH = 256
_CREDENTIALS_IN_URI = re.compile(r"(?i)(https?://)([^/\s@]+)@")


def _failure_reason(stage: str, error: BaseException) -> str:
    details: list[str] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and len(details) < _MAX_REASON_CAUSES:
        marker = id(current)
        if marker in seen:
            break
        seen.add(marker)
        name = type(current).__name__
        status = getattr(current, "status", None)
        if not isinstance(status, int):
            status = getattr(current, "code", None)
        status_detail = f" status={status}" if isinstance(status, int) else ""
        try:
            message = str(current)
        except Exception:
            message = "<unprintable exception>"
        message = " ".join(message.split())
        message = _CREDENTIALS_IN_URI.sub(r"\1<redacted>@", message)
        message = message[:_MAX_CAUSE_MESSAGE_LENGTH] or "<no message>"
        details.append(f"{name}{status_detail}: {message}")
        current = current.__cause__ or current.__context__
    if not details:
        details.append("<unprintable exception>")
    return f"{stage}: " + " <- ".join(details)[:_MAX_REASON_LENGTH]


def _writer_view(output: object) -> CurdResultWriterView:
    if isinstance(output, CurdResultWriterView):
        return output
    if isinstance(output, AgentWriterView):
        if output.kind is not WriterViewKind.CURD_RESULT:
            raise ContractValidationError(
                "writer dispatch returned the wrong writer kind"
            )
        assert isinstance(output.payload, CurdResultWriterView)
        return output.payload
    raise ContractValidationError(
        "writer dispatch must return a curd result writer view"
    )


def _blocked_writer_view(
    curd: SemanticCurd,
    reason: str,
) -> CurdResultWriterView:
    rows = tuple(
        CriterionResultWriterView(
            CriterionDisposition.BLOCKED,
            reason=reason,
        )
        for _criterion in curd.criteria
    )
    return CurdResultWriterView(
        criterion_results=rows,
        deliverables=(),
        unresolved_work=(reason,),
    )


def _checkpoint_writer_view(
    curd: SemanticCurd,
    reason: str,
    checkpoint: WriterCheckpoint,
) -> CurdResultWriterView:
    """Host-finalize an overrun into a partial result the next dispatch resumes.

    Criteria the writer finished keep their disposition, evidence, and
    deliverables; every criterion it did not reach is blocked on the overrun
    reason. A checkpoint may never cover the whole curd: the review branch is
    skipped on this path, so a full-coverage checkpoint would be a pass no
    reviewer ever saw.
    """

    if len(checkpoint.completed) >= len(curd.criteria):
        raise ValueError(
            "budget checkpoint must leave at least one criterion unfinished, "
            + f"not {len(checkpoint.completed)} of {len(curd.criteria)}"
        )
    unreached = len(curd.criteria) - len(checkpoint.completed)
    return CurdResultWriterView(
        criterion_results=(
            *checkpoint.completed,
            *(
                CriterionResultWriterView(
                    CriterionDisposition.BLOCKED,
                    reason=reason,
                )
                for _unreached in range(unreached)
            ),
        ),
        deliverables=checkpoint.deliverables,
        unresolved_work=(reason, *checkpoint.remaining),
    )


def _result_invocation(
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    *,
    evidence: Mapping[str, EvidenceRef],
    deliverables: Mapping[str, ArtifactRef],
    runtime_refs: tuple[str, ...],
) -> dict[str, object]:
    return {
        "result_id": f"{plan.plan_id}/revision/{plan.revision}/result/{index}",
        "source_plan_ref": SourcePlanRef(plan.plan_id, plan.revision, plan.digest),
        "source_curd_ref": _source_curd_ref(plan, curd),
        "expected_criterion_ids": [item.criterion_id for item in curd.criteria],
        "evidence": evidence,
        "deliverables": deliverables,
        "runtime_refs": runtime_refs,
        "contract_version": _version(CurdResult),
    }


def _blocked_result(
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    reason: str,
    *,
    provenance_refs: tuple[str, ...],
) -> CurdResult:
    invocation = _result_invocation(
        plan,
        curd,
        index,
        evidence={},
        deliverables={},
        runtime_refs=provenance_refs,
    )
    canonical = _normalize(
        _blocked_writer_view(curd, reason),
        WriterViewKind.CURD_RESULT,
        invocation,
    )
    assert isinstance(canonical.value, CurdResult)
    return canonical.value


def _review_failure(
    request: ReviewRequest,
    reason: str,
    disposition: ReviewDisposition,
    evidence: Mapping[str, EvidenceRef],
) -> ReviewResult:
    return _review(
        request,
        ReviewResultWriterView(disposition, [], reason),
        evidence,
    )


def _diagnosis_failure(
    request: DiagnosisRequest,
    reason: str,
    disposition: DiagnosisDisposition,
    evidence: Mapping[str, EvidenceRef],
) -> DiagnosisResult:
    return _diagnosis(
        request,
        DiagnosisResultWriterView(
            disposition=disposition,
            reproduction=ReproductionWriterView(
                status=ReproductionDisposition.BLOCKED,
                steps=("Invoke the diagnosis callback",),
                observed=reason,
            ),
            hypotheses=(),
            reason=reason,
        ),
        evidence,
    )


def _execute_curd(
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    *,
    repository_root: Path,
    artifact_directory: Path,
    resolved_evidence: Mapping[str, object],
    durable_evidence: Mapping[str, EvidenceRef],
    shared_inputs: tuple[object, ...],
    phase: Literal["cook", "cure"],
    provenance_refs: tuple[str, ...],
    dispatch_writer: WriterDispatch,
    dispatch_review: ReviewDispatch,
    dispatch_diagnosis: DiagnosisDispatch,
) -> tuple[BranchResult | None, CurdResult]:
    try:
        context, host_evidence = _writer_context(
            curd,
            plan,
            repository_root=repository_root,
            artifact_directory=artifact_directory,
            resolved_evidence=resolved_evidence,
            durable_evidence=durable_evidence,
            shared_inputs=shared_inputs,
            phase=phase,
        )
    except Exception as error:
        return None, _blocked_result(
            plan,
            curd,
            index,
            _failure_reason("writer context failed", error),
            provenance_refs=provenance_refs,
        )

    overrun_reason: str | None = None
    try:
        output = dispatch_writer(context)
    except WriterBudgetExceeded as overrun:
        overrun_reason = _failure_reason("writer stopped at its budget", overrun)
        try:
            writer_view = _checkpoint_writer_view(
                curd, overrun_reason, overrun.checkpoint
            )
        except Exception as error:
            return None, _blocked_result(
                plan,
                curd,
                index,
                _failure_reason("budget checkpoint invalid", error),
                provenance_refs=provenance_refs,
            )
    except Exception as error:
        return None, _blocked_result(
            plan,
            curd,
            index,
            _failure_reason("writer callback failed", error),
            provenance_refs=provenance_refs,
        )
    else:
        try:
            writer_view = _writer_view(output)
        except Exception as error:
            return None, _blocked_result(
                plan,
                curd,
                index,
                _failure_reason("writer output invalid", error),
                provenance_refs=provenance_refs,
            )

    result_id = f"{plan.plan_id}/revision/{plan.revision}/result/{index}"
    try:
        deliverables, runtime_evidence = _deliverables(
            result_id,
            writer_view,
            repository_root=repository_root,
            artifact_directory=artifact_directory,
        )
        collision = set(host_evidence) & set(runtime_evidence)
        if collision:
            names = ", ".join(sorted(collision))
            raise ValueError(f"deliverable evidence keys collide: {names}")
        host_evidence |= runtime_evidence
        invocation = _result_invocation(
            plan,
            curd,
            index,
            evidence=host_evidence,
            deliverables=deliverables,
            runtime_refs=provenance_refs,
        )
        provisional = _normalize(
            writer_view,
            WriterViewKind.CURD_RESULT,
            invocation,
        )
        if overrun_reason is not None:
            # The writer stopped mid-curd: there is no finished result to
            # review or diagnose, only progress to hand the next dispatch.
            assert isinstance(provisional.value, CurdResult)
            return None, provisional.value
        subject = _subject_artifact(
            result_id,
            provisional,
            artifact_directory,
        )
    except Exception as error:
        return None, _blocked_result(
            plan,
            curd,
            index,
            _failure_reason(
                "budget checkpoint invalid"
                if overrun_reason is not None
                else "writer output invalid",
                error,
            ),
            provenance_refs=provenance_refs,
        )

    subject_evidence = EvidenceRef(
        evidence_id=f"{result_id}/subject-evidence",
        kind=EvidenceKind.RUNTIME,
        artifact=subject,
    )
    host_evidence[subject_evidence.evidence_id] = subject_evidence
    passed = all(
        item.disposition is CriterionDisposition.PASSED
        for item in writer_view.criterion_results
    )
    if passed:
        request = ReviewRequest(
            contract_version=_version(ReviewRequest),
            review_id=f"{result_id}/review",
            subject=subject,
            coverage_targets=[item.criterion_id for item in curd.criteria],
            evidence=_evidence_values(host_evidence),
        )
        try:
            review_output = dispatch_review(request)
        except Exception as error:
            branch = _review_failure(
                request,
                _failure_reason("review callback failed", error),
                ReviewDisposition.EXECUTOR_FAILURE,
                {item.evidence_id: item for item in request.evidence},
            )
        else:
            try:
                branch = _review(
                    request,
                    review_output,
                    {item.evidence_id: item for item in request.evidence},
                )
            except Exception as error:
                branch = _review_failure(
                    request,
                    _failure_reason("review output invalid", error),
                    ReviewDisposition.INVALID,
                    {item.evidence_id: item for item in request.evidence},
                )
        writer_view = _reviewed_result_view(writer_view, branch)
        for finding in branch.findings:
            for item in finding.evidence:
                host_evidence[item.evidence_id] = item
        runtime_ref = branch.review_id
    else:
        failed = [
            criterion.description
            for criterion, row in zip(curd.criteria, writer_view.criterion_results)
            if row.disposition is not CriterionDisposition.PASSED
        ]
        request = DiagnosisRequest(
            contract_version=_version(DiagnosisRequest),
            diagnosis_id=f"{result_id}/diagnosis",
            symptom="Curd execution did not pass: " + "; ".join(failed),
            subject=subject,
            evidence=_evidence_values(host_evidence),
        )
        try:
            diagnosis_output = dispatch_diagnosis(request)
        except Exception as error:
            branch = _diagnosis_failure(
                request,
                _failure_reason("diagnosis callback failed", error),
                DiagnosisDisposition.EXECUTOR_FAILURE,
                {item.evidence_id: item for item in request.evidence},
            )
        else:
            try:
                branch = _diagnosis(
                    request,
                    diagnosis_output,
                    {item.evidence_id: item for item in request.evidence},
                )
            except Exception as error:
                branch = _diagnosis_failure(
                    request,
                    _failure_reason("diagnosis output invalid", error),
                    DiagnosisDisposition.INVALID,
                    {item.evidence_id: item for item in request.evidence},
                )
        runtime_ref = branch.diagnosis_id
    invocation = _result_invocation(
        plan,
        curd,
        index,
        evidence=host_evidence,
        deliverables=deliverables,
        runtime_refs=(*provenance_refs, runtime_ref),
    )
    try:
        final = _normalize(writer_view, WriterViewKind.CURD_RESULT, invocation)
    except Exception as error:
        return None, _blocked_result(
            plan,
            curd,
            index,
            _failure_reason("result normalization failed", error),
            provenance_refs=(*provenance_refs, runtime_ref),
        )
    assert isinstance(final.value, CurdResult)
    return branch, final.value


def _coerce_diagnosis_bindings(
    bindings: CureDiagnosisBindings,
) -> dict[str, CureDiagnosisBinding]:
    if isinstance(bindings, Mapping):
        entries = tuple(bindings.items())
    elif isinstance(bindings, tuple):  # pyright: ignore[reportUnnecessaryIsInstance]
        entries = tuple((None, item) for item in bindings)
    else:
        raise TypeError(  # pyright: ignore[reportUnreachable]
            "cure requires a mapping or tuple of per-curd diagnosis bindings"
        )
    normalized: dict[str, CureDiagnosisBinding] = {}
    for key, binding in entries:
        if not isinstance(binding, CureDiagnosisBinding):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("cure diagnosis bindings must be CureDiagnosisBinding values")
        curd_id = binding.source_curd_ref.curd_id
        if key is not None and key != curd_id:
            raise ValueError(
                f"diagnosis binding key {key!r} does not match source curd {curd_id!r}"
            )
        if curd_id in normalized:
            raise ValueError(f"duplicate diagnosis binding for curd {curd_id!r}")
        normalized[curd_id] = binding
    return normalized


def _require_confirmed_bindings(
    bindings: Mapping[str, CureDiagnosisBinding],
) -> None:
    for curd_id, binding in bindings.items():
        if binding.diagnosis.disposition is not DiagnosisDisposition.CONFIRMED:
            raise ValueError(
                f"cure dispatch requires a confirmed diagnosis for curd {curd_id!r}"
            )


def _validate_cure_bindings(
    curd_plan: CurdPlan,
    bindings: CureDiagnosisBindings,
) -> dict[str, CureDiagnosisBinding]:
    if curd_plan.digest != curd_plan_digest(curd_plan):
        raise ValueError("curd plan digest does not match its canonical content")
    normalized = _coerce_diagnosis_bindings(bindings)
    expected_plan = SourcePlanRef(
        curd_plan.plan_id,
        curd_plan.revision,
        curd_plan.digest,
    )
    expected_curds = {curd.curd_id: curd for curd in curd_plan.curds}
    missing = sorted(set(expected_curds) - set(normalized))
    extra = sorted(set(normalized) - set(expected_curds))
    if missing or extra:
        raise ValueError(
            f"diagnosis bindings must match plan curds exactly; missing={missing!r}, extra={extra!r}"
        )
    for curd_id, curd in expected_curds.items():
        binding = normalized[curd_id]
        if binding.source_plan_ref != expected_plan:
            raise ValueError(
                f"diagnosis binding for curd {curd_id!r} has a stale source plan ref"
            )
        expected_curd = _source_curd_ref(curd_plan, curd)
        if binding.source_curd_ref != expected_curd:
            raise ValueError(
                f"diagnosis binding for curd {curd_id!r} has a stale source curd ref"
            )
    _require_confirmed_bindings(normalized)
    return normalized


def _execute_plan(
    curd_plan: CurdPlan,
    *,
    repository_root: str | Path,
    artifact_directory: str | Path,
    evidence: Mapping[str, EvidenceRef],
    phase: Literal["cook", "cure"],
    provenance_refs: tuple[str, ...],
    diagnosis_bindings: Mapping[str, CureDiagnosisBinding] | None,
    dispatch_writer: WriterDispatch,
    dispatch_review: ReviewDispatch,
    dispatch_diagnosis: DiagnosisDispatch,
) -> ExecutionResults:
    branches: list[BranchResult] = []
    results: list[CurdResult] = []
    root = Path(repository_root)
    artifacts = Path(artifact_directory)
    if not curd_plan.curds:
        return (), ()
    try:
        shared_inputs, resolved_evidence, durable_evidence = _resolve_plan_context(
            curd_plan,
            repository_root=root,
            artifact_directory=artifacts,
            evidence=evidence,
        )
    except Exception as error:
        reason = _failure_reason("writer context failed", error)
        return (), tuple(
            _blocked_result(
                curd_plan,
                curd,
                index,
                reason,
                provenance_refs=provenance_refs,
            )
            for index, curd in enumerate(curd_plan.curds, start=1)
        )
    for index, curd in enumerate(curd_plan.curds, start=1):
        curd_provenance = provenance_refs
        if diagnosis_bindings is not None:
            curd_provenance = (
                *curd_provenance,
                diagnosis_bindings[curd.curd_id].diagnosis.diagnosis_id,
            )
        branch, result = _execute_curd(
            curd_plan,
            curd,
            index,
            repository_root=root,
            artifact_directory=artifacts,
            resolved_evidence=resolved_evidence,
            durable_evidence=durable_evidence,
            shared_inputs=shared_inputs,
            phase=phase,
            provenance_refs=curd_provenance,
            dispatch_writer=dispatch_writer,
            dispatch_review=dispatch_review,
            dispatch_diagnosis=dispatch_diagnosis,
        )
        if branch is not None:
            branches.append(branch)
        results.append(result)
    return tuple(branches), tuple(results)


def cook(
    curd_plan: CurdPlan,
    *,
    repository_root: str | Path,
    artifact_directory: str | Path,
    dispatch_writer: WriterDispatch,
    dispatch_review: ReviewDispatch,
    dispatch_diagnosis: DiagnosisDispatch,
    evidence: Mapping[str, EvidenceRef] | None = None,
) -> ExecutionResults:
    validated_plan = validate_curd_plan(curd_plan)
    return _execute_plan(
        validated_plan,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        evidence={} if evidence is None else evidence,
        phase="cook",
        provenance_refs=(),
        diagnosis_bindings=None,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis,
    )



def cure(
    curd_plan: CurdPlan,
    diagnosis_bindings: CureDiagnosisBindings,
    *,
    repository_root: str | Path,
    artifact_directory: str | Path,
    dispatch_writer: WriterDispatch,
    dispatch_review: ReviewDispatch,
    dispatch_diagnosis: DiagnosisDispatch,
    evidence: Mapping[str, EvidenceRef] | None = None,
) -> ExecutionResults:
    validated_plan = validate_curd_plan(curd_plan)
    normalized = _validate_cure_bindings(validated_plan, diagnosis_bindings)
    return _execute_plan(
        validated_plan,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        evidence={} if evidence is None else evidence,
        phase="cure",
        provenance_refs=(),
        diagnosis_bindings=normalized,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis,
    )


def run_workflow(
    request: PlannerRequest,
    *,
    repository_root: str | Path,
    artifact_directory: str | Path,
    dispatch_planner: PlannerDispatch,
    dispatch_writer: WriterDispatch,
    dispatch_review: ReviewDispatch,
    dispatch_diagnosis: DiagnosisDispatch,
    artifacts: Mapping[str, ArtifactRef] | None = None,
    evidence: Mapping[str, EvidenceRef] | None = None,
    lineages: Mapping[str, IdentityLineage] | None = None,
    source_plan: CurdPlan | None = None,
    phase: Literal["cook", "cure"] = "cook",
    diagnosis_bindings: CureDiagnosisBindings | None = None,
) -> WorkflowResults:
    if phase == "cure":
        if diagnosis_bindings is None:
            raise ValueError("cure requires per-curd diagnosis bindings")
        prevalidated = _coerce_diagnosis_bindings(diagnosis_bindings)
        if not prevalidated:
            raise ValueError("cure requires per-curd diagnosis bindings")
        _require_confirmed_bindings(prevalidated)
    else:
        prevalidated = None
    planner_result = _materialize_plan(
        request,
        dispatch_planner,
        artifacts={} if artifacts is None else artifacts,
        evidence={} if evidence is None else evidence,
        lineages={} if lineages is None else lineages,
        source_plan=source_plan,
    )
    if planner_result.plan is None:
        return planner_result, (), ()
    validated_plan = validate_curd_plan(planner_result.plan)
    if phase == "cure":
        if prevalidated is None:
            raise TypeError(
                "cure requires a mapping or tuple of per-curd diagnosis bindings"
            )
        normalized = _validate_cure_bindings(validated_plan, prevalidated)
    else:
        normalized = None
    branches, results = _execute_plan(
        validated_plan,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        evidence={} if evidence is None else evidence,
        phase=phase,
        provenance_refs=(),
        diagnosis_bindings=normalized,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis,
    )
    return planner_result, branches, results


__all__ = [
    "CureDiagnosisBinding",
    "CureDiagnosisBindings",
    "WriterBudgetExceeded",
    "WriterCheckpoint",
    "bind_diagnosis",
    "cook",
    "cure",
    "plan",
    "run_workflow",
]
