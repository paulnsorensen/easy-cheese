from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Literal, cast
from urllib.parse import quote, urlsplit

import attrs
from attrs import Attribute

from easy_cheese_schemas.contracts import (
    AgentWriterView,
    ArtifactLink,
    ArtifactRef,
    CheckpointIntent,
    ContractVersion,
    CoverageDisposition,
    Criterion,
    CriterionDisposition,
    CriterionResultWriterView,
    CurdPlan,
    CurdResult,
    CurdResultWriterView,
    RemediationCureWriterView,
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
    NextMove,
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
    _bounded_string,  # pyright: ignore[reportPrivateUsage]
    _list_of,  # pyright: ignore[reportPrivateUsage]
    _string_list,  # pyright: ignore[reportPrivateUsage]
    _tuple_sequence,  # pyright: ignore[reportPrivateUsage]
)
from easy_cheese_schemas.planner import materialize_planner_result
from easy_cheese_schemas.schema_runtime import (
    CanonicalArtifact,
    ContractValidationError,
    curd_plan_digest,
    normalize_agent_output,
    supported_version_for,
    validate_curd_plan,
)

from . import git_utils, handoff, paths
from .artifacts import (
    MAX_ARTIFACT_BYTES,
    read_repository_artifact,
    resolve_artifact,
    resolve_verified_bytes,
)
from .wheypoint import grounded as wheypoint_grounded
from .wheypoint import recovery as wheypoint_recovery

PlannerDispatch = Callable[[PlannerRequest], object]
WriterDispatch = Callable[[Mapping[str, object]], object]
ReviewDispatch = Callable[[ReviewRequest], object]
DiagnosisDispatch = Callable[[DiagnosisRequest], object]
BranchResult = ReviewResult | DiagnosisResult
ExecutionResults = tuple[tuple[BranchResult, ...], tuple[CurdResult, ...]]
WorkflowResults = tuple[PlannerResult, tuple[BranchResult, ...], tuple[CurdResult, ...]]




def _optional_tuple_sequence(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    values = cast("list[str] | tuple[str, ...]", value)
    return _tuple_sequence(values)


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
    reason: str = attrs.field(validator=_bounded_string)
    # Criteria the writer finished, in curd-criteria order. A writer that
    # completed nothing still checkpoints for its deliverables and next action.
    completed: tuple[CriterionResultWriterView, ...] = attrs.field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(CriterionResultWriterView),
    )
    # Files the writer already wrote — the changed-file ownership a redispatch
    # must not re-derive.
    deliverables: tuple[DeliverableWriterView, ...] = attrs.field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(DeliverableWriterView),
    )
    # Unfinished work and the exact next action, in the writer's own words.
    remaining: tuple[str, ...] = attrs.field(
        factory=tuple, converter=_tuple_sequence, validator=_string_list()
    )
    # Grounded repository ranges the host validates before a recovery retry.
    grounded: tuple[str, ...] | None = attrs.field(
        default=None,
        converter=_optional_tuple_sequence,
        validator=attrs.validators.optional(_string_list()),
    )


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


CureDiagnosisBindings = (
    Mapping[str, CureDiagnosisBinding] | tuple[CureDiagnosisBinding, ...]
)


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
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
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
        "criteria": curd.criteria,
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
    deliverables: tuple[DeliverableWriterView, ...],
    *,
    repository_root: Path,
    artifact_directory: Path,
) -> tuple[dict[str, ArtifactRef], dict[str, EvidenceRef]]:
    artifacts: dict[str, ArtifactRef] = {}
    evidence: dict[str, EvidenceRef] = {}
    for index, item in enumerate(deliverables, start=1):
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
        raise ContractValidationError(
            f"dispatch returned {canonical.value.__class__.__name__}"
        )
    return canonical


def _subject_artifact(
    result_id: str,
    canonical: CanonicalArtifact,
    artifact_directory: Path,
) -> ArtifactRef:
    if len(canonical.canonical_bytes) > MAX_ARTIFACT_BYTES:
        raise ValueError(f"artifact exceeds maximum size of {MAX_ARTIFACT_BYTES} bytes")
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
                item.criterion_id,
                CriterionDisposition.FAILED,
                evidence_keys=evidence_keys,
            )
            for item in view.criterion_results
        )
        return CurdResultWriterView(rows, view.deliverables, view.unresolved_work)
    reason = review.reason or "Review did not cover the curd result"
    rows = tuple(
        CriterionResultWriterView(
            item.criterion_id, CriterionDisposition.BLOCKED, reason=reason
        )
        for item in view.criterion_results
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

def _cure_writer_view(output: object) -> RemediationCureWriterView:
    if isinstance(output, RemediationCureWriterView):
        return output
    raise ContractValidationError(
        "Cure writer dispatch must return a remediation Cure writer view"
    )


def _blocked_rows(
    criteria: tuple[Criterion, ...], reason: str
) -> Iterator[CriterionResultWriterView]:
    return (
        CriterionResultWriterView(
            criterion.criterion_id, CriterionDisposition.BLOCKED, reason=reason
        )
        for criterion in criteria
    )


def _blocked_writer_view(
    curd: SemanticCurd,
    reason: str,
    *,
    deliverables: tuple[DeliverableWriterView, ...] = (),
) -> CurdResultWriterView:
    return CurdResultWriterView(
        criterion_results=tuple(_blocked_rows(curd.criteria, reason)),
        deliverables=deliverables,
        unresolved_work=(reason,),
    )


def _checkpoint_writer_view(
    curd: SemanticCurd,
    reason: str,
    checkpoint: WriterCheckpoint,
) -> CurdResultWriterView:
    """Finalize completed criteria and block each criterion not completed."""
    for position, item in enumerate(checkpoint.completed, start=1):
        if item.disposition not in (
            CriterionDisposition.PASSED,
            CriterionDisposition.FAILED,
        ):
            raise ValueError(
                f"budget checkpoint completed[{position}] must be finished "
                + f"(passed or failed), not {item.disposition.value}"
            )
    completed_ids = [item.criterion_id for item in checkpoint.completed]
    if len(checkpoint.completed) >= len(curd.criteria):
        raise ValueError(
            "budget checkpoint must leave at least one criterion unfinished, "
            + f"not {len(checkpoint.completed)} of {len(curd.criteria)}"
        )
    if len(completed_ids) != len(set(completed_ids)):
        raise ValueError("budget checkpoint must not repeat criterion_id")
    expected_ids = {criterion.criterion_id for criterion in curd.criteria}
    if not set(completed_ids).issubset(expected_ids):
        raise ValueError("budget checkpoint contains an unknown criterion_id")
    remaining = tuple(
        criterion
        for criterion in curd.criteria
        if criterion.criterion_id not in completed_ids
    )
    return CurdResultWriterView(
        criterion_results=(
            *checkpoint.completed,
            *_blocked_rows(remaining, reason),
        ),
        deliverables=checkpoint.deliverables,
        unresolved_work=(reason, *checkpoint.remaining),
    )


def _merge_checkpoint_items(
    previous: Sequence[object],
    latest: Sequence[object],
    *,
    label: str,
    key: Callable[[object], str],
) -> tuple[object, ...]:
    merged = list(previous)
    positions: dict[str, object] = {}
    for item in previous:
        marker = key(item)
        if marker in positions:
            raise ValueError(f"budget checkpoint {label} must not repeat {marker}")
        positions[marker] = item
    for item in latest:
        marker = key(item)
        if marker in positions:
            if positions[marker] != item:
                raise ValueError(f"budget checkpoint {label} conflicts for {marker}")
            continue
        positions[marker] = item
        merged.append(item)
    return tuple(merged)


def _merge_budget_checkpoints(
    previous: WriterCheckpoint, latest: WriterCheckpoint
) -> WriterCheckpoint:
    completed = _merge_checkpoint_items(
        previous.completed,
        latest.completed,
        label="criterion_id",
        key=lambda item: cast(CriterionResultWriterView, item).criterion_id,
    )
    deliverables = _merge_checkpoint_items(
        previous.deliverables,
        latest.deliverables,
        label="deliverable path",
        key=lambda item: cast(DeliverableWriterView, item).path,
    )
    return attrs.evolve(
        latest,
        completed=completed,
        deliverables=deliverables,
        remaining=latest.remaining or previous.remaining,
        grounded=latest.grounded or previous.grounded,
    )


def _result_invocation(
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    *,
    evidence: Mapping[str, EvidenceRef],
    deliverables: Mapping[str, ArtifactRef],
    provenance_refs: tuple[str, ...],
) -> dict[str, object]:
    return {
        "result_id": f"{plan.plan_id}/revision/{plan.revision}/result/{index}",
        "source_plan_ref": SourcePlanRef(plan.plan_id, plan.revision, plan.digest),
        "source_curd_ref": _source_curd_ref(plan, curd),
        "expected_criterion_ids": [item.criterion_id for item in curd.criteria],
        "evidence": evidence,
        "deliverables": deliverables,
        "provenance_refs": provenance_refs,
        "contract_version": _version(CurdResult),
    }


def _blocked_result(
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    reason: str,
    *,
    provenance_refs: tuple[str, ...],
    deliverable_views: tuple[DeliverableWriterView, ...] = (),
    resolved_deliverables: Mapping[str, ArtifactRef] | None = None,
    resolved_evidence: Mapping[str, EvidenceRef] | None = None,
) -> CurdResult:
    invocation = _result_invocation(
        plan,
        curd,
        index,
        evidence=resolved_evidence or {},
        deliverables=resolved_deliverables or {},
        provenance_refs=provenance_refs,
    )
    canonical = _normalize(
        _blocked_writer_view(curd, reason, deliverables=deliverable_views),
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


def _finalize_view(
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    writer_view: CurdResultWriterView,
    *,
    result_id: str,
    repository_root: Path,
    artifact_directory: Path,
    host_evidence: dict[str, EvidenceRef],
    provenance_refs: tuple[str, ...],
) -> tuple[CanonicalArtifact, Mapping[str, ArtifactRef]]:
    """Resolve a writer view's deliverables into host evidence and normalize it.

    Returns the normalized artifact with the resolved deliverables so the caller
    can build a later invocation over the same deliverable set.
    """

    deliverables, runtime_evidence = _deliverables(
        result_id,
        writer_view.deliverables,
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
        provenance_refs=provenance_refs,
    )
    return _normalize(writer_view, WriterViewKind.CURD_RESULT, invocation), deliverables


def _budget_target_identity(root: Path) -> str:
    try:
        result = git_utils.run_git(
            ["config", "--get", "remote.origin.url"], cwd=root, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return str(root.resolve())
    remote = result.stdout.strip() if result.returncode == 0 else ""
    return remote or str(root.resolve())


def _budget_work_id(
    plan: CurdPlan, curd: SemanticCurd, repository_root: Path | None = None
) -> str:
    root = paths.resolve_repo_root(repository_root)
    target = _budget_target_identity(root)
    payload = (
        f"{target}:{plan.plan_id}:{plan.revision}:{plan.digest}:{curd.curd_id}"
    ).encode()
    return "cook-" + hashlib.sha256(payload).hexdigest()[:32]


def _budget_notes(curd: SemanticCurd, checkpoint: WriterCheckpoint) -> str:
    completed = ", ".join(item.criterion_id for item in checkpoint.completed) or "none"
    deliverables = ", ".join(item.path for item in checkpoint.deliverables) or "none"
    remaining = "; ".join(checkpoint.remaining) or "none"
    return (
        f"Writer budget checkpoint for {curd.curd_id}. "
        f"Completed: {completed}. Deliverables: {deliverables}. Remaining: {remaining}."
    )


def _validate_budget_checkpoint(
    *,
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    checkpoint: WriterCheckpoint,
    repository_root: Path,
    host_evidence: Mapping[str, EvidenceRef],
) -> CurdResult:
    if not checkpoint.remaining:
        raise ValueError("writer checkpoint remaining work is empty")
    grounded = tuple(checkpoint.grounded or ())
    if not grounded:
        raise ValueError("writer checkpoint grounded context is empty")
    root = paths.resolve_repo_root(repository_root)
    _ = wheypoint_grounded.validate_grounded(grounded, root=root)
    writer_view = _checkpoint_writer_view(curd, checkpoint.reason, checkpoint)
    with tempfile.TemporaryDirectory(prefix=".budget-checkpoint-") as staging:
        provisional, _ = _finalize_view(
            plan,
            curd,
            index,
            writer_view,
            result_id=f"{plan.plan_id}/revision/{plan.revision}/result/{index}",
            repository_root=root,
            artifact_directory=Path(staging),
            host_evidence=dict(host_evidence),
            provenance_refs=(),
        )
    assert isinstance(provisional.value, CurdResult)
    return provisional.value


def _commit_budget_checkpoint(
    *,
    plan: CurdPlan,
    curd: SemanticCurd,
    checkpoint: WriterCheckpoint,
    repository_root: Path,
) -> tuple[str, tuple[str, ...]]:
    if checkpoint.grounded is None:
        raise ValueError("writer checkpoint has no grounded context")
    grounded = tuple(checkpoint.grounded)
    if not grounded:
        raise ValueError("writer checkpoint grounded context is empty")
    root = paths.resolve_repo_root(repository_root)
    grounded_entries = wheypoint_grounded.validate_grounded(grounded, root=root)
    work_id = _budget_work_id(plan, curd, root)
    orientation = f"Resume cook for {curd.curd_id} from the writer budget checkpoint."
    notes = _budget_notes(curd, checkpoint)
    if len(notes) > 4096:
        raise ValueError("budget checkpoint notes exceed 4096 characters")
    artifact_slug = f"{work_id}-{hashlib.sha256(notes.encode()).hexdigest()[:12]}"
    artifact_path = paths.artifact_path("cook", artifact_slug, root=root)
    artifact = artifact_path.relative_to(root).as_posix()
    project = paths.project_key(root)
    corpus_root = paths.project_corpus_root(project)
    intent = CheckpointIntent(
        work_id=work_id,
        orientation=orientation,
        working_context=list(grounded_entries),
        notes=notes,
        next=NextMove.COOK,
        artifact=artifact,
        artifact_links=[ArtifactLink(path=artifact)],
    )
    payload = (
        handoff.render_handoff_slug(
            handoff.HandoffSlug(
                status="needs-context",
                reason="writer budget exhausted; resume from the authoritative checkpoint",
                next_skill="cook",
                artifact=artifact,
                orientation=orientation,
            )
        )
        + "\n\n"
        + notes
        + "\n"
    ).encode()
    recovery = wheypoint_recovery.persist_checkpoint(
        intent,
        artifact_path=artifact_path,
        artifact_payload=payload,
        repository_root=root,
        corpus_root=corpus_root,
        project_key=project,
    )
    return recovery.work_id, recovery.working_context


def _recovery_context(
    context: Mapping[str, object],
    *,
    plan: CurdPlan,
    curd: SemanticCurd,
    checkpoint: WriterCheckpoint,
    repository_root: Path,
) -> dict[str, object]:
    work_id, working_context = _commit_budget_checkpoint(
        plan=plan,
        curd=curd,
        checkpoint=checkpoint,
        repository_root=repository_root,
    )
    recovered = dict(context)
    recovered.update(
        {
            "checkpoint_ref": work_id,
            "working_context": working_context,
            "completed": checkpoint.completed,
            "deliverables": checkpoint.deliverables,
            "remaining_work": checkpoint.remaining,
            "retry_count": 1,
        }
    )
    return recovered


def _execute_overrun(
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    overrun: WriterBudgetExceeded,
    *,
    repository_root: Path,
    artifact_directory: Path,
    host_evidence: dict[str, EvidenceRef],
    provenance_refs: tuple[str, ...],
    failure_reason: str | None = None,
) -> CurdResult:
    """Finalize a writer's budget overrun without touching the review branch."""

    checkpoint = overrun.checkpoint
    overrun_reason = failure_reason or _failure_reason("writer stopped at its budget", overrun)
    result_id = f"{plan.plan_id}/revision/{plan.revision}/result/{index}"
    try:
        writer_view = _checkpoint_writer_view(curd, overrun_reason, checkpoint)
    except Exception as error:
        reason = _failure_reason("budget checkpoint invalid", error)
        salvaged_views = checkpoint.deliverables
        try:
            salvaged, salvaged_evidence = _deliverables(
                result_id,
                salvaged_views,
                repository_root=repository_root,
                artifact_directory=artifact_directory,
            )
        except Exception as salvage_error:
            salvaged_views, salvaged, salvaged_evidence = (), {}, {}
            reason = (
                f"{reason}; "
                + _failure_reason("deliverable salvage failed", salvage_error)
            )[:_MAX_REASON_LENGTH]
        return _blocked_result(
            plan,
            curd,
            index,
            reason,
            provenance_refs=provenance_refs,
            deliverable_views=salvaged_views,
            resolved_deliverables=salvaged,
            resolved_evidence=salvaged_evidence,
        )

    try:
        provisional, _ = _finalize_view(
            plan,
            curd,
            index,
            writer_view,
            result_id=result_id,
            repository_root=repository_root,
            artifact_directory=artifact_directory,
            host_evidence=host_evidence,
            provenance_refs=provenance_refs,
        )
    except Exception as error:
        return _blocked_result(
            plan,
            curd,
            index,
            _failure_reason("budget checkpoint invalid", error),
            provenance_refs=provenance_refs,
        )
    assert isinstance(provisional.value, CurdResult)
    return provisional.value


@attrs.define(frozen=True)
class CurdWriterExecution:
    """Result of one Cook or Cure writer call before review or diagnosis."""

    plan: CurdPlan
    writer_view: CurdResultWriterView
    host_evidence: dict[str, EvidenceRef]
    deliverables: Mapping[str, ArtifactRef]
    subject: ArtifactRef
    result: CurdResult
    cure_reconciliation: RemediationCureWriterView | None = None
    writer_context_digest: str = ""

def execute_curd_writer(
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
    extra_context: Mapping[str, object] | None = None,
    result_id: str | None = None,
) -> CurdWriterExecution:
    """Run one writer and normalize its result without dispatching review."""

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
    writer_context = context if extra_context is None else {**context, **extra_context}
    writer_context_digest = _canonical_digest(writer_context)
    writer_result_id = result_id or f"{plan.plan_id}/revision/{plan.revision}/result/{index}"
    outcome = _dispatch_writer_with_recovery(
        writer_context,
        host_evidence,
        plan=plan,
        curd=curd,
        index=index,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        provenance_refs=provenance_refs,
        allow_budget_recovery=phase == "cook",
        dispatch_writer=dispatch_writer,
    )
    recovery_execution = outcome.recovery_execution
    outcome_context_digest = _canonical_digest(outcome.context)
    if outcome.terminal_result is not None:
        if recovery_execution is not None:
            return attrs.evolve(
                recovery_execution,
                result=outcome.terminal_result,
                writer_context_digest=writer_context_digest,
            )
        reason = outcome.terminal_result.unresolved_work[0]
        writer_view = _blocked_writer_view(curd, reason)
        invocation = _result_invocation(
            plan,
            curd,
            index,
            evidence=outcome.host_evidence,
            deliverables={},
            provenance_refs=provenance_refs,
        )
        canonical = _normalize(writer_view, WriterViewKind.CURD_RESULT, invocation)
        return CurdWriterExecution(
            plan=plan,
            writer_view=writer_view,
            host_evidence=outcome.host_evidence,
            deliverables={},
            subject=_subject_artifact(writer_result_id, canonical, artifact_directory),
            result=outcome.terminal_result,
            cure_reconciliation=None,
            writer_context_digest=writer_context_digest,
        )
    output = outcome.output
    assert output is not None
    try:
        cure_reconciliation = None
        if phase == "cure":
            cure_reconciliation = _cure_writer_view(output)
            writer_view = cure_reconciliation.result
        else:
            writer_view = _writer_view(output)
        provisional, deliverables = _finalize_view(
            plan,
            curd,
            index,
            writer_view,
            result_id=writer_result_id,
            repository_root=repository_root,
            artifact_directory=artifact_directory,
            host_evidence=outcome.host_evidence,
            provenance_refs=provenance_refs,
        )
        subject = _subject_artifact(writer_result_id, provisional, artifact_directory)
        invocation = _result_invocation(
            plan,
            curd,
            index,
            evidence=outcome.host_evidence,
            deliverables=deliverables,
            provenance_refs=provenance_refs,
        )
        final = _normalize(writer_view, WriterViewKind.CURD_RESULT, invocation)
        assert isinstance(final.value, CurdResult)
    except Exception as error:
        if recovery_execution is None:
            raise
        reason = _failure_reason("writer retry output invalid", error)
        rows = tuple(
            attrs.evolve(row, reason=reason)
            if row.disposition is CriterionDisposition.BLOCKED
            else row
            for row in recovery_execution.result.criterion_results
        )
        preserved = attrs.evolve(
            recovery_execution.result,
            criterion_results=rows,
            unresolved_work=(reason, *recovery_execution.result.unresolved_work[1:]),
        )
        return attrs.evolve(
            recovery_execution,
            result=preserved,
            writer_context_digest=writer_context_digest,
        )
    return CurdWriterExecution(
        plan=plan,
        writer_view=writer_view,
        host_evidence=outcome.host_evidence,
        deliverables=deliverables,
        subject=subject,
        result=final.value,
        cure_reconciliation=cure_reconciliation,
        writer_context_digest=outcome_context_digest,
    )


def _materialize_checkpoint_execution(
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    checkpoint: WriterCheckpoint,
    *,
    repository_root: Path,
    artifact_directory: Path,
    host_evidence: dict[str, EvidenceRef],
    provenance_refs: tuple[str, ...],
    reason: str | None = None,
) -> CurdWriterExecution:
    """Retain validated checkpoint evidence before a recovery retry can mutate files."""
    writer_reason = reason or _failure_reason(
        "writer stopped at its budget", WriterBudgetExceeded(checkpoint)
    )
    writer_view = _checkpoint_writer_view(curd, writer_reason, checkpoint)
    result_id = f"{plan.plan_id}/revision/{plan.revision}/result/{index}"
    provisional, deliverables = _finalize_view(
        plan,
        curd,
        index,
        writer_view,
        result_id=result_id,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        host_evidence=host_evidence,
        provenance_refs=provenance_refs,
    )
    assert isinstance(provisional.value, CurdResult)
    return CurdWriterExecution(
        plan=plan,
        writer_view=writer_view,
        host_evidence=host_evidence,
        deliverables=deliverables,
        subject=_subject_artifact(result_id, provisional, artifact_directory),
        result=provisional.value,
        cure_reconciliation=None,
    )


@attrs.define(frozen=True, slots=True)
class _WriterRecoveryOutcome:
    """Result of writer dispatch and its bounded Cook recovery."""

    context: dict[str, object]
    host_evidence: dict[str, EvidenceRef]
    output: object | None = None
    recovery_overrun: WriterBudgetExceeded | None = None
    recovery_snapshot: CurdResult | None = None
    terminal_result: CurdResult | None = None
    recovery_execution: CurdWriterExecution | None = None


def _dispatch_writer_with_recovery(
    context: Mapping[str, object],
    host_evidence: dict[str, EvidenceRef],
    *,
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    repository_root: Path,
    artifact_directory: Path,
    provenance_refs: tuple[str, ...],
    allow_budget_recovery: bool,
    dispatch_writer: WriterDispatch,
) -> _WriterRecoveryOutcome:
    writer_context = dict(context)
    retried = False
    recovery_overrun: WriterBudgetExceeded | None = None
    recovery_snapshot: CurdResult | None = None
    recovery_execution: CurdWriterExecution | None = None

    def terminal(
        result: CurdResult,
        *,
        refs: tuple[str, ...] = provenance_refs,
    ) -> _WriterRecoveryOutcome:
        return _WriterRecoveryOutcome(
            context=writer_context,
            host_evidence=host_evidence,
            recovery_overrun=recovery_overrun,
            recovery_snapshot=recovery_snapshot,
            terminal_result=attrs.evolve(result, provenance_refs=refs),
            recovery_execution=recovery_execution,
        )

    def failed(
        label: str,
        error: Exception,
        *,
        refs: tuple[str, ...] = provenance_refs,
    ) -> _WriterRecoveryOutcome:
        reason = _failure_reason(label, error)
        if recovery_overrun is None:
            return terminal(
                _blocked_result(
                    plan,
                    curd,
                    index,
                    reason,
                    provenance_refs=refs,
                ),
                refs=refs,
            )
        if recovery_snapshot is not None:
            rows = tuple(
                attrs.evolve(row, reason=reason)
                if row.disposition is CriterionDisposition.BLOCKED
                else row
                for row in recovery_snapshot.criterion_results
            )
            return terminal(
                attrs.evolve(
                    recovery_snapshot,
                    criterion_results=rows,
                    unresolved_work=(reason, *recovery_snapshot.unresolved_work[1:]),
                ),
                refs=refs,
            )
        return terminal(
            _execute_overrun(
                plan,
                curd,
                index,
                recovery_overrun,
                repository_root=repository_root,
                artifact_directory=artifact_directory,
                host_evidence=host_evidence,
                provenance_refs=refs,
                failure_reason=reason,
            ),
            refs=refs,
        )

    while True:
        try:
            output = dispatch_writer(writer_context)
            return _WriterRecoveryOutcome(
                context=writer_context,
                host_evidence=host_evidence,
                output=output,
                recovery_overrun=recovery_overrun,
                recovery_snapshot=recovery_snapshot,
                recovery_execution=recovery_execution,
            )
        except WriterBudgetExceeded as overrun:
            if not allow_budget_recovery:
                try:
                    recovery_execution = _materialize_checkpoint_execution(
                        plan,
                        curd,
                        index,
                        overrun.checkpoint,
                        repository_root=repository_root,
                        artifact_directory=artifact_directory,
                        host_evidence=host_evidence,
                        provenance_refs=provenance_refs,
                    )
                except Exception:
                    recovery_execution = None
                if recovery_execution is not None:
                    return terminal(recovery_execution.result)
                return terminal(
                    _execute_overrun(
                        plan,
                        curd,
                        index,
                        overrun,
                        repository_root=repository_root,
                        artifact_directory=artifact_directory,
                        host_evidence=host_evidence,
                        provenance_refs=provenance_refs,
                    )
                )
            if retried:
                assert recovery_overrun is not None
                try:
                    latest = attrs.evolve(
                        overrun.checkpoint,
                        grounded=(
                            overrun.checkpoint.grounded
                            or recovery_overrun.checkpoint.grounded
                        ),
                    )
                    _ = _validate_budget_checkpoint(
                        plan=plan,
                        curd=curd,
                        index=index,
                        checkpoint=latest,
                        repository_root=repository_root,
                        host_evidence=host_evidence,
                    )
                    merged = _merge_budget_checkpoints(
                        recovery_overrun.checkpoint,
                        overrun.checkpoint,
                    )
                    _ = _checkpoint_writer_view(curd, merged.reason, merged)
                except Exception as error:
                    return failed("second budget checkpoint invalid", error)
                if recovery_snapshot is not None:
                    merged_reason = _failure_reason(
                        "writer stopped at its budget", WriterBudgetExceeded(merged)
                    )
                    rows = tuple(
                        attrs.evolve(row, reason=merged_reason)
                        if row.disposition is CriterionDisposition.BLOCKED
                        else row
                        for row in recovery_snapshot.criterion_results
                    )
                    return terminal(
                        attrs.evolve(
                            recovery_snapshot,
                            criterion_results=rows,
                            unresolved_work=(merged_reason, *merged.remaining),
                        )
                    )
                return terminal(
                    _execute_overrun(
                        plan,
                        curd,
                        index,
                        WriterBudgetExceeded(merged),
                        repository_root=repository_root,
                        artifact_directory=artifact_directory,
                        host_evidence=host_evidence,
                        provenance_refs=provenance_refs,
                    )
                )
            if overrun.checkpoint.grounded is None:
                try:
                    recovery_execution = _materialize_checkpoint_execution(
                        plan,
                        curd,
                        index,
                        overrun.checkpoint,
                        repository_root=repository_root,
                        artifact_directory=artifact_directory,
                        host_evidence=host_evidence,
                        provenance_refs=provenance_refs,
                    )
                except Exception:
                    recovery_execution = None
                if recovery_execution is not None:
                    return terminal(recovery_execution.result)
                return terminal(
                    _execute_overrun(
                        plan,
                        curd,
                        index,
                        overrun,
                        repository_root=repository_root,
                        artifact_directory=artifact_directory,
                        host_evidence=host_evidence,
                        provenance_refs=provenance_refs,
                    )
                )
            try:
                recovery_snapshot = _validate_budget_checkpoint(
                    plan=plan,
                    curd=curd,
                    index=index,
                    checkpoint=overrun.checkpoint,
                    repository_root=repository_root,
                    host_evidence=host_evidence,
                )
                writer_context = _recovery_context(
                    context,
                    plan=plan,
                    curd=curd,
                    checkpoint=overrun.checkpoint,
                    repository_root=repository_root,
                )
                recovery_execution = _materialize_checkpoint_execution(
                    plan,
                    curd,
                    index,
                    overrun.checkpoint,
                    repository_root=repository_root,
                    artifact_directory=artifact_directory,
                    host_evidence=host_evidence,
                    provenance_refs=provenance_refs,
                )
                recovery_snapshot = recovery_execution.result
            except Exception as error:
                return terminal(
                    _execute_overrun(
                        plan,
                        curd,
                        index,
                        overrun,
                        repository_root=repository_root,
                        artifact_directory=artifact_directory,
                        host_evidence=host_evidence,
                        provenance_refs=provenance_refs,
                        failure_reason=_failure_reason("wheypoint recovery failed", error),
                    )
                )
            recovery_overrun = overrun
            retried = True
        except Exception as error:
            return failed("writer callback failed", error)


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
    allow_budget_recovery: bool,
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

    outcome = _dispatch_writer_with_recovery(
        context,
        host_evidence,
        plan=plan,
        curd=curd,
        index=index,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        provenance_refs=provenance_refs,
        allow_budget_recovery=allow_budget_recovery,
        dispatch_writer=dispatch_writer,
    )
    host_evidence = outcome.host_evidence
    recovery_overrun = outcome.recovery_overrun
    recovery_snapshot = outcome.recovery_snapshot
    if outcome.terminal_result is not None:
        return None, outcome.terminal_result
    output = outcome.output
    assert output is not None

    def retry_failure(
        label: str,
        error: Exception,
        *,
        refs: tuple[str, ...] = provenance_refs,
    ) -> tuple[BranchResult | None, CurdResult]:
        reason = _failure_reason(label, error)
        if recovery_overrun is None:
            return None, _blocked_result(
                plan,
                curd,
                index,
                reason,
                provenance_refs=refs,
            )
        if recovery_snapshot is not None:
            rows = tuple(
                attrs.evolve(row, reason=reason)
                if row.disposition is CriterionDisposition.BLOCKED
                else row
                for row in recovery_snapshot.criterion_results
            )
            return None, attrs.evolve(
                recovery_snapshot,
                criterion_results=rows,
                unresolved_work=(reason, *recovery_snapshot.unresolved_work[1:]),
                provenance_refs=refs,
            )
        return None, _execute_overrun(
            plan,
            curd,
            index,
            recovery_overrun,
            repository_root=repository_root,
            artifact_directory=artifact_directory,
            host_evidence=host_evidence,
            provenance_refs=refs,
            failure_reason=reason,
        )

    try:
        writer_view = _writer_view(output)
    except Exception as error:
        return retry_failure("writer output invalid", error)

    result_id = f"{plan.plan_id}/revision/{plan.revision}/result/{index}"
    try:
        provisional, deliverables = _finalize_view(
            plan,
            curd,
            index,
            writer_view,
            result_id=result_id,
            repository_root=repository_root,
            artifact_directory=artifact_directory,
            host_evidence=host_evidence,
            provenance_refs=provenance_refs,
        )
        subject = _subject_artifact(
            result_id,
            provisional,
            artifact_directory,
        )
    except Exception as error:
        return retry_failure("writer output invalid", error)

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
        failed_ids = {
            row.criterion_id
            for row in writer_view.criterion_results
            if row.disposition is not CriterionDisposition.PASSED
        }
        failed = [
            criterion.description
            for criterion in curd.criteria
            if criterion.criterion_id in failed_ids
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
        provenance_refs=(*provenance_refs, runtime_ref),
    )
    try:
        final = _normalize(writer_view, WriterViewKind.CURD_RESULT, invocation)
    except Exception as error:
        return retry_failure(
            "result normalization failed",
            error,
            refs=(*provenance_refs, runtime_ref),
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
            raise TypeError(
                "cure diagnosis bindings must be CureDiagnosisBinding values"
            )
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
    selected_curd_ids: Sequence[str] | None = None,
) -> dict[str, CureDiagnosisBinding]:
    if curd_plan.digest != curd_plan_digest(curd_plan):
        raise ValueError("curd plan digest does not match its canonical content")
    normalized = _coerce_diagnosis_bindings(bindings)
    expected_plan = SourcePlanRef(
        curd_plan.plan_id,
        curd_plan.revision,
        curd_plan.digest,
    )
    # A partial cure binds one diagnosis per selected curd, so the expected
    # set is the dependency-closed selection, not the whole plan.
    selected = None if selected_curd_ids is None else set(selected_curd_ids)
    expected_curds = {
        curd.curd_id: curd
        for curd in curd_plan.curds
        if selected is None or curd.curd_id in selected
    }
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


def _selected_curds(
    curd_plan: CurdPlan,
    curd_ids: Sequence[str] | None,
) -> tuple[tuple[int, SemanticCurd], ...]:
    indexed = tuple(enumerate(curd_plan.curds, start=1))
    declared = {curd.curd_id: curd for _, curd in indexed}
    if curd_ids is None:
        selected_ids = set(declared)
    else:
        requested = tuple(curd_ids)
        if not requested:
            raise ContractValidationError("partial execution requires at least one curd ID")
        if len(set(requested)) != len(requested):
            raise ContractValidationError("partial execution must not repeat curd IDs")
        selected_ids = set(requested)
        unknown = selected_ids - declared.keys()
        if unknown:
            raise ContractValidationError(
                "partial execution names unknown curd IDs: " + ", ".join(sorted(unknown))
            )
    selected = tuple(
        (index, curd) for index, curd in indexed if curd.curd_id in selected_ids
    )
    for _, curd in selected:
        missing = set(curd.dependencies) - selected_ids
        if missing:
            raise ContractValidationError(
                f"partial execution for {curd.curd_id!r} omits dependencies: "
                + ", ".join(sorted(missing))
            )
    ordered: list[tuple[int, SemanticCurd]] = []
    remaining = {curd.curd_id: (index, curd) for index, curd in selected}
    completed: set[str] = set()
    while remaining:
        ready = sorted(
            (
                item
                for item in remaining.values()
                if set(item[1].dependencies) <= completed
            ),
            key=lambda item: item[0],
        )
        if not ready:
            raise ContractValidationError("curd plan dependencies contain a cycle")
        ordered.extend(ready)
        for _, curd in ready:
            completed.add(curd.curd_id)
            del remaining[curd.curd_id]
    return tuple(ordered)


def _execute_plan(
    curd_plan: CurdPlan,
    *,
    curd_ids: Sequence[str] | None,
    repository_root: str | Path,
    artifact_directory: str | Path,
    evidence: Mapping[str, EvidenceRef],
    phase: Literal["cook", "cure"],
    provenance_refs: tuple[str, ...],
    diagnosis_bindings: Mapping[str, CureDiagnosisBinding] | None,
    allow_budget_recovery: bool,
    dispatch_writer: WriterDispatch,
    dispatch_review: ReviewDispatch,
    dispatch_diagnosis: DiagnosisDispatch,
) -> ExecutionResults:
    branches: list[BranchResult] = []
    results: list[CurdResult] = []
    root = Path(repository_root)
    artifacts = Path(artifact_directory)
    selected = _selected_curds(curd_plan, curd_ids)
    if not selected:
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
            for index, curd in selected
        )
    for index, curd in selected:
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
            allow_budget_recovery=allow_budget_recovery,
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
    curd_ids: Sequence[str] | None = None,
) -> ExecutionResults:
    validated_plan = validate_curd_plan(curd_plan)
    return _execute_plan(
        validated_plan,
        curd_ids=curd_ids,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        evidence={} if evidence is None else evidence,
        phase="cook",
        provenance_refs=(),
        diagnosis_bindings=None,
        allow_budget_recovery=True,
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
    curd_ids: Sequence[str] | None = None,
) -> ExecutionResults:
    validated_plan = validate_curd_plan(curd_plan)
    # Resolve the dependency-closed selection first so a partial cure is
    # validated against the curds it will actually execute.
    selected = _selected_curds(validated_plan, curd_ids)
    normalized = _validate_cure_bindings(
        validated_plan,
        diagnosis_bindings,
        tuple(curd.curd_id for _, curd in selected),
    )
    return _execute_plan(
        validated_plan,
        curd_ids=curd_ids,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        evidence={} if evidence is None else evidence,
        phase="cure",
        provenance_refs=(),
        diagnosis_bindings=normalized,
        allow_budget_recovery=False,
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
    curd_ids: Sequence[str] | None = None,
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
        selected_for_cure = _selected_curds(validated_plan, curd_ids)
        normalized = _validate_cure_bindings(
            validated_plan,
            prevalidated,
            tuple(curd.curd_id for _, curd in selected_for_cure),
        )
    else:
        normalized = None
    branches, results = _execute_plan(
        validated_plan,
        curd_ids=curd_ids,
        repository_root=repository_root,
        artifact_directory=artifact_directory,
        evidence={} if evidence is None else evidence,
        phase=phase,
        provenance_refs=(),
        diagnosis_bindings=normalized,
        allow_budget_recovery=False,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis,
    )
    return planner_result, branches, results



# Public phase seams consumed by the Cook fan adapter.
resolve_plan_context = _resolve_plan_context
blocked_result = _blocked_result
blocked_writer_view = _blocked_writer_view
contract_version = _version
diagnosis = _diagnosis
evidence_values = _evidence_values
failure_reason = _failure_reason
review = _review
reviewed_result_view = _reviewed_result_view
result_invocation = _result_invocation
normalize = _normalize
subject_artifact = _subject_artifact
__all__ = [
    "CureDiagnosisBinding",
    "CureDiagnosisBindings",
    "CurdWriterExecution",
    "WriterBudgetExceeded",
    "WriterCheckpoint",
    "blocked_result",
    "blocked_writer_view",
    "contract_version",
    "diagnosis",
    "evidence_values",
    "failure_reason",
    "resolve_plan_context",
    "review",
    "reviewed_result_view",
    "result_invocation",
    "normalize",
    "subject_artifact",
    "bind_diagnosis",
    "cook",
    "cure",
    "execute_curd_writer",
    "plan",
    "run_workflow",
]
