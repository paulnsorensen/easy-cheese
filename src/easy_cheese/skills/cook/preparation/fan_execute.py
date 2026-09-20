"""Cook-only, Age, and Cure adapters for accepted fan handoffs."""
# This package adapter composes internal workflow phase primitives.
# pyright: reportPrivateUsage=false
from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import attrs

from easy_cheese_schemas import (
    ArtifactRef,
    BoundedScope,
    CurdPlan,
    CurdResult,
    CurdResultWriterView,
    CriterionDisposition,
    CriterionResultWriterView,
    DeliverableWriterView,
    canonical_bytes,
    DiagnosisDisposition,
    DiagnosisRequest,
    EvidenceKind,
    EvidenceRef,
    RemediationCureObservation,
    SourceLocation,
    RemediationScopeKey,
    RemediationScopeKind,
    SourcePlanRef,
    ReviewRequest,
    ReviewResult,
    SemanticCurd,
    WriterViewKind,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared import workflow
from easy_cheese.shared.fanout.run_fan import (
    CureDispatchOutcome,
    FanContext,
    FanExecutionOutcome,
    RemediationEventContext,
    ReviewDispatchOutcome,
    run_fan,
)
from easy_cheese.shared.fanout.remediation import PressGateResult, finding_key
from easy_cheese.shared.publication import atomic_write
from easy_cheese.shared.fanout.remediation_store import scope_state_path


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


def _path_component(value: str) -> str:
    """Encode opaque identifiers before using them as path components."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _contained_path(root: Path, target: Path) -> Path:
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    try:
        _ = resolved_target.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"remediation path escapes artifact root: {target}") from error
    return resolved_target


def _context_path(artifact_directory: Path, run_id: str, scope_id: str) -> Path:
    root = artifact_directory.resolve()
    return _contained_path(
        root,
        root / "remediation" / _path_component(run_id)
        / f"{_path_component(scope_id)}-context.json",
    )


def _manifest_path(artifact_directory: Path, run_id: str) -> Path:
    return _contained_path(
        artifact_directory.resolve(),
        artifact_directory.resolve() / "execution" / f"{_path_component(run_id)}-manifest.json",
    )


def _repository_identity(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return f"worktree:{repository_root.resolve()}"
    return f"commit:{completed.stdout.strip()}"


def _path_ref(path: Path, *, artifact_id: str, role: str) -> ArtifactRef:
    raw = path.read_bytes()
    return ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=path.resolve().as_uri(),
        digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        size_bytes=len(raw),
        media_type="application/json",
    )


def _persist_runtime_ref(artifact_directory: Path, run_id: str, name: str, role: str, value: object) -> ArtifactRef:
    raw = canonical_bytes(value)
    path = _contained_path(
        artifact_directory.resolve(),
        artifact_directory.resolve() / "remediation" / _path_component(run_id)
        / _path_component(role) / f"{_path_component(name)}.json",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, raw)
    return ArtifactRef(
        artifact_id=name, role=role, uri=path.resolve().as_uri(),
        digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        size_bytes=len(raw), media_type="application/json",
    )


def _validate_manifest_ref(root: Path, ref: ArtifactRef) -> None:
    path = Path(ref.uri.removeprefix("file://"))
    if not path.resolve().is_relative_to(root.resolve()):
        raise ContractValidationError("checkpoint manifest reference escapes artifact root")
    raw = path.read_bytes()
    if len(raw) != ref.size_bytes or hashlib.sha256(raw).hexdigest() != ref.digest.removeprefix("sha256:"):
        raise ContractValidationError(f"checkpoint artifact digest mismatch: {ref.artifact_id}")
    if ref.media_type != "application/json":
        raise ContractValidationError("checkpoint artifact media type mismatch")


def _load_checkpoint_manifest(artifact_directory: Path, run_id: str, plan: CurdPlan, repository_root: Path) -> tuple[ArtifactRef, ...]:
    path = _manifest_path(artifact_directory, run_id)
    if not path.exists():
        return ()
    payload = _json_object(cast(object, json.loads(path.read_text())), "checkpoint manifest must be an object")
    if payload.get("run_id") != run_id or payload.get("plan_id") != plan.plan_id or payload.get("plan_digest") != plan.digest:
        raise ContractValidationError("checkpoint manifest identity mismatch")
    if payload.get("repository_identity") != _repository_identity(repository_root):
        raise ContractValidationError("checkpoint manifest repository identity mismatch")
    references = _json_list(payload.get("references"), "checkpoint manifest references must be a list")
    marker = payload.get("commit_marker")
    expected_marker = hashlib.sha256(canonical_bytes(references)).hexdigest()
    if marker != expected_marker:
        raise ContractValidationError("checkpoint manifest commit marker mismatch")
    validated: list[ArtifactRef] = []
    for raw in references:
        ref = _artifact_from_json(raw)
        _validate_manifest_ref(artifact_directory, ref)
        validated.append(ref)
    return tuple(validated)


def _write_checkpoint_manifest(
    artifact_directory: Path, run_id: str, plan: CurdPlan, repository_root: Path,
    refs: Sequence[ArtifactRef],
) -> ArtifactRef:
    unique = {ref.artifact_id: ref for ref in refs}
    payload = {
        "run_id": run_id,
        "plan_id": plan.plan_id,
        "plan_revision": plan.revision,
        "plan_digest": plan.digest,
        "repository_identity": _repository_identity(repository_root),
        "references": tuple(unique.values()),
    }
    payload["commit_marker"] = hashlib.sha256(canonical_bytes(payload["references"])).hexdigest()
    path = _manifest_path(artifact_directory, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, canonical_bytes(payload))
    return _path_ref(path, artifact_id=f"{run_id}/checkpoint-manifest", role="checkpoint-manifest")


def _json_object(value: object, message: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(message)
    return cast(dict[str, object], value)


def _json_list(value: object, message: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(message)
    return cast(list[object], value)


def _json_int(value: object, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(message)
    return value


def _writer_view_from_json(value: object) -> CurdResultWriterView:
    payload = _json_object(value, "writer context view must be an object")
    rows = _json_list(payload.get("criterion_results"), "writer context criteria must be a list")
    criteria = tuple(
        CriterionResultWriterView(
            str(row["criterion_id"]),
            CriterionDisposition(str(row["disposition"])),
            tuple(str(item) for item in _json_list(row.get("evidence_keys", []), "criterion evidence must be a list")),
            cast(str | None, row.get("reason")),
        )
        for row_value in rows
        for row in (_json_object(row_value, "criterion result must be an object"),)
    )
    deliverables = tuple(
        DeliverableWriterView(
            str(row["role"]), str(row["path"]), str(row["media_type"])
        )
        for row_value in _json_list(payload.get("deliverables", []), "deliverables must be a list")
        for row in (_json_object(row_value, "deliverable must be an object"),)
    )
    return CurdResultWriterView(
        criterion_results=criteria,
        deliverables=deliverables,
        unresolved_work=tuple(str(item) for item in _json_list(payload.get("unresolved_work", []), "unresolved work must be a list")),
    )


def _artifact_from_json(value: object) -> ArtifactRef:
    payload = _json_object(value, "artifact reference must be an object")
    schema_uri = payload.get("schema_uri")
    if schema_uri is not None and not isinstance(schema_uri, str):
        raise ValueError("artifact schema URI must be a string")
    return ArtifactRef(
        artifact_id=str(payload["artifact_id"]), role=str(payload["role"]),
        uri=str(payload["uri"]), digest=str(payload["digest"]),
        size_bytes=_json_int(payload["size_bytes"], "artifact size must be an integer"), media_type=str(payload["media_type"]),
        schema_uri=schema_uri,
    )


def _evidence_from_json(value: object) -> EvidenceRef:
    payload = _json_object(value, "evidence reference must be an object")
    location_value = payload.get("location")
    location = None
    if location_value is not None:
        location_payload = _json_object(location_value, "evidence location must be an object")
        start_column = location_payload.get("start_column")
        end_column = location_payload.get("end_column")
        if start_column is not None and not isinstance(start_column, int):
            raise ValueError("evidence start column must be an integer")
        if end_column is not None and not isinstance(end_column, int):
            raise ValueError("evidence end column must be an integer")
        location = SourceLocation(
            artifact_id=str(location_payload["artifact_id"]),
            path=str(location_payload["path"]),
            start_line=_json_int(location_payload["start_line"], "evidence start line must be an integer"),
            start_column=start_column,
            end_line=_json_int(location_payload["end_line"], "evidence end line must be an integer"),
            end_column=end_column,
        )
    summary = payload.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("evidence summary must be a string")
    return EvidenceRef(
        evidence_id=str(payload["evidence_id"]),
        kind=EvidenceKind(str(payload["kind"])),
        artifact=_artifact_from_json(payload["artifact"]),
        location=location,
        summary=summary,
    )


def _press_result_from_json(value: object) -> PressGateResult:
    payload = _json_object(value, "persisted Press result must be an object")
    failures_value = payload.get("new_failures", [])
    evidence_value = payload.get("evidence", [])
    if not isinstance(failures_value, list) or not isinstance(evidence_value, list):
        raise ValueError("persisted Press result fields are invalid")
    failures = cast(list[object], failures_value)
    evidence = cast(list[object], evidence_value)
    scope_value = payload.get("scope")
    scope = None
    if scope_value is not None:
        scope_payload = _json_object(scope_value, "Press scope must be an object")
        scope = RemediationScopeKey(
            run_id=str(scope_payload["run_id"]),
            source_plan_ref=SourcePlanRef(
                plan_id=str(_json_object(scope_payload["source_plan_ref"], "Press plan must be an object")["plan_id"]),
                revision=_json_int(_json_object(scope_payload["source_plan_ref"], "Press plan must be an object")["revision"], "Press plan revision must be an integer"),
                digest=str(_json_object(scope_payload["source_plan_ref"], "Press plan must be an object")["digest"]),
            ),
            scope_kind=RemediationScopeKind(str(scope_payload["scope_kind"])),
            scope_id=str(scope_payload["scope_id"]),
        )
    gate_round = payload.get("gate_round")
    if gate_round is not None:
        gate_round = _json_int(gate_round, "Press gate round must be an integer")
    return PressGateResult(
        passed=bool(payload["passed"]),
        baseline_id=str(payload["baseline_id"]),
        new_failures=tuple(str(item) for item in failures),
        evidence=tuple(_evidence_from_json(item) for item in evidence),
        scope=scope,
        gate_round=gate_round,
    )


def _load_persisted_press_results(artifact_directory: Path, run_id: str) -> tuple[PressGateResult, ...]:
    root = _contained_path(
        artifact_directory.resolve(),
        artifact_directory.resolve() / "remediation" / _path_component(run_id) / _path_component("press-result"),
    )
    if not root.exists():
        return ()
    values: list[PressGateResult] = []
    for path in root.glob("*.json"):
        values.append(_press_result_from_json(cast(object, json.loads(path.read_text()))))
    if any(value.scope is None or value.gate_round is None for value in values):
        raise ContractValidationError("persisted Press envelope lacks scope identity or gate round")
    rounds = [cast(int, value.gate_round) for value in values]
    if len(set(rounds)) != len(rounds) or sorted(rounds) != list(range(1, len(rounds) + 1)):
        raise ContractValidationError("persisted Press gate rounds are not unique and sequential")
    return tuple(sorted(values, key=lambda value: cast(int, value.gate_round)))




def _persist_scope_context(
    artifact_directory: Path, run_id: str, scope_id: str,
    *, index: int, writer: workflow.CurdWriterExecution,
    writer_view: CurdResultWriterView, result: CurdResult, subject: ArtifactRef,
    latest_review: ReviewResult | None,
) -> None:
    payload = {
        "scope_id": scope_id,
        "index": index,
        "writer_view": writer_view,
        "host_evidence": tuple(writer.host_evidence.values()),
        "deliverables": tuple(writer.deliverables.values()),
        "subject": subject,
        "result": result,
        "latest_review": latest_review,
        "writer_context_digest": writer.writer_context_digest,
    }
    path = _context_path(artifact_directory, run_id, scope_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, canonical_bytes(payload))


def _validate_contract_value(value: object, contract: type) -> object:
    version = supported_version_for(contract)
    if version is None:
        raise ContractValidationError(f"{contract.__name__} has no supported version")
    loaded = validate_contract(
        json.dumps(value, sort_keys=True).encode(), contract, version
    )
    return loaded.value


def _load_scope_context(
    artifact_directory: Path, run_id: str, plan: CurdPlan,
    curd: SemanticCurd, index: int,
) -> _ScopeExecution | None:
    path = _context_path(artifact_directory, run_id, curd.curd_id)
    if not path.exists():
        return None
    try:
        payload = _json_object(cast(object, json.loads(path.read_text())), "persisted scope context must be an object")
        if payload.get("scope_id") != curd.curd_id or _json_int(payload.get("index"), "persisted scope index must be an integer") != index:
            raise ValueError("persisted scope context does not match the plan")
        result = cast(CurdResult, _validate_contract_value(payload["result"], CurdResult))
        latest_raw = payload.get("latest_review")
        latest = None if latest_raw is None else cast(ReviewResult, _validate_contract_value(latest_raw, ReviewResult))
        evidence = {
            item.evidence_id: item
            for item in (_evidence_from_json(value) for value in _json_list(payload["host_evidence"], "host evidence must be a list"))
        }
        deliverables = {
            item.artifact_id: item
            for item in (_artifact_from_json(value) for value in _json_list(payload["deliverables"], "deliverables must be a list"))
        }
        subject = _artifact_from_json(payload["subject"])
        writer_view = _writer_view_from_json(payload["writer_view"])
        writer = workflow.CurdWriterExecution(
            plan=plan, writer_view=writer_view, host_evidence=evidence,
            deliverables=deliverables, subject=subject, result=result,
            writer_context_digest=str(payload.get("writer_context_digest", "")),
        )
        return _ScopeExecution(curd, index, writer, writer_view, result, subject, latest)
    except (KeyError, TypeError, ValueError, OSError, ContractValidationError) as error:
        raise ValueError(f"invalid persisted fan context {path}: {error}") from error


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
    results: Mapping[str, CurdResult] | None = None,
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
    run_id = execution_id or f"{plan.plan_id}-execution"
    committed_refs = list(_load_checkpoint_manifest(artifacts, run_id, plan, root))
    if results and not _manifest_path(artifacts, run_id).exists():
        raise ContractValidationError("accepted results require a checkpoint manifest")
    journal_path = _contained_path(
        artifacts.resolve(),
        artifacts.resolve() / "execution" / f"{_path_component(run_id)}.json",
    )

    def checkpoint_manifest() -> None:
        refs = list(committed_refs)
        if journal_path.exists():
            journal_ref = _path_ref(journal_path, artifact_id=f"{run_id}/results", role="curd-results")
            refs = [item for item in refs if item.artifact_id != journal_ref.artifact_id]
            refs.append(journal_ref)
        _ = _write_checkpoint_manifest(artifacts, run_id, plan, root, refs)

    checkpoint_manifest()
    journal_results: dict[str, CurdResult] = dict(results or {})
    def persist_result(result: CurdResult) -> None:
        journal_results[result.source_curd_ref.curd_id] = result
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(journal_path, canonical_bytes({"request_id": run_id, "results": tuple(journal_results.values())}))
        checkpoint_manifest()
    if results is not None:
        for result in results.values():
            journal_results[result.source_curd_ref.curd_id] = result
    scopes: dict[str, _ScopeExecution] = {}
    for curd in plan.curds:
        if results is None or curd.curd_id not in results:
            continue
        restored = _load_scope_context(
            artifacts, run_id, plan, curd, indexed[curd.curd_id]
        )
        if restored is None:
            raise ContractValidationError(
                f"accepted result {curd.curd_id} has no matching adapter context"
            )
        scopes[curd.curd_id] = restored
    postmerge: _PostmergeExecution | None = None
    if scopes and _context_path(artifacts, run_id, "postmerge").exists():
        aggregate = _aggregate_curd(plan, scopes)
        restored = _load_scope_context(artifacts, run_id, plan, aggregate, 1)
        if restored is not None:
            postmerge = _PostmergeExecution(
                curd=aggregate, writer=restored.writer,
                latest_review=restored.latest_review,
            )
    persisted_press = _load_persisted_press_results(artifacts, run_id)
    latest_postmerge_gate_evidence: list[EvidenceRef] = list(
        persisted_press[-1].evidence if persisted_press else ()
    )
    postmerge_gate_evidence: list[EvidenceRef] = [
        item for gate in persisted_press for item in gate.evidence
    ]
    press_refs: list[ArtifactRef] = []

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
        _persist_scope_context(
            artifacts, run_id, curd.curd_id, index=indexed[curd.curd_id],
            writer=writer, writer_view=writer.writer_view,
            result=writer.result, subject=writer.subject, latest_review=None,
        )
        if _load_scope_context(artifacts, run_id, plan, curd, indexed[curd.curd_id]) is None:
            raise ContractValidationError(
                f"Cook context failed validation for {curd.curd_id}"
            )
        # Publish the result only after its validated adapter context exists.
        persist_result(writer.result)
        return writer.result

    def press_adapter(
        scope: RemediationScopeKey, gate_round: int
    ) -> PressGateResult:
        if dispatch_press is None:
            raise RuntimeError("postmerge Press dispatcher is required")
        value = dispatch_press(scope, gate_round)
        value = attrs.evolve(value, scope=scope, gate_round=gate_round)
        press_refs.append(_persist_runtime_ref(
            artifacts, run_id, f"{scope.scope_id}-press-{gate_round}", "press-result", value,
        ))
        if scope.scope_id == "postmerge":
            latest_postmerge_gate_evidence[:] = value.evidence
            known = {item.evidence_id for item in postmerge_gate_evidence}
            postmerge_gate_evidence.extend(
                item for item in value.evidence if item.evidence_id not in known
            )
        return value

    def age_adapter(event: RemediationEventContext) -> ReviewDispatchOutcome:
        scope = event.scope
        review_round = event.round_number
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
            _persist_scope_context(
                artifacts, run_id, "postmerge", index=1,
                writer=postmerge.writer, writer_view=postmerge.writer.writer_view,
                result=postmerge.writer.result, subject=subject, latest_review=review,
            )
            return ReviewDispatchOutcome(
                result=review,
                request_digest=f"sha256:{hashlib.sha256(canonical_bytes(request)).hexdigest()}",
            )
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
        state.writer = attrs.evolve(
            state.writer, writer_view=state.writer_view,
            result=state.result, subject=state.subject,
        )
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
        _persist_scope_context(
            artifacts, run_id, scope.scope_id, index=state.index,
            writer=state.writer, writer_view=state.writer_view,
            result=state.result, subject=state.subject, latest_review=review,
        )
        return ReviewDispatchOutcome(
            result=review,
            request_digest=f"sha256:{hashlib.sha256(canonical_bytes(request)).hexdigest()}",
        )

    def cure_adapter(event: RemediationEventContext) -> CureDispatchOutcome:
        scope = event.scope
        locked_selection = event.locked_selection
        cure_round = event.round_number
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
                observation = _cure_observation((), locked_selection)
                return CureDispatchOutcome(
                    observation=observation,
                    request_digest=_cure_request_digest(request, diagnosis, postmerge.writer, scope, locked_selection, cure_round),
                )
            request_digest = _cure_request_digest(request, diagnosis, postmerge.writer, scope, locked_selection, cure_round)
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
            subject_evidence = _subject_evidence(writer)
            writer.host_evidence[subject_evidence.evidence_id] = subject_evidence
            _persist_scope_context(
                artifacts, run_id, "postmerge", index=1,
                writer=writer, writer_view=writer.writer_view,
                result=writer.result, subject=writer.subject,
                latest_review=postmerge.latest_review,
            )
            applied, deferred, reverted = _declared_cure_partition(
                writer, locked_selection
            )
            observation = _cure_observation(
                applied,
                deferred,
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
                reverted_finding_keys=reverted,
            )
            return CureDispatchOutcome(
                observation=observation,
                request_digest=request_digest,
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
            observation = _cure_observation((), locked_selection)
            return CureDispatchOutcome(
                observation=observation,
                request_digest=_cure_request_digest(request, diagnosis, state.writer, scope, locked_selection, cure_round),
            )
        binding = workflow.bind_diagnosis(plan, state.curd, diagnosis)
        request_digest = _cure_request_digest(request, diagnosis, state.writer, scope, locked_selection, cure_round)
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
        _persist_scope_context(
            artifacts, run_id, scope.scope_id, index=state.index,
            writer=writer, writer_view=state.writer_view,
            result=state.result, subject=state.subject,
            latest_review=state.latest_review,
        )
        applied, deferred, reverted = _declared_cure_partition(
            writer, locked_selection
        )
        observation = _cure_observation(
            applied,
            deferred,
            touched_paths=tuple(writer.deliverables),
            gate_evidence=tuple(writer.host_evidence.values()),
            reverted_finding_keys=reverted,
        )
        return CureDispatchOutcome(
            observation=observation,
            request_digest=request_digest,
        )

    context = FanContext(
        run_id=execution_id or f"{plan.plan_id}-execution",
        artifact_directory=artifacts,
        cook=cook_adapter,
        age=age_adapter,
        cure=cure_adapter,
        press=press_adapter if dispatch_press is not None else None,
        result_sink=persist_result,
        checkpoint_sink=checkpoint_manifest,
    )
    outcome = run_fan(plan, context, selected=selected, results=results)
    refs: list[ArtifactRef] = list(press_refs)
    journal_path = _contained_path(
        artifacts.resolve(),
        artifacts.resolve() / "execution" / f"{_path_component(run_id)}.json",
    )
    if journal_path.exists():
        refs.append(_path_ref(journal_path, artifact_id=f"{run_id}/results", role="curd-results"))
    for scope_id, state in outcome.scope_states.items():
        state_path = scope_state_path(artifacts, state.scope)
        refs.append(_path_ref(state_path, artifact_id=f"{run_id}/{scope_id}/state", role="remediation-state"))
        context_path = _context_path(artifacts, run_id, scope_id)
        if context_path.exists():
            refs.append(_path_ref(context_path, artifact_id=f"{run_id}/{scope_id}/context", role="adapter-context"))
    refs.extend(outcome.stop_evidence_refs)
    if outcome.remediation_request_ref is not None:
        refs.append(outcome.remediation_request_ref)
    _ = _write_checkpoint_manifest(artifacts, run_id, plan, root, refs)
    return outcome


def _cure_request_digest(
    request: DiagnosisRequest,
    diagnosis: object,
    writer: workflow.CurdWriterExecution,
    scope: RemediationScopeKey,
    locked_selection: tuple[str, ...],
    round_number: int,
) -> str:
    envelope = {
        "diagnosis_request": request,
        "diagnosis_result": diagnosis,
        "writer_context_digest": writer.writer_context_digest,
        "scope": scope,
        "locked_selection": locked_selection,
        "round": round_number,
    }
    return f"sha256:{hashlib.sha256(canonical_bytes(envelope)).hexdigest()}"


def _declared_cure_partition(
    writer: workflow.CurdWriterExecution, locked_selection: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    declaration = writer.cure_reconciliation
    if declaration is None:
        raise ValueError("Cure writer must declare finding reconciliation")
    applied = tuple(declaration.applied_finding_keys)
    deferred = tuple(declaration.deferred_finding_keys)
    reverted = tuple(declaration.reverted_finding_keys)
    selected = set(locked_selection)
    if set(applied) & set(deferred) or set(applied) | set(deferred) != selected:
        raise ValueError("Cure writer result must partition the locked selection")
    if not set(reverted) <= selected:
        raise ValueError("Cure writer result reverted keys must be selected")
    return applied, deferred, reverted


def _aggregate_subject(
    plan: CurdPlan, scopes: Mapping[str, _ScopeExecution], artifact_directory: Path
) -> tuple[ArtifactRef, tuple[EvidenceRef, ...]]:
    payload = {
        "plan_id": plan.plan_id,
        "revision": plan.revision,
        "results": [state.result for state in scopes.values()],
    }
    raw = canonical_bytes(payload)
    root = artifact_directory.resolve()
    path = _contained_path(
        root,
        root / "remediation" / _path_component(plan.plan_id)
        / "postmerge-subject.json",
    )
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
    reverted_finding_keys: tuple[str, ...] = (),
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
        reverted_finding_keys=reverted_finding_keys,
    )