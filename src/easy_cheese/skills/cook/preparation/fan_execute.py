"""Cook-only phase adapters for accepted fan handoffs.

The checkpoint manifest detects corruption in persisted references; it does not
provide tamper resistance.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlsplit

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
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    load_agent_writer_view,
)
from easy_cheese.shared import workflow
from easy_cheese.shared.fanout.run_fan import (
    CureDispatchOutcome,
    FanContext,
    FanExecutionOutcome,
    PressDispatcher,
    RemediationEventContext,
    ReviewDispatchOutcome,
    run_fan_locked,
)
from easy_cheese.shared.fanout.press_types import PressGateResult
from easy_cheese.shared.fanout.remediation import finding_key
from easy_cheese.shared.artifacts import resolve_file_path, restrict_local_path
from easy_cheese.shared.bounded_read import read_bounded_file
from easy_cheese.shared.fanout.remediation_store import run_lock
from easy_cheese.shared.fanout.remediation_store import scope_state_path
from easy_cheese.shared.git_utils import run_git
from easy_cheese.shared.publication import atomic_write
from easy_cheese.shared.remediation_artifacts import (
    REMEDIATION_STATE_ROLE,
    build_artifact_ref,
    bytes_digest,
    contained_path as _contained_path,
    path_component as _path_component,
)


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


@attrs.define
class _FanAdapters:
    """Host-owned Cook, Press, Age, and Cure adapters for one fan run."""

    plan: CurdPlan
    root: Path
    artifacts: Path
    indexed: Mapping[str, int]
    shared_inputs: tuple[object, ...]
    resolved_evidence: Mapping[str, object]
    durable_evidence: Mapping[str, EvidenceRef]
    run_id: str
    dispatch_writer: workflow.WriterDispatch
    dispatch_review: workflow.ReviewDispatch
    dispatch_diagnosis: workflow.DiagnosisDispatch
    dispatch_press: PressDispatcher | None
    committed_refs: list[ArtifactRef]
    journal_path: Path
    journal_results: dict[str, CurdResult]
    press_refs: list[ArtifactRef] = attrs.field(factory=list)
    scopes: dict[str, _ScopeExecution] = attrs.field(factory=dict)
    aggregate_curd: SemanticCurd | None = None
    postmerge: _PostmergeExecution | None = None
    latest_postmerge_gate_evidence: list[EvidenceRef] = attrs.field(factory=list)
    postmerge_gate_evidence: list[EvidenceRef] = attrs.field(factory=list)

    def checkpoint_manifest(self) -> None:
        refs = [*self.committed_refs, *self.press_refs]
        if self.journal_path.exists():
            journal_ref = _path_ref(
                self.journal_path, artifact_id=f"{self.run_id}/results",
                role="curd-results",
            )
            refs = [item for item in refs if item.artifact_id != journal_ref.artifact_id]
            refs.append(journal_ref)
        _ = _write_checkpoint_manifest(
            self.artifacts, self.run_id, self.plan, self.root, refs
        )

    def persist_result(self, result: CurdResult) -> None:
        self.journal_results[result.source_curd_ref.curd_id] = result
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(
            self.journal_path,
            canonical_bytes({
                "request_id": self.run_id,
                "results": tuple(self.journal_results.values()),
            }),
        )
        self.checkpoint_manifest()

    def cook(self, curd: SemanticCurd) -> CurdResult:
        try:
            writer = workflow.execute_curd_writer(
                self.plan, curd, self.indexed[curd.curd_id],
                repository_root=self.root, artifact_directory=self.artifacts,
                resolved_evidence=self.resolved_evidence,
                durable_evidence=self.durable_evidence,
                shared_inputs=self.shared_inputs, phase="cook",
                provenance_refs=(), dispatch_writer=self.dispatch_writer,
            )
        except Exception as error:
            return workflow.blocked_result(
                self.plan, curd, self.indexed[curd.curd_id],
                workflow.failure_reason("fan Cook writer failed", error),
                provenance_refs=(),
            )
        subject_evidence = _subject_evidence(writer)
        writer.host_evidence[subject_evidence.evidence_id] = subject_evidence
        self.scopes[curd.curd_id] = _ScopeExecution(
            curd, self.indexed[curd.curd_id], writer, writer.writer_view,
            writer.result, writer.subject,
        )
        _persist_scope_context(
            self.artifacts, self.run_id, curd.curd_id,
            index=self.indexed[curd.curd_id], writer=writer,
            writer_view=writer.writer_view, result=writer.result,
            subject=writer.subject, latest_review=None,
        )
        if _load_scope_context(
            self.artifacts, self.run_id, self.plan, curd,
            self.indexed[curd.curd_id],
        ) is None:
            raise ContractValidationError(
                f"Cook context failed validation for {curd.curd_id}"
            )
        self.persist_result(writer.result)
        return writer.result

    def press(self, scope: RemediationScopeKey, gate_round: int) -> PressGateResult:
        if self.dispatch_press is None:
            raise RuntimeError("postmerge Press dispatcher is required")
        value = attrs.evolve(
            self.dispatch_press(scope, gate_round),
            scope=scope, gate_round=gate_round,
        )
        self.press_refs.append(_persist_runtime_ref(
            self.artifacts, self.run_id, f"{scope.scope_id}-press-{gate_round}",
            "press-result", value,
        ))
        if scope.scope_kind is RemediationScopeKind.POSTMERGE:
            if not self.latest_postmerge_gate_evidence:
                self.latest_postmerge_gate_evidence[:] = value.evidence
            known = {item.evidence_id for item in self.postmerge_gate_evidence}
            self.postmerge_gate_evidence.extend(
                item for item in value.evidence if item.evidence_id not in known
            )
        self.checkpoint_manifest()
        return value

    def age(self, event: RemediationEventContext) -> ReviewDispatchOutcome:
        scope, review_round = event.scope, event.round_number
        if scope.scope_kind is RemediationScopeKind.POSTMERGE:
            if self.aggregate_curd is None:
                self.aggregate_curd = _aggregate_curd(self.plan, self.scopes)
            if self.postmerge is None:
                subject, evidence_values = _aggregate_subject(
                    self.plan, self.run_id, self.aggregate_curd,
                    self.scopes, self.artifacts,
                )
            else:
                subject = self.postmerge.writer.subject
                evidence_values = workflow.evidence_values(
                    self.postmerge.writer.host_evidence
                )
            evidence_values = workflow.evidence_values({
                item.evidence_id: item
                for item in (*evidence_values, *self.latest_postmerge_gate_evidence)
            })
            request = ReviewRequest(
                contract_version=workflow.contract_version(ReviewRequest),
                review_id=(
                    f"{self.plan.plan_id}/revision/{self.plan.revision}/"
                    f"postmerge/review/{review_round}"
                ),
                subject=subject,
                coverage_targets=[
                    criterion.criterion_id
                    for curd in self.plan.curds for criterion in curd.criteria
                ],
                evidence=evidence_values,
            )
            review = workflow.review(
                request, self.dispatch_review(request),
                {item.evidence_id: item for item in request.evidence},
            )
            if self.postmerge is None:
                self.postmerge = _PostmergeExecution(
                    curd=self.aggregate_curd,
                    writer=workflow.CurdWriterExecution(
                        plan=self.plan,
                        writer_view=workflow.blocked_writer_view(
                            self.aggregate_curd, "postmerge review pending"
                        ),
                        host_evidence={
                            item.evidence_id: item for item in request.evidence
                        },
                        deliverables={}, subject=subject,
                        result=next(iter(self.scopes.values())).result,
                    ),
                    latest_review=review,
                )
            else:
                self.postmerge.latest_review = review
            _persist_scope_context(
                self.artifacts, self.run_id, "postmerge",
                scope_kind=scope.scope_kind, index=1,
                writer=self.postmerge.writer,
                writer_view=self.postmerge.writer.writer_view,
                result=self.postmerge.writer.result, subject=subject,
                latest_review=review,
            )
            return ReviewDispatchOutcome(
                result=review,
                request_digest=f"sha256:{hashlib.sha256(canonical_bytes(request)).hexdigest()}",
            )
        state = self.scopes.get(scope.scope_id)
        if state is None:
            raise RuntimeError(f"Age requested before Cook for {scope.scope_id}")
        request = ReviewRequest(
            contract_version=workflow.contract_version(ReviewRequest),
            review_id=(
                f"{self.plan.plan_id}/revision/{self.plan.revision}/result/"
                f"{state.index}/review/{review_round}"
            ),
            subject=state.subject,
            coverage_targets=[item.criterion_id for item in state.curd.criteria],
            evidence=workflow.evidence_values(state.writer.host_evidence),
        )
        review = workflow.review(
            request, self.dispatch_review(request),
            {item.evidence_id: item for item in request.evidence},
        )
        state.writer_view = workflow.reviewed_result_view(state.writer_view, review)
        state.result, state.subject = _refresh_result(state, review, self.artifacts)
        state.writer = attrs.evolve(
            state.writer, writer_view=state.writer_view,
            result=state.result, subject=state.subject,
        )
        subject_evidence = EvidenceRef(
            evidence_id=f"{state.result.result_id}/subject-evidence",
            kind=EvidenceKind.RUNTIME, artifact=state.subject,
        )
        state.writer.host_evidence[subject_evidence.evidence_id] = subject_evidence
        state.latest_review = review
        for finding in review.findings:
            for item in finding.evidence:
                state.writer.host_evidence[item.evidence_id] = item
        _persist_scope_context(
            self.artifacts, self.run_id, scope.scope_id, index=state.index,
            writer=state.writer, writer_view=state.writer_view,
            result=state.result, subject=state.subject, latest_review=review,
        )
        return ReviewDispatchOutcome(
            result=review,
            request_digest=f"sha256:{hashlib.sha256(canonical_bytes(request)).hexdigest()}",
        )

    def cure(self, event: RemediationEventContext) -> CureDispatchOutcome:
        scope, locked_selection, cure_round = (
            event.scope, event.locked_selection, event.round_number
        )
        if scope.scope_kind is RemediationScopeKind.POSTMERGE:
            if self.postmerge is None or self.postmerge.latest_review is None:
                raise RuntimeError("Cure requested before postmerge Age")
            writer_state: _ScopeExecution | _PostmergeExecution = self.postmerge
            curd, index, subject = self.postmerge.curd, 1, self.postmerge.writer.subject
            diagnosis_id = (
                f"{self.plan.plan_id}/revision/{self.plan.revision}/"
                f"postmerge/diagnosis/{cure_round}"
            )
            findings = self.postmerge.latest_review.findings
            symptom = "Postmerge findings require cure: " + "; ".join(
                f"{finding.finding_id}: {finding.summary}"
                for finding in findings if finding_key(finding) in locked_selection
            )
            extra_context: Mapping[str, object] | None = {
                "aggregate_subject": subject,
                "locked_selection": locked_selection,
                "normalized_review": self.postmerge.latest_review,
                "plan_results": tuple(item.result for item in self.scopes.values()),
            }
            result_id = (
                f"{self.plan.plan_id}/revision/{self.plan.revision}/postmerge-result"
            )
        else:
            state = self.scopes.get(scope.scope_id)
            if state is None:
                raise RuntimeError(f"Cure requested before Cook for {scope.scope_id}")
            writer_state, curd, index, subject = state, state.curd, state.index, state.subject
            diagnosis_id = (
                f"{self.plan.plan_id}/revision/{self.plan.revision}/result/"
                f"{state.index}/diagnosis/{cure_round}"
            )
            findings = state.latest_review.findings if state.latest_review else ()
            symptom = "Review findings require cure: " + "; ".join(
                f"{finding.finding_id}: {finding.summary}"
                for finding in findings if finding_key(finding) in locked_selection
            )
            extra_context, result_id = None, None
        request = DiagnosisRequest(
            contract_version=workflow.contract_version(DiagnosisRequest),
            diagnosis_id=diagnosis_id, symptom=symptom, subject=subject,
            evidence=workflow.evidence_values(writer_state.writer.host_evidence),
        )
        diagnosis = workflow.diagnosis(
            request, self.dispatch_diagnosis(request),
            {item.evidence_id: item for item in request.evidence},
        )
        request_digest = _cure_request_digest(
            request, diagnosis, writer_state.writer, scope,
            locked_selection, cure_round,
        )
        if diagnosis.disposition is not DiagnosisDisposition.CONFIRMED:
            return CureDispatchOutcome(
                observation=_cure_observation((), locked_selection),
                request_digest=request_digest,
            )
        binding = workflow.bind_diagnosis(self.plan, curd, diagnosis)
        if extra_context is not None:
            extra_context = {
                **extra_context, "confirmed_diagnosis": diagnosis,
            }
        writer = workflow.execute_curd_writer(
            self.plan, curd, index,
            repository_root=self.root, artifact_directory=self.artifacts,
            resolved_evidence=self.resolved_evidence,
            durable_evidence=self.durable_evidence,
            shared_inputs=self.shared_inputs, phase="cure",
            provenance_refs=(binding.diagnosis.diagnosis_id,),
            dispatch_writer=self.dispatch_writer,
            extra_context=extra_context, result_id=result_id,
        )
        writer_state.writer = writer
        if isinstance(writer_state, _ScopeExecution):
            writer_state.writer_view = writer.writer_view
            writer_state.result, writer_state.subject = writer.result, writer.subject
        subject_evidence = _subject_evidence(writer)
        writer.host_evidence[subject_evidence.evidence_id] = subject_evidence
        _persist_scope_context(
            self.artifacts, self.run_id, scope.scope_id, scope_kind=scope.scope_kind,
            index=index, writer=writer, writer_view=writer.writer_view,
            result=writer.result, subject=writer.subject,
            latest_review=writer_state.latest_review,
        )
        applied, deferred, reverted = _declared_cure_partition(writer)
        gate_evidence = tuple(writer.host_evidence.values())
        if scope.scope_kind is RemediationScopeKind.POSTMERGE:
            gate_evidence = tuple({
                item.evidence_id: item
                for item in (*self.postmerge_gate_evidence, *gate_evidence)
            }.values())
        return CureDispatchOutcome(
            observation=_cure_observation(
                applied, deferred, touched_paths=tuple(writer.deliverables),
                gate_evidence=gate_evidence, reverted_finding_keys=reverted,
            ),
            request_digest=request_digest,
        )

def _context_path(
    artifact_directory: Path,
    run_id: str,
    scope_kind: RemediationScopeKind | str,
    scope_id: str | None = None,
) -> Path:
    if scope_id is None:
        scope_id = str(scope_kind)
        scope_kind = RemediationScopeKind.CURD
    kind = scope_kind.value if isinstance(scope_kind, RemediationScopeKind) else scope_kind
    root = artifact_directory.resolve()
    return _contained_path(
        root,
        root / "remediation" / _path_component(run_id)
        / f"{_path_component(kind)}-{_path_component(scope_id)}-context.json",
    )


def _manifest_path(artifact_directory: Path, run_id: str) -> Path:
    root = artifact_directory.resolve()
    return _contained_path(
        root, root / "execution" / f"{_path_component(run_id)}-manifest.json"
    )


class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...


_TRANSIENT_IDENTITY_DIRS = frozenset({
    ".cheese", ".context", ".git", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".venv", "__pycache__", "node_modules",
})


def _identity_digest_entry(digest: _Digest, root: Path, path: Path) -> None:
    relative = path.relative_to(root).as_posix().encode("utf-8")
    digest.update(relative + b"\\0")
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        digest.update(b"missing\\0")
        return
    digest.update(str(metadata.st_mode).encode("ascii") + b"\\0")
    if stat.S_ISLNK(metadata.st_mode):
        digest.update(os.readlink(path).encode("utf-8", "surrogateescape"))
        return
    if not stat.S_ISREG(metadata.st_mode):
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        raise ContractValidationError(
            f"cannot snapshot repository entry {relative.decode(errors='replace')}"
        ) from error
    try:
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
    finally:
        os.close(descriptor)


def _repository_identity(
    repository_root: Path, excluded_root: Path | None = None
) -> str:
    root = repository_root.resolve()
    excluded = None if excluded_root is None else excluded_root.resolve()
    try:
        probe = run_git(["rev-parse", "--show-toplevel"], cwd=root, timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        raise ContractValidationError("cannot determine repository identity") from error
    paths: list[Path] = []
    if probe.returncode == 0:
        try:
            head = run_git(["rev-parse", "HEAD"], cwd=root, timeout=10)
            remote = run_git(
                ["config", "--get", "remote.origin.url"], cwd=root, timeout=10
            )
            listed = run_git(
                [
                    "ls-files", "--cached", "--others", "--exclude-standard", "-z"
                ],
                cwd=root,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ContractValidationError(
                "cannot determine repository identity"
            ) from error
        if head.returncode != 0:
            raise ContractValidationError("cannot determine repository HEAD")
        if remote.returncode not in {0, 1}:
            raise ContractValidationError("cannot determine repository remote")
        if listed.returncode != 0:
            raise ContractValidationError("cannot enumerate repository contents")
        paths = [Path(item) for item in listed.stdout.split("\0") if item]
        source: tuple[str, str, str, str, list[Path]] = (
            "git", probe.stdout.strip(), head.stdout.strip(),
            remote.stdout.strip(), paths,
        )
    else:
        if "not a git repository" not in probe.stderr.lower():
            raise ContractValidationError("cannot determine repository identity")
        if (root / ".git").exists():
            raise ContractValidationError(
                "repository identity failed for an existing Git worktree"
            )
        source = ("nongit", "", "", "", paths)
        for current, directories, files in os.walk(root, followlinks=False):
            directories[:] = sorted(
                name for name in directories if name not in _TRANSIENT_IDENTITY_DIRS
            )
            for name in sorted(files):
                paths.append(Path(current) / name)
        source = (*source[:-1], [path.relative_to(root) for path in paths])
    digest = hashlib.sha256()
    digest.update(root.as_posix().encode("utf-8") + b"\\0")
    digest.update("\\0".join(source[:4]).encode("utf-8") + b"\\0")
    for relative in sorted(source[4], key=lambda item: item.as_posix()):
        path = root / relative
        if any(part in _TRANSIENT_IDENTITY_DIRS for part in relative.parts):
            continue
        if excluded is not None and path.is_relative_to(excluded):
            continue
        _identity_digest_entry(digest, root, path)
    return f"sha256:{digest.hexdigest()}"


def _path_ref(path: Path, *, artifact_id: str, role: str) -> ArtifactRef:
    raw = read_bounded_file(path, limit=16 * 1024 * 1024)
    return build_artifact_ref(path, raw, artifact_id=artifact_id, role=role)


def _persist_runtime_ref(
    artifact_directory: Path, run_id: str, name: str, role: str, value: object
) -> ArtifactRef:
    raw = canonical_bytes(value)
    root = artifact_directory.resolve()
    path = _contained_path(
        root,
        root / "remediation" / _path_component(run_id)
        / _path_component(role) / f"{_path_component(name)}.json",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, raw)
    return build_artifact_ref(path, raw, artifact_id=name, role=role)


def _validate_manifest_ref(root: Path, ref: ArtifactRef) -> None:
    parsed = urlsplit(ref.uri)
    try:
        path = restrict_local_path(resolve_file_path(parsed.netloc, parsed.path), root)
        raw = read_bounded_file(path, limit=ref.size_bytes)
    except (OSError, ValueError) as error:
        raise ContractValidationError(
            f"checkpoint artifact cannot be read: {ref.artifact_id}"
        ) from error
    if len(raw) != ref.size_bytes or bytes_digest(raw) != ref.digest:
        raise ContractValidationError(
            f"checkpoint artifact digest mismatch: {ref.artifact_id}"
        )
    if ref.media_type != "application/json":
        raise ContractValidationError("checkpoint artifact media type mismatch")


def _load_checkpoint_manifest(
    artifact_directory: Path,
    run_id: str,
    plan: CurdPlan,
    repository_root: Path,
    repository_identity: str | None = None,
) -> tuple[ArtifactRef, ...]:
    path = _manifest_path(artifact_directory, run_id)
    if not path.exists():
        return ()
    payload = _json_object(
        cast(object, json.loads(read_bounded_file(path, limit=16 * 1024 * 1024))),
        "checkpoint manifest must be an object",
    )
    if payload.get("run_id") != run_id or payload.get("plan_id") != plan.plan_id or payload.get("plan_digest") != plan.digest:
        raise ContractValidationError("checkpoint manifest identity mismatch")
    expected_identity = repository_identity or _repository_identity(repository_root, artifact_directory)
    if payload.get("repository_identity") != expected_identity:
        raise ContractValidationError("checkpoint manifest repository identity mismatch")
    references = _json_list(payload.get("references"), "checkpoint manifest references must be a list")
    marker = payload.get("commit_marker")
    expected_marker = bytes_digest(canonical_bytes(references)).removeprefix("sha256:")
    if marker != expected_marker:
        raise ContractValidationError("checkpoint manifest commit marker mismatch")
    validated: list[ArtifactRef] = []
    for raw in references:
        ref = _artifact_from_json(raw)
        _validate_manifest_ref(artifact_directory, ref)
        validated.append(ref)
    return tuple(validated)


def _write_checkpoint_manifest(
    artifact_directory: Path,
    run_id: str,
    plan: CurdPlan,
    repository_root: Path,
    refs: Sequence[ArtifactRef],
    repository_identity: str | None = None,
) -> ArtifactRef:
    unique = {ref.artifact_id: ref for ref in refs}
    payload = {
        "run_id": run_id,
        "plan_id": plan.plan_id,
        "plan_revision": plan.revision,
        "plan_digest": plan.digest,
        "repository_identity": repository_identity or _repository_identity(repository_root, artifact_directory),
        "references": tuple(unique.values()),
    }
    payload["commit_marker"] = bytes_digest(canonical_bytes(payload["references"])).removeprefix("sha256:")
    path = _manifest_path(artifact_directory, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(payload)
    atomic_write(path, raw)
    return build_artifact_ref(
        path, raw, artifact_id=f"{run_id}/checkpoint-manifest", role="checkpoint-manifest"
    )



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


def _json_string(value: object, message: str) -> str:
    if not isinstance(value, str):
        raise ValueError(message)
    return value


def _writer_view_from_json(value: object) -> CurdResultWriterView:
    payload = load_agent_writer_view(
        {"kind": WriterViewKind.CURD_RESULT.value, "payload": value}
    )
    assert isinstance(payload.payload, CurdResultWriterView)
    return payload.payload


def _artifact_from_json(value: object) -> ArtifactRef:
    payload = _json_object(value, "artifact reference must be an object")
    schema_uri = payload.get("schema_uri")
    if schema_uri is not None and not isinstance(schema_uri, str):
        raise ValueError("artifact schema URI must be a string")
    return ArtifactRef(
        artifact_id=_json_string(payload.get("artifact_id"), "artifact ID must be a string"),
        role=_json_string(payload.get("role"), "artifact role must be a string"),
        uri=_json_string(payload.get("uri"), "artifact URI must be a string"),
        digest=_json_string(payload.get("digest"), "artifact digest must be a string"),
        size_bytes=_json_int(
            payload.get("size_bytes"), "artifact size must be an integer"
        ),
        media_type=_json_string(
            payload.get("media_type"), "artifact media type must be a string"
        ),
        schema_uri=schema_uri,
    )


def _evidence_from_json(value: object) -> EvidenceRef:
    payload = _json_object(value, "evidence reference must be an object")
    location_value = payload.get("location")
    location = None
    if location_value is not None:
        location_payload = _json_object(
            location_value, "evidence location must be an object"
        )
        start_column = location_payload.get("start_column")
        end_column = location_payload.get("end_column")
        if start_column is not None and not isinstance(start_column, int):
            raise ValueError("evidence start column must be an integer")
        if end_column is not None and not isinstance(end_column, int):
            raise ValueError("evidence end column must be an integer")
        location = SourceLocation(
            artifact_id=_json_string(
                location_payload.get("artifact_id"),
                "evidence location artifact ID must be a string",
            ),
            path=_json_string(
                location_payload.get("path"), "evidence location path must be a string"
            ),
            start_line=_json_int(
                location_payload.get("start_line"),
                "evidence start line must be an integer",
            ),
            start_column=start_column,
            end_line=_json_int(
                location_payload.get("end_line"),
                "evidence end line must be an integer",
            ),
            end_column=end_column,
        )
    summary = payload.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("evidence summary must be a string")
    try:
        kind = EvidenceKind(
            _json_string(payload.get("kind"), "evidence kind must be a string")
        )
    except ValueError as error:
        raise ValueError("evidence kind is invalid") from error
    return EvidenceRef(
        evidence_id=_json_string(
            payload.get("evidence_id"), "evidence ID must be a string"
        ),
        kind=kind,
        artifact=_artifact_from_json(payload.get("artifact")),
        location=location,
        summary=summary,
    )


def _press_result_from_json(value: object) -> PressGateResult:
    payload = _json_object(value, "persisted Press result must be an object")
    failures_value = payload.get("new_failures", [])
    evidence_value = payload.get("evidence", [])
    if not isinstance(failures_value, list) or not isinstance(evidence_value, list):
        raise ValueError("persisted Press result fields are invalid")
    failures = tuple(
        _json_string(item, "Press failure must be a string")
        for item in cast(list[object], failures_value)
    )
    evidence = tuple(
        _evidence_from_json(item) for item in cast(list[object], evidence_value)
    )
    scope_value = payload.get("scope")
    scope = None
    if scope_value is not None:
        scope_payload = _json_object(scope_value, "Press scope must be an object")
        plan_payload = _json_object(
            scope_payload.get("source_plan_ref"), "Press plan must be an object"
        )
        try:
            scope_kind = RemediationScopeKind(
                _json_string(scope_payload.get("scope_kind"), "Press scope kind must be a string")
            )
        except ValueError as error:
            raise ValueError("Press scope kind is invalid") from error
        scope = RemediationScopeKey(
            run_id=_json_string(scope_payload.get("run_id"), "Press run ID must be a string"),
            source_plan_ref=SourcePlanRef(
                plan_id=_json_string(plan_payload.get("plan_id"), "Press plan ID must be a string"),
                revision=_json_int(
                    plan_payload.get("revision"), "Press plan revision must be an integer"
                ),
                digest=_json_string(
                    plan_payload.get("digest"), "Press plan digest must be a string"
                ),
            ),
            scope_kind=scope_kind,
            scope_id=_json_string(
                scope_payload.get("scope_id"), "Press scope ID must be a string"
            ),
        )
    gate_round = payload.get("gate_round")
    if gate_round is not None:
        gate_round = _json_int(gate_round, "Press gate round must be an integer")
    passed = payload.get("passed")
    if not isinstance(passed, bool):
        raise ValueError("Press passed flag must be a boolean")
    return PressGateResult(
        passed=passed,
        baseline_id=_json_string(
            payload.get("baseline_id"), "Press baseline ID must be a string"
        ),
        new_failures=failures,
        evidence=evidence,
        scope=scope,
        gate_round=gate_round,
    )


def _load_persisted_press_results(
    artifact_directory: Path,
    refs: Sequence[ArtifactRef],
) -> tuple[PressGateResult, ...]:
    """Load only Press envelopes admitted by the validated checkpoint manifest."""
    if isinstance(refs, (str, bytes)):
        raise TypeError("manifest references must be a sequence of ArtifactRef")
    values: list[PressGateResult] = []
    for ref in refs:
        if ref.role != "press-result":
            continue
        try:
            parsed = urlsplit(ref.uri)
            path = restrict_local_path(
                resolve_file_path(parsed.netloc, parsed.path), artifact_directory
            )
            raw = read_bounded_file(path, limit=ref.size_bytes)
        except (OSError, ValueError) as error:
            raise ContractValidationError(
                f"checkpoint artifact cannot be read: {ref.artifact_id}"
            ) from error
        if bytes_digest(raw) != ref.digest:
            raise ContractValidationError(
                f"checkpoint artifact digest mismatch: {ref.artifact_id}"
            )
        values.append(_press_result_from_json(cast(object, json.loads(raw))))
    if any(value.scope is None or value.gate_round is None for value in values):
        raise ContractValidationError("persisted Press envelope lacks scope identity or gate round")
    rounds = [cast(int, value.gate_round) for value in values]
    if len(set(rounds)) != len(rounds) or sorted(rounds) != list(range(1, len(rounds) + 1)):
        raise ContractValidationError("persisted Press gate rounds are not unique and sequential")
    return tuple(sorted(values, key=lambda value: cast(int, value.gate_round)))




def _persist_scope_context(
    artifact_directory: Path,
    run_id: str,
    scope_id: str,
    *,
    scope_kind: RemediationScopeKind = RemediationScopeKind.CURD,
    index: int,
    writer: workflow.CurdWriterExecution,
    writer_view: CurdResultWriterView,
    result: CurdResult,
    subject: ArtifactRef,
    latest_review: ReviewResult | None,
) -> None:
    payload = {
        "scope_id": scope_id,
        "scope_kind": scope_kind,
        "index": index,
        "writer_view": writer_view,
        "host_evidence": tuple(writer.host_evidence.values()),
        "deliverables": tuple(writer.deliverables.values()),
        "subject": subject,
        "result": result,
        "latest_review": latest_review,
        "writer_context_digest": writer.writer_context_digest,
    }
    path = _context_path(artifact_directory, run_id, scope_kind, scope_id)
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
    artifact_directory: Path,
    run_id: str,
    plan: CurdPlan,
    curd: SemanticCurd,
    index: int,
    scope_kind: RemediationScopeKind = RemediationScopeKind.CURD,
) -> _ScopeExecution | None:
    path = _context_path(artifact_directory, run_id, scope_kind, curd.curd_id)
    if not path.exists():
        return None
    try:
        payload = _json_object(
            cast(object, json.loads(read_bounded_file(path, limit=16 * 1024 * 1024))),
            "persisted scope context must be an object",
        )
        if (
            payload.get("scope_id") != curd.curd_id
            or payload.get("scope_kind") not in {scope_kind, scope_kind.value}
            or _json_int(payload.get("index"), "persisted scope index must be an integer") != index
        ):
            raise ValueError("persisted scope context does not match the plan")
        result = cast(CurdResult, _validate_contract_value(payload["result"], CurdResult))
        latest_raw = payload.get("latest_review")
        latest = None if latest_raw is None else cast(ReviewResult, _validate_contract_value(latest_raw, ReviewResult))
        evidence = {
            item.evidence_id: item
            for item in (_evidence_from_json(value) for value in _json_list(payload["host_evidence"], "host evidence must be a list"))
        }
        writer_view = _writer_view_from_json(payload["writer_view"])
        deliverable_values = tuple(
            _artifact_from_json(value)
            for value in _json_list(payload["deliverables"], "deliverables must be a list")
        )
        if len(deliverable_values) != len(writer_view.deliverables):
            raise ValueError("persisted deliverables do not match the writer view")
        deliverables = {
            view.path: artifact
            for view, artifact in zip(writer_view.deliverables, deliverable_values, strict=True)
        }
        subject = _artifact_from_json(payload["subject"])
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
    dispatch_press: PressDispatcher | None = None,
    results: Mapping[str, CurdResult] | None = None,
) -> FanExecutionOutcome:
    """Run selected curds while holding the complete fan-run lock."""
    artifacts = Path(artifact_directory)
    run_id = execution_id or f"{plan.plan_id}-execution"
    with run_lock(artifacts, run_id):
        return _execute_fan_locked(
            plan,
            repository_root=repository_root,
            artifact_directory=artifact_directory,
            dispatch_writer=dispatch_writer,
            dispatch_review=dispatch_review,
            dispatch_diagnosis=dispatch_diagnosis,
            evidence=evidence,
            selected=selected,
            execution_id=execution_id,
            dispatch_press=dispatch_press,
            results=results,
        )


def _execute_fan_locked(
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
    dispatch_press: PressDispatcher | None = None,
    results: Mapping[str, CurdResult] | None = None,
) -> FanExecutionOutcome:
    """Run fan adapters while the caller holds the complete fan-run lock."""

    root = Path(repository_root)
    artifacts = Path(artifact_directory)
    indexed = {curd.curd_id: index for index, curd in enumerate(plan.curds, start=1)}
    shared_inputs, resolved_evidence, durable_evidence = workflow.resolve_plan_context(
        plan,
        repository_root=root,
        artifact_directory=artifacts,
        evidence={} if evidence is None else evidence,
    )
    run_id = execution_id or f"{plan.plan_id}-execution"
    repository_identity = _repository_identity(root, artifacts)
    journal_path = _contained_path(
        artifacts.resolve(),
        artifacts.resolve() / "execution" / f"{_path_component(run_id)}.json",
    )
    committed_refs = list(
        _load_checkpoint_manifest(artifacts, run_id, plan, root, repository_identity)
    )
    if results and not _manifest_path(artifacts, run_id).exists():
        raise ContractValidationError("accepted results require a checkpoint manifest")
    adapters = _FanAdapters(
        plan=plan, root=root, artifacts=artifacts, indexed=indexed,
        shared_inputs=shared_inputs, resolved_evidence=resolved_evidence,
        durable_evidence=durable_evidence, run_id=run_id,
        dispatch_writer=dispatch_writer, dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis, dispatch_press=dispatch_press,
        committed_refs=committed_refs, journal_path=journal_path,
        journal_results=dict(results or {}),
        press_refs=[ref for ref in committed_refs if ref.role == "press-result"],
    )
    adapters.checkpoint_manifest()
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
        adapters.scopes[curd.curd_id] = restored
    adapters.aggregate_curd = (
        _aggregate_curd(plan, adapters.scopes) if adapters.scopes else None
    )
    if adapters.aggregate_curd is not None and _context_path(
        artifacts, run_id, RemediationScopeKind.POSTMERGE, "postmerge"
    ).exists():
        restored = _load_scope_context(
            artifacts, run_id, plan, adapters.aggregate_curd, 1,
            RemediationScopeKind.POSTMERGE,
        )
        if restored is not None:
            adapters.postmerge = _PostmergeExecution(
                curd=adapters.aggregate_curd,
                writer=restored.writer,
                latest_review=restored.latest_review,
            )
    persisted_press = _load_persisted_press_results(artifacts, committed_refs)
    adapters.latest_postmerge_gate_evidence[:] = (
        persisted_press[0].evidence if persisted_press else ()
    )
    adapters.postmerge_gate_evidence[:] = [
        item for gate in persisted_press for item in gate.evidence
    ]

    context = FanContext(
        run_id=adapters.run_id,
        artifact_directory=artifacts,
        cook=adapters.cook,
        age=adapters.age,
        cure=adapters.cure,
        press=adapters.press if dispatch_press is not None else None,
        result_sink=adapters.persist_result,
        checkpoint_sink=adapters.checkpoint_manifest,
    )
    outcome = run_fan_locked(plan, context, selected=selected, results=results)
    refs: list[ArtifactRef] = list(adapters.press_refs)
    journal_path = adapters.journal_path
    if journal_path.exists():
        refs.append(_path_ref(journal_path, artifact_id=f"{run_id}/results", role="curd-results"))
    for _scope_key, state in outcome.scope_states.items():
        scope_id = state.scope.scope_id
        state_path = scope_state_path(artifacts, state.scope)
        refs.append(_path_ref(
            state_path,
            artifact_id=f"{run_id}/{state.scope.scope_kind.value}/{scope_id}/state",
            role=REMEDIATION_STATE_ROLE,
        ))
        context_path = _context_path(
            artifacts, run_id, state.scope.scope_kind, state.scope.scope_id
        )
        if context_path.exists():
            refs.append(_path_ref(
                context_path,
                artifact_id=(
                    f"{run_id}/{state.scope.scope_kind.value}/{state.scope.scope_id}/context"
                ),
                role="adapter-context",
            ))
    refs.extend(outcome.stop_evidence_refs)
    if outcome.remediation_request_ref is not None:
        refs.append(outcome.remediation_request_ref)
    _ = _write_checkpoint_manifest(
        artifacts, run_id, plan, root, refs
    )
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
    writer: workflow.CurdWriterExecution
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    declaration = writer.cure_reconciliation
    if declaration is None:
        raise ValueError("Cure writer must declare finding reconciliation")
    return (
        tuple(declaration.applied_finding_keys),
        tuple(declaration.deferred_finding_keys),
        tuple(declaration.reverted_finding_keys),
    )


def _aggregate_subject(
    plan: CurdPlan,
    run_id: str,
    aggregate: SemanticCurd,
    scopes: Mapping[str, _ScopeExecution],
    artifact_directory: Path,
) -> tuple[ArtifactRef, tuple[EvidenceRef, ...]]:
    payload = {
        "run_id": run_id,
        "plan_id": plan.plan_id,
        "revision": plan.revision,
        "results": [state.result for state in scopes.values()],
    }
    raw = canonical_bytes(payload)
    root = artifact_directory.resolve()
    path = _contained_path(
        root,
        root / "remediation" / _path_component(run_id)
        / f"{_path_component(aggregate.curd_id)}-subject.json",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, raw)
    subject = build_artifact_ref(
        path, raw, artifact_id=f"{plan.plan_id}/postmerge-subject", role="subject"
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
    invocation = workflow.result_invocation(
        state.writer.plan,
        state.curd,
        state.index,
        evidence=state.writer.host_evidence,
        deliverables=state.writer.deliverables,
        provenance_refs=(review.review_id,),
    )
    canonical = workflow.normalize(
        state.writer_view, WriterViewKind.CURD_RESULT, invocation
    )
    assert isinstance(canonical.value, CurdResult)
    subject = workflow.subject_artifact(
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