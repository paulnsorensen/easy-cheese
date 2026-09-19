"""Cook ingress classification and evidence-driven preparation.

Cook is the consumer-owned boundary for Mold work.  This module deliberately
keeps preparation separate from execution: it classifies the request, resolves
continuity, checks durable evidence, and returns a closed
``CookPreparationResult``.  It never dispatches an agent and never treats a
status string as approval.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import attrs

from easy_cheese_schemas import (
    CURD_PLAN_SCHEMA_URI,
    MAX_ARTIFACT_BYTES,
    SCHEMA_ROOT,
    ArtifactRef,
    ContractVersion,
    EvidenceRef,
    CurdPlan,
    HandoffPointer,
    NormalizationReceipt,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    PlannerResultWriterView,
    PlannerUncertainty,
    canonical_bytes,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.compat import check_adapter_sunsets
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
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
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese_schemas.validate import (
    require_exact_keys,
    require_mapping,
    require_relative_path,
)
from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_artifact,
    resolve_file_path,
    resolve_verified_bytes,
    restrict_local_path,
)
from easy_cheese.shared.mold_cook_handoff import (
    SETUP_EVIDENCE_SCHEMA_URI,
    MoldCookSpecReadiness,
    SetupEvidence,
    SetupEvidenceExecutionError,
    canonical_mold_cook_proposal,
    dialogue_authorizes_execution,
    evaluate_mold_cook_spec,
    validate_mold_cook_approval,
    validate_mold_cook_handoff,
    validate_mold_cook_setup_evidence,
)
from easy_cheese.shared.publication import (
    accept_mold_cook_handoff,
    publish_mold_cook_handoff,
)
from easy_cheese.shared.wheypoint.canonical import digest_bytes
from easy_cheese.shared.wheypoint.resolve import (
    Resolution,
    ResolutionOutcome,
    resolve,
)
from easy_cheese.shared import workflow
from easy_cheese.shared.workflow import plan as workflow_plan


_POINTER_MARKERS = frozenset(
    {"operation_id", "request_digest", "source_phase", "destination_phase", "payload"}
)
_PROJECTION_MARKERS = frozenset(
    {
        "schema_version",
        "work_id",
        "revision_id",
        "record_digest",
        "projection_digest",
        "next_action",
        "gating_entry_ids",
        "decision_dossier",
        "durability",
        "status",
    }
)
_HANDOFF_MARKERS = frozenset(
    {"request_id", "input_kind", "mode", "spec_ref", "approval_ref", "coverage"}
)
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")


class CookInputError(ValueError):
    """A request could not be classified as one supported Cook input."""


class CookEvidenceError(ValueError):
    """Evidence is absent, stale, detached, or outside its authority."""


class _DependencyClosureError(CookEvidenceError):
    """A partial approval names a curd without its approved dependencies."""


class _SetupExecutionFailed(CookEvidenceError):
    """The authorized setup command ran but did not pass."""


@attrs.define(frozen=True)
class ClassifiedCookInput:
    """The input contract selected before any format-specific resolution."""

    kind: MoldCookInputKind
    source: str
    path: Path | None = None
    explicit: bool = False
    declared_kind: MoldCookInputKind | None = None
    snapshot: bytes | None = None


@attrs.define(frozen=True)
class CookPreparationRequest:
    """Host-owned context for one recomputable preparation transition."""

    request_id: str
    source: str | Path | ClassifiedCookInput
    repository_root: Path = attrs.field(converter=Path)
    artifact_root: Path = attrs.field(converter=Path)
    mode: MoldCookMode = MoldCookMode.FULL
    explicit_kind: MoldCookInputKind | None = None
    holds: tuple[CookExecutionHold, ...] = attrs.field(factory=tuple)



@attrs.define(frozen=True)
class CookHoldClearance:
    """One explicit user response that clears a named execution hold."""

    hold_id: str
    response_ref: ArtifactRef = attrs.field(
        validator=attrs.validators.instance_of(ArtifactRef)
    )
    response_text: str

    def __attrs_post_init__(self) -> None:
        if not self.hold_id or not self.response_text.strip():
            raise ValueError("hold clearance requires a hold ID and response text")


@attrs.define(frozen=True)
class CookExecutionOutcome:
    """Durable binding for one accepted handoff execution."""

    request_id: str
    handoff_ref: ArtifactRef
    planner_result_ref: ArtifactRef
    plan_ref: ArtifactRef
    coverage: MoldCookCoverage
    completed_curds: tuple[str, ...]
    remainder: tuple[PlannerUncertainty, ...]
    whole_task_complete: bool
    resumable_ref: ArtifactRef
    execution_results: workflow.ExecutionResults = attrs.field(repr=False)
    outcome_ref: ArtifactRef | None = None


@attrs.define(frozen=True)
class _LegacyPlanMigration:
    """Typed read-only bridge from an intact historical CurdPlan pointer."""

    plan: CurdPlan
    plan_ref: ArtifactRef
    normalization_receipt_ref: ArtifactRef | None = None


class _PreparationFailure(Exception):
    """Internal typed failure converted into an invalid preparation result."""

    def __init__(self, code: str, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.code: str = code
        self.path: str | None = path


def _version(contract: type) -> ContractVersion:
    version = supported_version_for(contract)
    if version is None:
        raise TypeError(f"{contract.__name__} has no supported contract version")
    return version


def _local_path_for(uri: str, allowed_root: str | Path | None = None) -> Path:
    """Resolve one `file:` artifact URI through the shared artifact seam.

    A caller that already knows its trusted root passes it: the URI then names
    a path inside that root instead of widening it.
    """

    parsed = urlsplit(uri)
    if parsed.scheme != "file":
        raise CookEvidenceError(
            f"artifact URI must use the local file scheme, got {parsed.scheme!r}"
        )
    path = resolve_file_path(parsed.netloc, parsed.path)
    if allowed_root is None:
        return path
    return restrict_local_path(path, allowed_root)


def _as_path(source: str | Path) -> Path | None:
    try:
        return (
            source.expanduser()
            if isinstance(source, Path)
            else Path(source).expanduser()
        )
    except (OSError, ValueError):
        return None


def _read_path(path: Path, *, limit: int = MAX_ARTIFACT_BYTES) -> bytes:
    """Read one regular file through a bounded, no-follow descriptor."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd: int | None = None
    try:
        fd = os.open(path, flags)
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise CookInputError(f"input is not a regular file: {path!r}")
        if metadata.st_size < 0 or metadata.st_size > limit:
            raise CookInputError(
                f"input {path!r} is larger than the {limit}-byte limit"
            )
        remaining = metadata.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                raise CookInputError(f"input {path!r} changed while it was read")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    except CookInputError:
        raise
    except OSError as exc:
        raise CookInputError(f"cannot read input {path!r}: {exc}") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _is_regular_path(path: Path) -> bool:
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False


def _declared_kind(raw: bytes) -> MoldCookInputKind | None:
    try:
        value = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(value, Mapping):
        return None
    mapping = cast("Mapping[str, object]", value)
    keys = set(mapping)
    if keys & _POINTER_MARKERS:
        return MoldCookInputKind.CANONICAL_POINTER
    if keys & _PROJECTION_MARKERS:
        return MoldCookInputKind.CONTINUATION
    if _HANDOFF_MARKERS <= keys:
        return MoldCookInputKind.CANONICAL_POINTER
    return None


def _kind(value: MoldCookInputKind | str | None) -> MoldCookInputKind | None:
    if value is None:
        return None
    if isinstance(value, MoldCookInputKind):
        return value
    normalized = value.strip().casefold().replace("-", "_")
    values = {
        "spec": MoldCookInputKind.DIRECT_SPEC,
        "direct_spec": MoldCookInputKind.DIRECT_SPEC,
        "pointer": MoldCookInputKind.CANONICAL_POINTER,
        "canonical_pointer": MoldCookInputKind.CANONICAL_POINTER,
        "continue": MoldCookInputKind.CONTINUATION,
        "continuation": MoldCookInputKind.CONTINUATION,
        "task": MoldCookInputKind.TASK,
        "slug": MoldCookInputKind.SLUG,
    }
    try:
        return values[normalized]
    except KeyError:
        try:
            return MoldCookInputKind(normalized)
        except ValueError as exc:
            raise CookInputError(f"unsupported explicit input mode {value!r}") from exc


def classify_input(
    source: str | Path,
    *,
    explicit_kind: MoldCookInputKind | str | None = None,
) -> ClassifiedCookInput:
    """Choose the ingress contract before resolving its contents.

    Explicit mode always wins. Existing regular files are inspected before
    slug/task inference, including cwd-relative names without path markers.
    """

    expected = _kind(explicit_kind)
    source_text = str(source)
    path = _as_path(source)
    regular = path is not None and _is_regular_path(path)
    snapshot: bytes | None = None
    declared: MoldCookInputKind | None = None
    if regular:
        assert path is not None
        snapshot = _read_path(path)
        declared = _declared_kind(snapshot)
    if expected is not None:
        if declared is not None and declared is not expected:
            raise CookInputError(
                f"input declares {declared.value}, not the explicit {expected.value} mode"
            )
        return ClassifiedCookInput(
            expected, source_text, path, True, declared, snapshot
        )
    if declared is not None:
        return ClassifiedCookInput(
            declared, source_text, path, False, declared, snapshot
        )
    if regular:
        assert path is not None
        if path.suffix.casefold() in {".md", ".markdown"}:
            return ClassifiedCookInput(
                MoldCookInputKind.DIRECT_SPEC,
                source_text,
                path,
                False,
                None,
                snapshot,
            )
        raise CookInputError(
            f"unrecognised artifact {str(path)!r}; use an explicit Cook input mode"
        )
    from easy_cheese.shared.paths import validate_slug

    if validate_slug(source_text) is None:
        return ClassifiedCookInput(MoldCookInputKind.SLUG, source_text)
    if not source_text.strip():
        raise CookInputError("Cook input must not be empty")
    return ClassifiedCookInput(MoldCookInputKind.TASK, source_text)


def _request_id(source: ClassifiedCookInput, explicit: str | None) -> str:
    if explicit:
        return explicit
    # The parts are JSON-encoded, never newline-joined: free text in the
    # objective would otherwise reproduce another input's token.
    token = json.dumps(
        [
            source.kind.value,
            source.source,
            "" if source.path is None else str(source.path.resolve()),
            "" if source.snapshot is None else digest_bytes(source.snapshot),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"cook-{hashlib.sha256(token.encode()).hexdigest()[:20]}"


def _persist_bytes(
    root: Path,
    *,
    content: bytes,
    artifact_id: str,
    role: str,
    media_type: str,
    schema_uri: str | None = None,
) -> ArtifactRef:
    digest = digest_bytes(content)
    reference = ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=root.resolve().as_uri(),
        digest=digest,
        size_bytes=len(content),
        media_type=media_type,
        schema_uri=schema_uri,
    )
    try:
        retained = resolve_verified_bytes(
            reference,
            content,
            media_type.split(";", 1)[0],
            root,
        )
    except (
        ArtifactDigestMismatchError,
        ArtifactResolutionError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise CookEvidenceError(f"cannot retain artifact {artifact_id!r}") from exc
    return attrs.evolve(reference, uri=Path(retained.path).as_uri())


def _persist_value(
    root: Path,
    value: object,
    *,
    artifact_id: str,
    role: str,
    schema_uri: str | None,
) -> ArtifactRef:
    return _persist_bytes(
        root,
        content=canonical_bytes(value),
        artifact_id=artifact_id,
        role=role,
        media_type="application/json",
        schema_uri=schema_uri,
    )


def _resolve_ref(ref: ArtifactRef, root: Path) -> bytes:
    scheme = urlsplit(ref.uri).scheme
    if scheme not in {"file", "repo"}:
        raise CookEvidenceError(
            f"artifact {ref.artifact_id!r} uses unsupported local-only scheme {scheme!r}"
        )
    try:
        return resolve_artifact(
            attrs.evolve(ref, schema_uri=None),
            repository_root=root,
            artifact_directory=root,
            allowed_local_root=root,
        ).content
    except (ArtifactResolutionError, ArtifactDigestMismatchError, OSError) as exc:
        raise CookEvidenceError(
            f"artifact {ref.artifact_id!r} is unreadable: {exc}"
        ) from exc


def _load_contract(ref: ArtifactRef, contract: type, root: Path) -> object:
    raw = _resolve_ref(ref, root)
    try:
        return validate_contract(raw, contract, _version(contract)).value
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise CookEvidenceError(
            f"artifact {ref.artifact_id!r} is not a valid {contract.__name__}: {exc}"
        ) from exc


def validate_preparation_result(value: object) -> CookPreparationResult:
    """Validate one canonical preparation result through the shared schema."""

    raw = canonical_bytes(value)
    try:
        validated = validate_contract(
            raw,
            CookPreparationResult,
            _version(CookPreparationResult),
        ).value
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise CookEvidenceError(f"invalid CookPreparationResult: {exc}") from exc
    if not isinstance(validated, CookPreparationResult):
        raise CookEvidenceError("validated preparation result has the wrong type")
    return validated


def load_preparation_result(path: str | Path) -> CookPreparationResult:
    """Load a standalone result or a Mold saved-not-ready envelope."""

    raw = _read_path(Path(path))
    try:
        decoded = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("preparation result is not valid JSON") from exc
    value = require_mapping(decoded, "preparation result")
    if "value" in value and "digest" in value:
        value = require_mapping(value["value"], "preparation result value")
    if "preparation_result" in value:
        value = require_mapping(value["preparation_result"], "saved preparation result")
    return validate_preparation_result(value)


def _request_payload(request: CookPreparationRequest) -> dict[str, object]:
    source = request.source
    if not isinstance(source, ClassifiedCookInput):
        raise CookEvidenceError("preparation request source was not classified")
    path = None if source.path is None else str(source.path.resolve())
    source_digest = None if source.snapshot is None else digest_bytes(source.snapshot)
    return {
        "request_id": request.request_id,
        "kind": source.kind.value,
        "source": source.source,
        "path": path,
        "explicit": source.explicit,
        "declared_kind": (
            None if source.declared_kind is None else source.declared_kind.value
        ),
        "source_digest": source_digest,
        "repository_root": str(request.repository_root),
        "artifact_root": str(request.artifact_root),
        "mode": request.mode.value,
    }


def _persist_request(request: CookPreparationRequest) -> ArtifactRef:
    return _persist_bytes(
        request.artifact_root,
        content=canonical_bytes(_request_payload(request)),
        artifact_id=f"{request.request_id}/preparation-request",
        role="preparation_request",
        media_type="application/json",
    )


def _request_metadata(ref: ArtifactRef, root: Path) -> Mapping[str, object]:
    raw = _resolve_ref(ref, root)
    try:
        value = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CookEvidenceError(
            "preparation request reference is not valid JSON"
        ) from exc
    values = require_mapping(value, "preparation request")
    required = (
        "request_id",
        "kind",
        "source",
        "path",
        "explicit",
        "declared_kind",
        "source_digest",
        "repository_root",
        "artifact_root",
        "mode",
    )
    try:
        require_exact_keys(values, required, "preparation request")
    except ValueError as exc:
        raise CookEvidenceError(str(exc)) from exc
    return values


def _source_ref(
    source: ClassifiedCookInput, root: Path, request_id: str
) -> ArtifactRef:
    if source.path is not None:
        raw = (
            source.snapshot if source.snapshot is not None else _read_path(source.path)
        )
        media_type = (
            "text/markdown"
            if source.path.suffix.casefold() in {".md", ".markdown"}
            else "application/octet-stream"
        )
        return _persist_bytes(
            root,
            content=raw,
            artifact_id=f"{request_id}/input",
            role="spec" if source.kind is MoldCookInputKind.DIRECT_SPEC else "input",
            media_type=media_type,
        )
    return _persist_bytes(
        root,
        content=source.source.encode("utf-8"),
        artifact_id=f"{request_id}/input",
        role="spec" if source.kind is MoldCookInputKind.TASK else "input",
        media_type="text/plain",
    )


def _spec_ref(
    source: ClassifiedCookInput,
    root: Path,
    request_id: str,
) -> tuple[ArtifactRef, str]:
    if source.kind is MoldCookInputKind.DIRECT_SPEC:
        if source.path is None:
            raise _PreparationFailure(
                "missing-spec", "direct spec input must name a file"
            )
        raw = (
            source.snapshot if source.snapshot is not None else _read_path(source.path)
        )
        path = source.path
    elif source.kind is MoldCookInputKind.TASK:
        raw = source.source.encode("utf-8")
        path = None
    elif source.kind is MoldCookInputKind.SLUG:
        candidate = _find_spec(source.source)
        if candidate is None:
            raise _PreparationFailure(
                "missing-spec",
                f"spec slug {source.source!r} was not found",
            )
        try:
            raw = _read_path(candidate)
        except (CookInputError, OSError, UnicodeDecodeError) as exc:
            raise _PreparationFailure(
                "invalid-spec",
                f"cannot read spec {candidate!r}: {exc}",
                path=str(candidate),
            ) from exc
        path = candidate
    else:
        raise _PreparationFailure(
            "missing-spec",
            "this input requires an independently supplied spec",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _PreparationFailure(
            "invalid-spec",
            f"spec is not UTF-8: {exc}",
            path=None if path is None else str(path),
        ) from exc
    return (
        _persist_bytes(
            root,
            content=raw,
            artifact_id=f"{request_id}/spec",
            role="spec",
            media_type="text/markdown",
        ),
        text,
    )


def _find_spec(slug: str) -> Path | None:
    from easy_cheese.shared.paths import artifact_path

    candidate = artifact_path("specs", slug)
    return candidate if candidate.is_file() else None


def _bound_spec_ref(
    value: ArtifactRef | str | Path,
    *,
    request: CookPreparationRequest,
) -> tuple[ArtifactRef, str]:
    if isinstance(value, ArtifactRef):
        if value.role != "spec":
            raise CookEvidenceError("bound spec must use the spec artifact role")
        raw = _resolve_ref(value, request.artifact_root)
        reference = value
    else:
        path = Path(value).expanduser().resolve()
        raw = _read_path(path)
        digest = digest_bytes(raw)
        expected = request.artifact_root.resolve() / (
            f"sha256-{digest.removeprefix('sha256:')}"
        )
        if path != expected:
            raise CookEvidenceError("bound spec must be a retained host artifact")
        reference = ArtifactRef(
            artifact_id=f"{request.request_id}/spec",
            role="spec",
            uri=path.as_uri(),
            digest=digest,
            size_bytes=len(raw),
            media_type="text/markdown",
            schema_uri=None,
        )
    try:
        return reference, raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CookEvidenceError("bound spec is not UTF-8") from exc


def _spec_readiness(
    source: ClassifiedCookInput,
    *,
    spec_ref: ArtifactRef,
    raw: bytes,
) -> MoldCookSpecReadiness | None:
    if source.kind not in {
        MoldCookInputKind.DIRECT_SPEC,
        MoldCookInputKind.SLUG,
    }:
        return None
    readiness = evaluate_mold_cook_spec(raw, spec_ref=spec_ref)
    identity = readiness.spec_slug
    if source.kind is MoldCookInputKind.DIRECT_SPEC and source.path is not None:
        if source.path.stem != identity:
            raise _PreparationFailure(
                "spec-identity-conflict",
                f"spec path stem {source.path.stem!r} does not match frontmatter slug {identity!r}",
                path=str(source.path),
            )
    if source.kind is MoldCookInputKind.SLUG and source.source != identity:
        raise _PreparationFailure(
            "spec-identity-conflict",
            f"requested slug {source.source!r} does not match frontmatter slug {identity!r}",
        )
    return readiness


def _continuity_hold(
    source: ClassifiedCookInput,
    repository_root: Path,
    *,
    identity: str | None = None,
) -> CookExecutionHold | None:
    if source.kind is MoldCookInputKind.TASK and identity is None:
        return None
    if source.kind not in {
        MoldCookInputKind.DIRECT_SPEC,
        MoldCookInputKind.SLUG,
        MoldCookInputKind.TASK,
    }:
        return None
    canonical_identity = identity or (
        source.path.stem if source.path is not None else source.source
    )
    resolution: Resolution = resolve(canonical_identity, workspace_root=repository_root)
    if resolution.outcome in {
        ResolutionOutcome.NOT_FOUND,
        ResolutionOutcome.AUTHORITATIVE,
    }:
        return None
    detail = resolution.detail or (
        f"continuity resolution returned {resolution.outcome.value}"
    )
    kind = (
        CookHoldKind.INTEGRITY
        if resolution.outcome is ResolutionOutcome.ERROR
        else CookHoldKind.BLOCKED
    )
    return CookExecutionHold(
        hold_id=f"continuity-{hashlib.sha256(canonical_identity.encode()).hexdigest()[:16]}",
        kind=kind,
        reason=detail,
    )


def _hold_result(
    request: CookPreparationRequest,
    source: ClassifiedCookInput,
    refs: Sequence[ArtifactRef],
    holds: Sequence[CookExecutionHold] = (),
    requirements: Sequence[CookUnmetRequirement] = (),
) -> CookPreparationResult:
    if not holds and not requirements:
        raise CookEvidenceError("blocked preparation requires a hold or requirement")
    return CookPreparationResult(
        contract_version=_version(CookPreparationResult),
        request_id=request.request_id,
        input_kind=source.kind,
        outcome=CookPreparationOutcome.BLOCKED,
        references=tuple(refs)
        or (_source_ref(source, request.artifact_root, request.request_id),),
        holds=tuple(holds),
        requirements=tuple(requirements),
    )


def _invalid_result(
    request: CookPreparationRequest,
    source: ClassifiedCookInput,
    refs: Sequence[ArtifactRef],
    failure: _PreparationFailure | Exception,
) -> CookPreparationResult:
    if isinstance(failure, _PreparationFailure):
        code, message, path = failure.code, str(failure), failure.path
    else:
        code, message, path = "invalid-input", str(failure), None
    return CookPreparationResult(
        contract_version=_version(CookPreparationResult),
        request_id=request.request_id,
        input_kind=source.kind,
        outcome=CookPreparationOutcome.INVALID,
        references=tuple(refs)
        or (_source_ref(source, request.artifact_root, request.request_id),),
        findings=(CookValidationFinding(code=code, message=message, path=path),),
    )


def _proposal(
    request: CookPreparationRequest,
    content: bytes,
    *,
    artifact_id: str,
) -> ArtifactRef:
    return _persist_bytes(
        request.artifact_root,
        content=content,
        artifact_id=artifact_id,
        role="proposal",
        media_type="application/json"
        if content.lstrip().startswith(b"{")
        else "text/markdown",
    )


def _scope_coverage(
    raw: bytes, readiness: MoldCookSpecReadiness | None
) -> MoldCookCoverage:
    """Derive the stable scope IDs that the host can present for approval."""
    ids: list[str] = []
    if readiness is not None and readiness.landing is not None:
        ids.extend(curd_id for layer in readiness.landing.layers for curd_id in layer)
    if not ids:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CookEvidenceError("scope proposal source is not UTF-8") from exc
        section = re.search(
            r"(?ims)^##\s+Curds\s*$([\s\S]*?)(?=^##\s+|\Z)", text
        )
        if section is not None:
            ids.extend(
                match.group(1)
                for match in re.finditer(
                    r"(?m)^\s*[-*]\s+([A-Za-z0-9][A-Za-z0-9._-]*):", section.group(1)
                )
            )
    if not ids:
        raise CookEvidenceError("scope proposal requires declared curd IDs")
    return MoldCookCoverage(curd_ids=tuple(dict.fromkeys(ids)))


def _approval_value(
    value: MoldCookApproval | ArtifactRef | str | Path | Mapping[str, object],
    *,
    request: CookPreparationRequest,
) -> tuple[MoldCookApproval, ArtifactRef]:
    if isinstance(value, ArtifactRef):
        if (
            value.role not in {"approval", "runner_approval"}
            or value.schema_uri != MOLD_COOK_APPROVAL_SCHEMA_URI
        ):
            raise CookEvidenceError(
                "approval must be a retained MoldCookApproval artifact"
            )
        approval = _load_contract(value, MoldCookApproval, request.artifact_root)
        assert isinstance(approval, MoldCookApproval)
        return approval, value
    if isinstance(value, (MoldCookApproval, Mapping)):
        raise CookEvidenceError(
            "raw approval values are not execution authority; pass the host-owned ArtifactRef"
        )
    path = Path(value).expanduser().resolve()
    raw = _read_path(path)
    digest = digest_bytes(raw)
    expected = (
        request.artifact_root.resolve() / f"sha256-{digest.removeprefix('sha256:')}"
    )
    if path != expected:
        raise CookEvidenceError("approval must be a retained host artifact reference")
    reference = ArtifactRef(
        artifact_id=f"{request.request_id}/approval",
        role="approval",
        uri=path.as_uri(),
        digest=digest,
        size_bytes=len(raw),
        media_type="application/json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    approval = _load_contract(reference, MoldCookApproval, request.artifact_root)
    assert isinstance(approval, MoldCookApproval)
    return approval, reference


def _check_approval(
    approval: MoldCookApproval,
    *,
    approval_ref: ArtifactRef,
    request: CookPreparationRequest,
    spec_ref: ArtifactRef,
    expected: MoldCookApprovalKind,
    expected_proposal: bytes | None = None,
) -> None:
    try:
        _ = validate_mold_cook_approval(approval, request.artifact_root)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise CookEvidenceError(str(exc)) from exc
    if approval.request_id != request.request_id:
        raise CookEvidenceError(
            "approval request_id does not match the preparation request"
        )
    if approval.spec_digest != spec_ref.digest:
        raise CookEvidenceError("approval is bound to a different spec")
    if approval.kind is not expected:
        raise CookEvidenceError(
            f"expected {expected.value} approval, got {approval.kind.value}"
        )
    if approval.decision is not MoldCookApprovalDecision.APPROVED:
        raise CookEvidenceError("approval is not an explicit approved response")
    if approval_ref.role not in {"approval", "runner_approval"}:
        raise CookEvidenceError("approval reference has the wrong role")
    if expected_proposal is not None:
        actual_proposal = _resolve_ref(approval.proposal_ref, request.artifact_root)
        if actual_proposal != expected_proposal:
            raise CookEvidenceError(
                "approval proposal is not the canonical envelope for this request"
            )
    source = require_relative_path(approval.response_source, "approval response_source")
    response_path = request.artifact_root.resolve() / source
    if _is_regular_path(response_path):
        if digest_bytes(_read_path(response_path)) != approval.response_ref.digest:
            raise CookEvidenceError(
                "approval response_source is detached from response_ref"
            )
    elif approval.response_source not in {
        approval.response_ref.artifact_id,
        approval.response_ref.uri,
    }:
        raise CookEvidenceError("approval response_source is not a host-owned artifact")


def _planner_request(
    request: CookPreparationRequest,
    objective: str,
    *,
    source_plan: PlannerResult | None = None,
) -> PlannerRequest:
    if source_plan is None:
        return PlannerRequest(
            contract_version=_version(PlannerRequest),
            request_id=request.request_id,
            kind=PlannerRequestKind.DECOMPOSE,
            objective=objective[:8192],
        )
    if source_plan.plan is None:
        raise CookEvidenceError("replan request requires a materialized source plan")
    from easy_cheese_schemas.contracts import SourcePlanRef

    return PlannerRequest(
        contract_version=_version(PlannerRequest),
        request_id=request.request_id,
        kind=PlannerRequestKind.REPLAN,
        objective=objective[:8192],
        source_plan_ref=SourcePlanRef(
            source_plan.plan.plan_id,
            source_plan.plan.revision,
            source_plan.plan.digest,
        ),
    )


def _coverage_for_plan(
    planner: PlannerResult,
    plan: CurdPlan,
    approval: MoldCookApproval,
) -> MoldCookCoverage:
    if planner.disposition not in {
        PlannerDisposition.COMPLETE,
        PlannerDisposition.PARTIAL,
    }:
        raise CookEvidenceError(
            f"planner disposition {planner.disposition.value} cannot authorize execution"
        )
    expected_remainder = planner.unresolved_work
    if approval.coverage.unresolved_work != expected_remainder:
        raise CookEvidenceError("approval acknowledges a stale PlannerResult remainder")
    selected = tuple(approval.coverage.curd_ids)
    selected_ids = set(selected)
    if len(selected_ids) != len(selected):
        raise CookEvidenceError("approval coverage must not repeat curd IDs")
    declared = {curd.curd_id: curd for curd in plan.curds}
    unknown = set(selected) - declared.keys()
    if unknown:
        raise CookEvidenceError(
            "approval names unknown curd IDs: " + ", ".join(sorted(unknown))
        )
    if planner.disposition is PlannerDisposition.COMPLETE:
        expected = tuple(curd.curd_id for curd in plan.curds)
        if selected != expected:
            raise CookEvidenceError("complete plan approval must cover every curd")
    for curd_id in selected:
        missing = set(declared[curd_id].dependencies) - selected_ids
        if missing:
            raise _DependencyClosureError(
                f"approval coverage for {curd_id!r} omits dependencies: "
                + ", ".join(sorted(missing))
            )
    return MoldCookCoverage(
        curd_ids=selected,
        unresolved_work=expected_remainder,
    )


def _validate_setup(
    evidence: SetupEvidence | Mapping[str, object] | ArtifactRef | str | Path,
    *,
    authorization: CookSetupAuthorization,
    plan: CurdPlan,
    request: CookPreparationRequest,
) -> ArtifactRef:
    if isinstance(evidence, ArtifactRef):
        evidence_ref = evidence
    elif isinstance(evidence, (str, Path)):
        path = Path(evidence).expanduser().resolve()
        raw = _read_path(path)
        digest = digest_bytes(raw)
        expected = (
            request.artifact_root.resolve() / f"sha256-{digest.removeprefix('sha256:')}"
        )
        if path != expected:
            raise CookEvidenceError("setup evidence must be a retained host artifact")
        evidence_ref = ArtifactRef(
            artifact_id=f"{request.request_id}/setup-evidence",
            role="setup_evidence",
            uri=path.as_uri(),
            digest=digest,
            size_bytes=len(raw),
            media_type="application/json",
            schema_uri=SETUP_EVIDENCE_SCHEMA_URI,
        )
    else:
        raise CookEvidenceError("setup evidence must be a durable host artifact")
    try:
        _ = validate_mold_cook_setup_evidence(
            evidence_ref,
            authorization=authorization,
            plan=plan,
            artifact_root=request.artifact_root,
        )
    except SetupEvidenceExecutionError as exc:
        raise _SetupExecutionFailed(str(exc)) from exc
    except ContractValidationError as exc:
        raise CookEvidenceError(str(exc)) from exc
    return evidence_ref


def _validate_handoff_authority(
    handoff: MoldCookHandoff,
    *,
    request: CookPreparationRequest,
) -> None:
    if handoff.setup_evidence_refs and handoff.runner_approval_ref is None:
        raise CookEvidenceError(
            "setup evidence requires a bound runner approval reference"
        )
    if handoff.runner_approval_ref is None:
        return
    runner = _load_contract(
        handoff.runner_approval_ref,
        MoldCookApproval,
        request.artifact_root,
    )
    assert isinstance(runner, MoldCookApproval)
    authorization = runner.setup_authorization
    if authorization is None:
        raise CookEvidenceError("runner approval has no setup authorization")
    expected_proposal = canonical_mold_cook_proposal(
        request_id=handoff.request_id,
        kind=MoldCookApprovalKind.RUNNER,
        spec_digest=handoff.spec_ref.digest,
        coverage=handoff.coverage,
        setup_authorization=authorization,
    )
    _check_approval(
        runner,
        approval_ref=handoff.runner_approval_ref,
        request=request,
        spec_ref=handoff.spec_ref,
        expected=MoldCookApprovalKind.RUNNER,
        expected_proposal=expected_proposal,
    )
    if handoff.plan_ref is None:
        raise CookEvidenceError("setup evidence requires a materialized plan")
    plan = _load_contract(handoff.plan_ref, CurdPlan, request.artifact_root)
    assert isinstance(plan, CurdPlan)
    for evidence_ref in handoff.setup_evidence_refs:
        _ = _validate_setup(
            evidence_ref,
            authorization=authorization,
            plan=plan,
            request=request,
        )


def _pointer_ref(path: Path, *, request_id: str) -> ArtifactRef:
    raw = _read_path(path)
    return ArtifactRef(
        artifact_id=f"{request_id}/handoff-pointer",
        role="handoff",
        uri=path.resolve().as_uri(),
        digest=digest_bytes(raw),
        size_bytes=len(raw),
        media_type="application/json",
        schema_uri=f"{SCHEMA_ROOT}/handoff-pointer",
    )


def _publish_handoff(
    request: CookPreparationRequest,
    *,
    source: ClassifiedCookInput,
    spec_ref: ArtifactRef,
    approval_ref: ArtifactRef,
    coverage: MoldCookCoverage,
    planner_result_ref: ArtifactRef | None,
    plan_ref: ArtifactRef | None,
    taste_verdict_ref: ArtifactRef | None = None,
    taste_ledger_ref: ArtifactRef | None = None,
    runner_approval_ref: ArtifactRef | None = None,
    setup_evidence_refs: Sequence[ArtifactRef] = (),
) -> ArtifactRef:
    handoff = MoldCookHandoff(
        contract_version=_version(MoldCookHandoff),
        request_id=request.request_id,
        input_kind=source.kind,
        mode=request.mode,
        spec_ref=spec_ref,
        approval_ref=approval_ref,
        coverage=coverage,
        planner_result_ref=planner_result_ref,
        plan_ref=plan_ref,
        taste_verdict_ref=taste_verdict_ref,
        taste_ledger_ref=taste_ledger_ref,
        runner_approval_ref=runner_approval_ref,
        setup_evidence_refs=tuple(setup_evidence_refs),
    )
    try:
        _validate_handoff_authority(handoff, request=request)
        validated = validate_mold_cook_handoff(handoff, request.artifact_root)
        canonical = canonical_bytes(validated)
        request_digest = digest_bytes(canonical)
        operation_id = (
            "cook-"
            + hashlib.sha256(
                f"{request.request_id}:{request_digest}".encode()
            ).hexdigest()[:24]
        )
        _ = publish_mold_cook_handoff(
            validated,
            request_digest=request_digest,
            operation_id=operation_id,
            artifact_root=request.artifact_root,
        )
        return _pointer_ref(
            request.artifact_root / "pointers" / f"{operation_id}.json",
            request_id=request.request_id,
        )
    except (ContractValidationError, CookEvidenceError, ValueError, OSError) as exc:
        raise CookEvidenceError(f"handoff could not be published: {exc}") from exc


def _ready_result(
    request: CookPreparationRequest,
    source: ClassifiedCookInput,
    refs: Sequence[ArtifactRef],
    handoff_ref: ArtifactRef,
    coverage: MoldCookCoverage,
) -> CookPreparationResult:
    return CookPreparationResult(
        contract_version=_version(CookPreparationResult),
        request_id=request.request_id,
        input_kind=source.kind,
        outcome=CookPreparationOutcome.READY,
        references=tuple((*refs, handoff_ref)),
        handoff_ref=handoff_ref,
        coverage=coverage,
    )


def _pointer_artifact_root(pointer_path: Path) -> Path:
    resolved = pointer_path.resolve()
    if resolved.parent.name == "pointers":
        return resolved.parent.parent
    return resolved.parent


def _read_pointer(
    source: ClassifiedCookInput,
) -> tuple[HandoffPointer, list[ArtifactRef]]:
    if source.path is None:
        raise _PreparationFailure(
            "missing-pointer", "canonical pointer input must name a file"
        )
    pointer_raw = _read_path(source.path)
    try:
        pointer = validate_contract(
            pointer_raw, HandoffPointer, _version(HandoffPointer)
        ).value
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise _PreparationFailure(
            "invalid-pointer", str(exc), path=str(source.path)
        ) from exc
    assert isinstance(pointer, HandoffPointer)
    refs = [pointer.payload]
    if pointer.normalization_receipt is not None:
        refs.append(pointer.normalization_receipt)
    return pointer, refs


def _legacy_plan(
    source: ClassifiedCookInput,
    *,
    artifact_root: Path,
) -> _LegacyPlanMigration | None:
    if source.path is None:
        return None
    pointer, _ = _read_pointer(source)
    if pointer.payload.schema_uri != CURD_PLAN_SCHEMA_URI:
        return None
    if pointer.payload.role != "curd_plan":
        raise _PreparationFailure(
            "invalid-pointer", "legacy pointer payload must use the curd_plan role", path=str(source.path)
        )
    if (pointer.source_phase, pointer.destination_phase) != ("mold", "cook"):
        raise _PreparationFailure(
            "invalid-pointer", "legacy pointer must use the mold-to-cook route", path=str(source.path)
        )
    try:
        root = _pointer_artifact_root(source.path)
        resolved = resolve_artifact(
            pointer.payload,
            repository_root=root,
            artifact_directory=artifact_root,
            allowed_local_root=root,
        )
        canonical = validate_contract(
            resolved.content,
            CurdPlan,
            _version(CurdPlan),
        )
        if pointer.normalization_receipt is not None:
            receipt_resolved = resolve_artifact(
                attrs.evolve(pointer.normalization_receipt, schema_uri=None),
                repository_root=root,
                artifact_directory=artifact_root,
                allowed_local_root=root,
            )
            try:
                receipt_payload = cast(object, json.loads(receipt_resolved.content))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ContractValidationError(
                    "legacy normalization receipt is not valid JSON"
                ) from exc
            if not isinstance(receipt_payload, Mapping):
                raise ContractValidationError(
                    "legacy normalization receipt must be a JSON object"
                )
            receipt_mapping = dict(cast("Mapping[str, object]", receipt_payload))
            _ = receipt_mapping.pop("contract_version", None)
            receipt = cast(
                "NormalizationReceipt",
                validate_contract(
                    canonical_bytes(receipt_mapping),
                    NormalizationReceipt,
                    None,
                ).value,
            )
            if (
                receipt.source_digest != pointer.payload.digest
                or receipt.canonical_digest != pointer.payload.digest
                or receipt.source_schema_uri != CURD_PLAN_SCHEMA_URI
            ):
                raise ContractValidationError(
                    "legacy normalization receipt is not bound to the curd plan"
                )
    except (
        ArtifactDigestMismatchError,
        ArtifactResolutionError,
        ContractValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise _PreparationFailure(
            "invalid-pointer", str(exc), path=str(source.path)
        ) from exc
    plan = cast(CurdPlan, canonical.value)
    return _LegacyPlanMigration(
        plan=plan,
        plan_ref=attrs.evolve(pointer.payload, role="curd_plan"),
        normalization_receipt_ref=pointer.normalization_receipt,
    )


@attrs.define(frozen=True)
class _RunnerSetup:
    runner_approval_ref: ArtifactRef | None
    setup_evidence_refs: tuple[ArtifactRef, ...]


def _apply_runner_setup(
    request: CookPreparationRequest,
    source: ClassifiedCookInput,
    refs: list[ArtifactRef],
    *,
    authority_request: CookPreparationRequest,
    runner_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None,
    setup_evidence: SetupEvidence
    | Mapping[str, object]
    | ArtifactRef
    | str
    | Path
    | None,
    setup_authorization: CookSetupAuthorization
    | ArtifactRef
    | Mapping[str, object]
    | str
    | Path
    | None,
    spec_ref: ArtifactRef,
    coverage: MoldCookCoverage,
    plan: CurdPlan,
    plan_ref: ArtifactRef,
) -> _RunnerSetup | CookPreparationResult:
    """Check runner approval and setup evidence, appending accepted refs.

    ``request`` names the result's identity; ``authority_request`` names the
    identity the approval evidence must bind to.  The two differ when Cook
    extends an accepted handoff.  A returned ``CookPreparationResult`` is a
    closed outcome the caller returns unchanged.
    """

    runner_handoff_ref: ArtifactRef | None = None
    authorization: CookSetupAuthorization | None = None
    setup_refs: list[ArtifactRef] = []
    if runner_approval is not None:
        runner, runner_ref = _approval_value(
            runner_approval,
            request=authority_request,
        )
        authorization = runner.setup_authorization
        if authorization is None:
            raise CookEvidenceError("runner approval lacks setup authorization")
        if setup_authorization is not None:
            if not isinstance(setup_authorization, CookSetupAuthorization):
                raise CookEvidenceError(
                    "setup_authorization must be the canonical runner authorization"
                )
            if setup_authorization != authorization:
                raise CookEvidenceError(
                    "setup_authorization does not match runner approval"
                )
        runner_proposal = canonical_mold_cook_proposal(
            request_id=authority_request.request_id,
            kind=MoldCookApprovalKind.RUNNER,
            spec_digest=spec_ref.digest,
            coverage=coverage,
            setup_authorization=authorization,
        )
        _check_approval(
            runner,
            approval_ref=runner_ref,
            request=authority_request,
            spec_ref=spec_ref,
            expected=MoldCookApprovalKind.RUNNER,
            expected_proposal=runner_proposal,
        )
        refs.append(runner_ref)
        runner_handoff_ref = attrs.evolve(runner_ref, role="runner_approval")
    if authorization is None:
        if setup_evidence is not None:
            raise CookEvidenceError(
                "setup evidence cannot be accepted without runner approval"
            )
    elif setup_evidence is None:
        return validate_preparation_result(
            CookPreparationResult(
                contract_version=_version(CookPreparationResult),
                request_id=request.request_id,
                input_kind=source.kind,
                outcome=CookPreparationOutcome.NEEDS_PREPARATION,
                references=tuple(refs),
                approved_plan_ref=plan_ref,
                coverage=coverage,
                setup_authorization=authorization,
            )
        )
    else:
        try:
            setup_ref = _validate_setup(
                setup_evidence,
                authorization=authorization,
                plan=plan,
                request=authority_request,
            )
        except _SetupExecutionFailed as exc:
            if isinstance(setup_evidence, ArtifactRef):
                refs.append(setup_evidence)
            return validate_preparation_result(
                _hold_result(
                    request,
                    source,
                    refs,
                    (
                        CookExecutionHold(
                            hold_id=f"setup-failed-{request.request_id}",
                            kind=CookHoldKind.BLOCKED,
                            reason=str(exc),
                        ),
                    ),
                )
            )
        setup_refs.append(setup_ref)
        refs.append(setup_ref)
    return _RunnerSetup(
        runner_approval_ref=runner_handoff_ref,
        setup_evidence_refs=tuple(setup_refs),
    )


def _canonical_pointer(
    source: ClassifiedCookInput,
    request: CookPreparationRequest,
    *,
    runner_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None = None,
    setup_authorization: CookSetupAuthorization
    | ArtifactRef
    | Mapping[str, object]
    | str
    | Path
    | None = None,
    setup_evidence: SetupEvidence
    | Mapping[str, object]
    | ArtifactRef
    | str
    | Path
    | None = None,
) -> CookPreparationResult:
    pointer, refs = _read_pointer(source)
    if pointer.payload.schema_uri != _version(MoldCookHandoff).schema_uri:
        raise _PreparationFailure(
            "unsupported-pointer-schema",
            f"pointer payload schema {pointer.payload.schema_uri!r} is not supported by Cook",
            path=str(source.path),
        )
    assert source.path is not None
    pointer_root = request.artifact_root.resolve()
    if not source.path.resolve().is_relative_to(pointer_root):
        raise _PreparationFailure(
            "pointer-outside-artifact-root",
            f"canonical pointer is outside artifact root {str(pointer_root)!r}",
            path=str(source.path),
        )
    accepted = accept_mold_cook_handoff(
        source.path,
        artifact_root=pointer_root,
    )
    handoff = cast(MoldCookHandoff, accepted.canonical.value)
    handoff = validate_mold_cook_handoff(handoff, pointer_root)
    _validate_handoff_authority(handoff, request=request)
    pointer_ref = _pointer_ref(source.path, request_id=request.request_id)
    refs.extend(
        (
            pointer_ref,
            handoff.spec_ref,
            handoff.approval_ref,
            *(
                (handoff.planner_result_ref, handoff.plan_ref)
                if handoff.planner_result_ref is not None
                and handoff.plan_ref is not None
                else ()
            ),
            *(
                (handoff.taste_verdict_ref, handoff.taste_ledger_ref)
                if handoff.taste_verdict_ref is not None
                and handoff.taste_ledger_ref is not None
                else ()
            ),
            *((handoff.runner_approval_ref,) if handoff.runner_approval_ref else ()),
            *handoff.setup_evidence_refs,
        )
    )
    extends_setup = (
        runner_approval is not None
        or setup_authorization is not None
        or setup_evidence is not None
    )
    if not extends_setup:
        return _ready_result(request, source, refs, pointer_ref, handoff.coverage)
    if handoff.runner_approval_ref is not None or handoff.setup_evidence_refs:
        raise CookEvidenceError(
            "an accepted handoff's setup authority cannot be replaced"
        )
    if setup_authorization is not None and runner_approval is None:
        raise CookEvidenceError(
            "setup authorization requires explicit runner approval evidence"
        )
    if setup_evidence is not None and runner_approval is None:
        raise CookEvidenceError(
            "setup evidence cannot be accepted without runner approval"
        )
    if runner_approval is None:
        raise CookEvidenceError("runner approval is required for setup")
    if handoff.plan_ref is None:
        raise CookEvidenceError("runner setup requires a full handoff plan")
    plan = _load_contract(handoff.plan_ref, CurdPlan, pointer_root)
    assert isinstance(plan, CurdPlan)
    authority_request = attrs.evolve(request, request_id=handoff.request_id)
    applied = _apply_runner_setup(
        request,
        source,
        refs,
        authority_request=authority_request,
        runner_approval=runner_approval,
        setup_evidence=setup_evidence,
        setup_authorization=setup_authorization,
        spec_ref=handoff.spec_ref,
        coverage=handoff.coverage,
        plan=plan,
        plan_ref=handoff.plan_ref,
    )
    if isinstance(applied, CookPreparationResult):
        return applied
    handoff_ref = _publish_handoff(
        authority_request,
        source=source,
        spec_ref=handoff.spec_ref,
        approval_ref=handoff.approval_ref,
        coverage=handoff.coverage,
        planner_result_ref=handoff.planner_result_ref,
        plan_ref=handoff.plan_ref,
        taste_verdict_ref=handoff.taste_verdict_ref,
        taste_ledger_ref=handoff.taste_ledger_ref,
        runner_approval_ref=applied.runner_approval_ref,
        setup_evidence_refs=applied.setup_evidence_refs,
    )
    return validate_preparation_result(
        _ready_result(request, source, refs, handoff_ref, handoff.coverage)
    )


@attrs.define(frozen=True)
class _ResolvedPreparationSource:
    processing_source: ClassifiedCookInput
    planner_value: PlannerResult | None
    planner_ref: ArtifactRef | None
    plan_ref: ArtifactRef | None
    spec_ref: ArtifactRef | None
    readiness: MoldCookSpecReadiness | None
    objective: str
    legacy_mode: bool


def _adopt_legacy_plan(
    legacy: _LegacyPlanMigration,
    *,
    classified: ClassifiedCookInput,
    request: CookPreparationRequest,
    artifacts: Path,
    refs: list[ArtifactRef],
    spec_binding: ArtifactRef | str | Path | None,
    previous_result: CookPreparationResult | None,
    objective: str,
    requirement_id: str,
    requirement_description: str,
) -> _ResolvedPreparationSource | CookPreparationResult:
    """Bind a historical plan to a canonical spec, or report what it still needs.

    This is the only surviving ingress that reads a legacy artifact, so the
    adapter sunset check runs here: an expired adapter must fail the run rather
    than migrate on a rule nobody maintains.
    """

    check_adapter_sunsets(date.today())
    if spec_binding is None and previous_result is not None:
        spec_binding = next(
            (item for item in previous_result.references if item.role == "spec"),
            None,
        )
    if spec_binding is None:
        return validate_preparation_result(
            _hold_result(
                request,
                classified,
                refs,
                requirements=(
                    CookUnmetRequirement(
                        requirement_id=requirement_id,
                        kind=CookRequirementKind.SCOPE,
                        description=requirement_description,
                    ),
                ),
            )
        )
    spec_ref, bound_objective = _bound_spec_ref(spec_binding, request=request)
    processing_source = ClassifiedCookInput(
        MoldCookInputKind.TASK,
        bound_objective,
    )
    readiness = evaluate_mold_cook_spec(
        _resolve_ref(spec_ref, artifacts),
        spec_ref=spec_ref,
    )
    planner_value = PlannerResult(
        contract_version=_version(PlannerResult),
        request_id=request.request_id,
        disposition=PlannerDisposition.COMPLETE,
        plan=legacy.plan,
    )
    planner_ref = _persist_value(
        artifacts,
        planner_value,
        artifact_id=f"{request.request_id}/planner-result",
        role="planner_result",
        schema_uri=_version(PlannerResult).schema_uri,
    )
    refs.append(planner_ref)
    return _ResolvedPreparationSource(
        processing_source=processing_source,
        planner_value=planner_value,
        planner_ref=planner_ref,
        plan_ref=legacy.plan_ref,
        spec_ref=spec_ref,
        readiness=readiness,
        objective=objective,
        legacy_mode=True,
    )


def _resolve_preparation_source(
    *,
    classified: ClassifiedCookInput,
    request: CookPreparationRequest,
    root: Path,
    artifacts: Path,
    refs: list[ArtifactRef],
    previous_result: CookPreparationResult | None,
    spec_binding: ArtifactRef | str | Path | None,
    runner_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None,
    setup_authorization: CookSetupAuthorization
    | ArtifactRef
    | Mapping[str, object]
    | str
    | Path
    | None,
    setup_evidence: SetupEvidence
    | Mapping[str, object]
    | ArtifactRef
    | str
    | Path
    | None,
) -> _ResolvedPreparationSource | CookPreparationResult:
    legacy: _LegacyPlanMigration | None = None
    processing_source: ClassifiedCookInput = classified
    planner_value: PlannerResult | None = None
    planner_ref: ArtifactRef | None = None
    plan_ref: ArtifactRef | None = None
    spec_ref: ArtifactRef | None = None
    readiness: MoldCookSpecReadiness | None = None
    objective = classified.source
    legacy_mode = False

    if classified.kind is MoldCookInputKind.DIRECT_SPEC:
        if classified.path is None:
            raise _PreparationFailure(
                "missing-spec",
                "direct spec input must name a file",
            )
        spec_ref, objective = _spec_ref(
            classified,
            artifacts,
            request.request_id,
        )
        readiness = evaluate_mold_cook_spec(
            _resolve_ref(spec_ref, artifacts),
            spec_ref=spec_ref,
        )

    elif classified.kind is MoldCookInputKind.SLUG:
        spec_ref, objective = _spec_ref(
            classified,
            artifacts,
            request.request_id,
        )
        readiness = _spec_readiness(
            classified,
            spec_ref=spec_ref,
            raw=_resolve_ref(spec_ref, artifacts),
        )
    elif classified.kind is MoldCookInputKind.CANONICAL_POINTER:
        if classified.path is None:
            raise _PreparationFailure(
                "missing-pointer",
                "canonical pointer input must name a file",
            )
        legacy = _legacy_plan(classified, artifact_root=artifacts)
        if legacy is None:
            result = _canonical_pointer(
                classified,
                request,
                runner_approval=runner_approval,
                setup_authorization=setup_authorization,
                setup_evidence=setup_evidence,
            )
            return validate_preparation_result(
                attrs.evolve(
                    result,
                    references=tuple((*refs, *result.references)),
                )
            )
        refs.extend(
            (
                _pointer_ref(classified.path, request_id=request.request_id),
                legacy.plan_ref,
                *(
                    (legacy.normalization_receipt_ref,)
                    if legacy.normalization_receipt_ref is not None
                    else ()
                ),
            )
        )
        return _adopt_legacy_plan(
            legacy,
            classified=classified,
            request=request,
            artifacts=artifacts,
            refs=refs,
            spec_binding=spec_binding,
            previous_result=previous_result,
            objective=(
                "migrate the historical CurdPlan into a canonical Mold-to-Cook handoff"
            ),
            requirement_id="legacy-spec-binding",
            requirement_description=(
                "an intact historical CurdPlan requires a canonical "
                "host-bound Mold spec before migration"
            ),
        )
    elif classified.kind is MoldCookInputKind.CONTINUATION:
        continuation_ref = _source_ref(classified, artifacts, request.request_id)
        refs.append(continuation_ref)
        resolution = resolve(classified.source, workspace_root=root)
        if resolution.outcome in {
            ResolutionOutcome.AUTHORITATIVE,
            ResolutionOutcome.NOT_FOUND,
        }:
            processing_source = ClassifiedCookInput(
                MoldCookInputKind.TASK,
                classified.source,
            )
            objective = classified.source
        elif resolution.outcome is ResolutionOutcome.LEGACY:
            legacy = (
                _legacy_plan(classified, artifact_root=artifacts)
                if classified.path is not None
                else None
            )
            if legacy is None:
                raise _PreparationFailure(
                    "legacy-continuation",
                    resolution.detail or "legacy continuation could not be adapted",
                )
            refs.append(legacy.plan_ref)
            return _adopt_legacy_plan(
                legacy,
                classified=classified,
                request=request,
                artifacts=artifacts,
                refs=refs,
                spec_binding=spec_binding,
                previous_result=previous_result,
                objective=(
                    "migrate the historical continuation into a canonical Cook handoff"
                ),
                requirement_id="legacy-spec-binding",
                requirement_description="legacy continuation requires a bound spec",
            )
        else:
            hold_kind = (
                CookHoldKind.INTEGRITY
                if resolution.outcome is ResolutionOutcome.ERROR
                else CookHoldKind.BLOCKED
            )
            return validate_preparation_result(
                _hold_result(
                    request,
                    classified,
                    refs,
                    (
                        CookExecutionHold(
                            hold_id=f"continuation-{request.request_id}",
                            kind=hold_kind,
                            reason=resolution.detail
                            or f"continuation is {resolution.outcome.value}",
                        ),
                    ),
                )
            )
    return _ResolvedPreparationSource(
        processing_source=processing_source,
        planner_value=planner_value,
        planner_ref=planner_ref,
        plan_ref=plan_ref,
        spec_ref=spec_ref,
        readiness=readiness,
        objective=objective,
        legacy_mode=legacy_mode,
    )


def prepare(
    source: str | Path | ClassifiedCookInput,
    *,
    request_id: str | None = None,
    repository_root: str | Path = ".",
    artifact_root: str | Path = ".cheese/cook",
    mode: MoldCookMode = MoldCookMode.FULL,
    explicit_kind: MoldCookInputKind | str | None = None,
    scope_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None = None,
    plan_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None = None,
    runner_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None = None,
    planner_result: PlannerResult | ArtifactRef | str | Path | None = None,
    planner_view: PlannerResultWriterView | None = None,
    planner_dispatch: Callable[[PlannerRequest], object] | None = None,
    setup_authorization: CookSetupAuthorization
    | ArtifactRef
    | Mapping[str, object]
    | str
    | Path
    | None = None,
    setup_evidence: SetupEvidence
    | Mapping[str, object]
    | ArtifactRef
    | str
    | Path
    | None = None,
    spec_binding: ArtifactRef | str | Path | None = None,
    holds: Sequence[CookExecutionHold] = (),
    previous: CookPreparationResult | None = None,
) -> CookPreparationResult:
    """Recompute one preparation outcome from host-owned evidence."""

    mode = MoldCookMode(mode)
    root = Path(repository_root).resolve()
    artifacts = Path(artifact_root).resolve()
    try:
        classified = (
            source
            if isinstance(source, ClassifiedCookInput)
            else classify_input(source, explicit_kind=explicit_kind)
        )
    except CookInputError as exc:
        fallback = ClassifiedCookInput(
            _kind(explicit_kind) or MoldCookInputKind.TASK,
            str(source),
            _as_path(source) if isinstance(source, (str, Path)) else None,
            explicit_kind is not None,
        )
        request = CookPreparationRequest(
            request_id=request_id or _request_id(fallback, None),
            source=fallback,
            repository_root=root,
            artifact_root=artifacts,
            mode=mode,
            explicit_kind=_kind(explicit_kind),
            holds=tuple(holds),
        )
        return _invalid_result(
            request,
            fallback,
            [_persist_request(request)],
            _PreparationFailure("invalid-input", str(exc)),
        )

    request = CookPreparationRequest(
        request_id=request_id or _request_id(classified, None),
        source=classified,
        repository_root=root,
        artifact_root=artifacts,
        mode=mode,
        explicit_kind=_kind(explicit_kind),
        holds=tuple(holds),
    )
    refs: list[ArtifactRef] = [_persist_request(request)]
    previous_result = previous
    try:
        if previous_result is not None:
            previous_result = validate_preparation_result(previous_result)
            refs.append(
                _persist_value(
                    artifacts,
                    previous_result,
                    artifact_id=f"{request.request_id}/previous-result",
                    role="preparation_result",
                    schema_uri=_version(CookPreparationResult).schema_uri,
                )
            )
        if request.holds:
            return validate_preparation_result(
                _hold_result(request, classified, refs, request.holds)
            )
        resolved_source = _resolve_preparation_source(
            classified=classified,
            request=request,
            root=root,
            artifacts=artifacts,
            refs=refs,
            previous_result=previous_result,
            spec_binding=spec_binding,
            runner_approval=runner_approval,
            setup_authorization=setup_authorization,
            setup_evidence=setup_evidence,
        )
        if isinstance(resolved_source, CookPreparationResult):
            return resolved_source
        processing_source = resolved_source.processing_source
        planner_value = resolved_source.planner_value
        planner_ref = resolved_source.planner_ref
        plan_ref = resolved_source.plan_ref
        spec_ref = resolved_source.spec_ref
        readiness = resolved_source.readiness
        objective = resolved_source.objective
        legacy_mode = resolved_source.legacy_mode

        if spec_binding is not None and spec_ref is None:
            spec_ref, objective = _bound_spec_ref(spec_binding, request=request)
            processing_source = ClassifiedCookInput(
                MoldCookInputKind.TASK,
                objective,
            )
            readiness = evaluate_mold_cook_spec(
                _resolve_ref(spec_ref, artifacts),
                spec_ref=spec_ref,
            )
        if spec_ref is None:
            return validate_preparation_result(
                _hold_result(
                    request,
                    classified,
                    refs,
                    (
                        CookExecutionHold(
                            hold_id=f"missing-spec-{request.request_id}",
                            kind=CookHoldKind.BLOCKED,
                            reason="Cook requires a canonical host-bound Mold spec",
                        ),
                    ),
                )
            )
        if spec_ref not in refs:
            refs.append(spec_ref)
        spec_raw = _resolve_ref(spec_ref, artifacts)
        if readiness is None:
            readiness = _spec_readiness(
                processing_source,
                spec_ref=spec_ref,
                raw=spec_raw,
            )
        if readiness is not None:
            continuity = _continuity_hold(
                processing_source,
                root,
                identity=readiness.spec_slug,
            )
            if continuity is not None:
                return validate_preparation_result(
                    _hold_result(request, classified, refs, (continuity,))
                )

        if (setup_authorization is not None or setup_evidence is not None) and (
            runner_approval is None
        ):
            raise CookEvidenceError(
                "setup authority and evidence must be derived from runner approval"
            )

        approved_scope_ref: ArtifactRef | None = None
        if not legacy_mode:
            if scope_approval is None:
                scope_coverage = _scope_coverage(spec_raw, readiness)
                proposal = canonical_mold_cook_proposal(
                    request_id=request.request_id,
                    kind=MoldCookApprovalKind.SCOPE,
                    spec_digest=spec_ref.digest,
                    coverage=scope_coverage,
                )
                proposal_ref = _proposal(
                    request,
                    proposal,
                    artifact_id=f"{request.request_id}/scope-proposal",
                )
                return validate_preparation_result(
                    CookPreparationResult(
                        contract_version=_version(CookPreparationResult),
                        request_id=request.request_id,
                        input_kind=classified.kind,
                        outcome=CookPreparationOutcome.NEEDS_APPROVAL,
                        references=tuple((*refs, proposal_ref)),
                        approval_kind=MoldCookApprovalKind.SCOPE,
                        proposal_ref=proposal_ref,
                        proposal_digest=proposal_ref.digest,
                        missing_decision="explicit scope approval",
                    )
                )
            scope, scope_ref = _approval_value(scope_approval, request=request)
            scope_proposal = canonical_mold_cook_proposal(
                request_id=request.request_id,
                kind=MoldCookApprovalKind.SCOPE,
                spec_digest=spec_ref.digest,
                coverage=scope.coverage,
            )
            _check_approval(
                scope,
                approval_ref=scope_ref,
                request=request,
                spec_ref=spec_ref,
                expected=MoldCookApprovalKind.SCOPE,
                expected_proposal=scope_proposal,
            )
            if previous_result is not None and previous_result.proposal_ref is not None:
                previous_proposal = _resolve_ref(
                    previous_result.proposal_ref,
                    artifacts,
                )
                if previous_proposal != scope_proposal:
                    raise CookEvidenceError(
                        "resubmission changed the displayed scope proposal"
                    )
            refs.append(scope_ref)
            approved_scope_ref = attrs.evolve(scope_ref, role="approved_scope")
            if request.mode is MoldCookMode.LIGHT:
                if len(scope.coverage.curd_ids) != 1 or scope.coverage.unresolved_work:
                    raise CookEvidenceError(
                        "Light authorization must name exactly one resolved curd"
                    )
                handoff_ref = _publish_handoff(
                    request,
                    source=classified,
                    spec_ref=spec_ref,
                    approval_ref=scope_ref,
                    coverage=scope.coverage,
                    planner_result_ref=None,
                    plan_ref=None,
                    taste_verdict_ref=(
                        None if readiness is None else readiness.taste_verdict_ref
                    ),
                    taste_ledger_ref=(
                        None if readiness is None else readiness.taste_ledger_ref
                    ),
                )
                return validate_preparation_result(
                    _ready_result(
                        request,
                        classified,
                        [*refs, approved_scope_ref],
                        handoff_ref,
                        scope.coverage,
                    )
                )

        if planner_value is None:
            if planner_result is None and planner_view is None:
                planner_request = _planner_request(request, objective)
                references = (
                    (*refs, approved_scope_ref)
                    if approved_scope_ref is not None
                    else tuple(refs)
                )
                return validate_preparation_result(
                    CookPreparationResult(
                        contract_version=_version(CookPreparationResult),
                        request_id=request.request_id,
                        input_kind=classified.kind,
                        outcome=CookPreparationOutcome.NEEDS_PLANNING,
                        references=references,
                        approved_scope_ref=approved_scope_ref,
                        planner_request=planner_request,
                    )
                )
            if planner_result is None:
                planner_request = _planner_request(request, objective)
                dispatch = planner_dispatch
                if planner_view is not None:

                    def planner_view_dispatch(_request: PlannerRequest) -> object:
                        return planner_view

                    dispatch = planner_view_dispatch
                if dispatch is None:
                    raise CookEvidenceError(
                        "planner output requires an orchestrator callback"
                    )
                try:
                    planner_value = workflow_plan(planner_request, dispatch)
                except (ContractValidationError, TypeError, ValueError) as exc:
                    return validate_preparation_result(
                        _hold_result(
                            request,
                            classified,
                            refs,
                            holds=(
                                CookExecutionHold(
                                    hold_id=f"planner-{request.request_id}",
                                    kind=CookHoldKind.INTEGRITY,
                                    reason=f"planner execution failed: {exc}",
                                ),
                            ),
                        )
                    )
            elif isinstance(planner_result, PlannerResult):
                planner_value = planner_result
            elif isinstance(planner_result, ArtifactRef):
                planner_value = cast(
                    PlannerResult,
                    _load_contract(planner_result, PlannerResult, artifacts),
                )
                refs.append(planner_result)
            else:
                planner_raw = _read_path(Path(planner_result).expanduser())
                planner_value = cast(
                    PlannerResult,
                    validate_contract(
                        planner_raw,
                        PlannerResult,
                        _version(PlannerResult),
                    ).value,
                )
                refs.append(
                    _persist_bytes(
                        artifacts,
                        content=planner_raw,
                        artifact_id=f"{request.request_id}/planner-result",
                        role="planner_result",
                        media_type="application/json",
                        schema_uri=_version(PlannerResult).schema_uri,
                    )
                )
        assert planner_value is not None
        if planner_ref is None:
            planner_ref = _persist_value(
                artifacts,
                planner_value,
                artifact_id=f"{request.request_id}/planner-result",
                role="planner_result",
                schema_uri=_version(PlannerResult).schema_uri,
            )
            refs.append(planner_ref)
        if planner_value.disposition in {
            PlannerDisposition.BLOCKED,
            PlannerDisposition.EXECUTOR_FAILURE,
            PlannerDisposition.NO_WORK,
        }:
            requirement_kind = (
                CookRequirementKind.INTEGRITY
                if planner_value.disposition is PlannerDisposition.EXECUTOR_FAILURE
                else CookRequirementKind.PLAN
            )
            return validate_preparation_result(
                _hold_result(
                    request,
                    classified,
                    refs,
                    requirements=(
                        CookUnmetRequirement(
                            requirement_id=f"planner-{planner_value.disposition.value}",
                            kind=requirement_kind,
                            description=(
                                planner_value.reason or planner_value.disposition.value
                            ),
                            evidence=(planner_ref,),
                        ),
                    ),
                )
            )
        if planner_value.plan is None:
            planner_request = _planner_request(request, objective)
            references = (
                (*refs, approved_scope_ref)
                if approved_scope_ref is not None
                else tuple(refs)
            )
            return validate_preparation_result(
                CookPreparationResult(
                    contract_version=_version(CookPreparationResult),
                    request_id=request.request_id,
                    input_kind=classified.kind,
                    outcome=CookPreparationOutcome.NEEDS_PLANNING,
                    references=references,
                    approved_scope_ref=approved_scope_ref,
                    planner_request=planner_request,
                )
            )
        plan = planner_value.plan
        if plan_ref is None:
            plan_ref = _persist_value(
                artifacts,
                plan,
                artifact_id=f"{request.request_id}/curd-plan",
                role="curd_plan",
                schema_uri=_version(CurdPlan).schema_uri,
            )
            refs.append(plan_ref)
        candidate_coverage = MoldCookCoverage(
            curd_ids=tuple(curd.curd_id for curd in plan.curds),
            unresolved_work=planner_value.unresolved_work,
        )
        expected_kind = (
            MoldCookApprovalKind.PARTIAL_PLAN
            if planner_value.disposition is PlannerDisposition.PARTIAL
            else MoldCookApprovalKind.PLAN
        )
        if plan_approval is None:
            proposal = canonical_mold_cook_proposal(
                request_id=request.request_id,
                kind=expected_kind,
                spec_digest=spec_ref.digest,
                coverage=candidate_coverage,
                planner_result=planner_value,
                plan_digest=plan.digest,
            )
            proposal_ref = _proposal(
                request,
                proposal,
                artifact_id=f"{request.request_id}/plan-proposal",
            )
            references = (
                (*refs, approved_scope_ref)
                if approved_scope_ref is not None
                else tuple(refs)
            )
            return validate_preparation_result(
                CookPreparationResult(
                    contract_version=_version(CookPreparationResult),
                    request_id=request.request_id,
                    input_kind=classified.kind,
                    outcome=CookPreparationOutcome.NEEDS_APPROVAL,
                    references=tuple((*references, proposal_ref)),
                    approval_kind=expected_kind,
                    proposal_ref=proposal_ref,
                    proposal_digest=proposal_ref.digest,
                    missing_decision="explicit plan approval",
                )
            )
        approval, approval_ref = _approval_value(plan_approval, request=request)
        expected_proposal = canonical_mold_cook_proposal(
            request_id=request.request_id,
            kind=expected_kind,
            spec_digest=spec_ref.digest,
            coverage=approval.coverage,
            planner_result=planner_value,
            plan_digest=plan.digest,
        )
        if previous_result is not None and previous_result.proposal_ref is not None:
            previous_proposal = _resolve_ref(
                previous_result.proposal_ref,
                artifacts,
            )
            if previous_proposal != expected_proposal:
                raise CookEvidenceError(
                    "resubmission changed the displayed plan proposal"
                )
        _check_approval(
            approval,
            approval_ref=approval_ref,
            request=request,
            spec_ref=spec_ref,
            expected=expected_kind,
            expected_proposal=expected_proposal,
        )
        try:
            coverage = _coverage_for_plan(planner_value, plan, approval)
        except _DependencyClosureError:
            planner_request = _planner_request(
                request,
                "replan approval coverage with its required dependencies",
                source_plan=planner_value,
            )
            return validate_preparation_result(
                CookPreparationResult(
                    contract_version=_version(CookPreparationResult),
                    request_id=request.request_id,
                    input_kind=classified.kind,
                    outcome=CookPreparationOutcome.NEEDS_PLANNING,
                    references=tuple((*refs, approval_ref)),
                    approved_scope_ref=approved_scope_ref,
                    planner_request=planner_request,
                )
            )
        refs.append(approval_ref)
        applied = _apply_runner_setup(
            request,
            classified,
            refs,
            authority_request=request,
            runner_approval=runner_approval,
            setup_evidence=setup_evidence,
            setup_authorization=setup_authorization,
            spec_ref=spec_ref,
            coverage=coverage,
            plan=plan,
            plan_ref=plan_ref,
        )
        if isinstance(applied, CookPreparationResult):
            return applied
        handoff_ref = _publish_handoff(
            request,
            source=classified,
            spec_ref=spec_ref,
            approval_ref=approval_ref,
            coverage=coverage,
            planner_result_ref=planner_ref,
            plan_ref=plan_ref,
            taste_verdict_ref=(
                None if readiness is None else readiness.taste_verdict_ref
            ),
            taste_ledger_ref=(
                None if readiness is None else readiness.taste_ledger_ref
            ),
            runner_approval_ref=applied.runner_approval_ref,
            setup_evidence_refs=applied.setup_evidence_refs,
        )
        return validate_preparation_result(
            _ready_result(request, classified, refs, handoff_ref, coverage)
        )
    except _PreparationFailure as failure:
        return validate_preparation_result(
            _invalid_result(request, classified, refs, failure)
        )
    except CookEvidenceError as failure:
        return validate_preparation_result(
            _invalid_result(
                request,
                classified,
                refs,
                _PreparationFailure("invalid-evidence", str(failure)),
            )
        )
    except (ContractValidationError, OSError, TypeError, ValueError) as failure:
        return validate_preparation_result(
            _invalid_result(request, classified, refs, failure)
        )


def _validate_hold_clearance(clearance: CookHoldClearance, root: Path) -> None:
    if clearance.response_ref.role != "dialogue":
        raise CookEvidenceError("hold clearance must reference local dialogue")
    raw = _resolve_ref(clearance.response_ref, root)
    try:
        parsed = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CookEvidenceError("hold clearance dialogue is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise CookEvidenceError("hold clearance dialogue must be a JSON object")
    dialogue = cast("dict[str, object]", parsed)
    if dialogue.get("response") != clearance.response_text:
        raise CookEvidenceError(
            "hold clearance response is absent from or detached from local dialogue"
        )
    if dialogue.get("hold") or dialogue.get("holds"):
        raise CookEvidenceError("hold clearance dialogue preserves an execution hold")
    clear_holds = dialogue.get("clear_holds")
    if not isinstance(clear_holds, list) or clearance.hold_id not in cast(
        "list[object]", clear_holds
    ):
        raise CookEvidenceError(
            f"hold clearance dialogue does not name {clearance.hold_id!r}"
        )
    if not dialogue_authorizes_execution(dialogue):
        raise CookEvidenceError("hold clearance dialogue does not authorize execution")


def resubmit(
    previous: object,
    *,
    source: str | Path | ClassifiedCookInput | None = None,
    repository_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
    mode: MoldCookMode | str | None = None,
    explicit_kind: MoldCookInputKind | str | None = None,
    scope_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None = None,
    plan_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None = None,
    runner_approval: MoldCookApproval
    | ArtifactRef
    | str
    | Path
    | Mapping[str, object]
    | None = None,
    planner_result: PlannerResult | ArtifactRef | str | Path | None = None,
    planner_view: PlannerResultWriterView | None = None,
    planner_dispatch: Callable[[PlannerRequest], object] | None = None,
    setup_authorization: CookSetupAuthorization
    | ArtifactRef
    | Mapping[str, object]
    | str
    | Path
    | None = None,
    setup_evidence: SetupEvidence
    | Mapping[str, object]
    | ArtifactRef
    | str
    | Path
    | None = None,
    spec_binding: ArtifactRef | str | Path | None = None,
    holds: Sequence[CookExecutionHold] = (),
    clearances: Sequence[CookHoldClearance] = (),
) -> CookPreparationResult:
    previous_result = validate_preparation_result(previous)
    request_ref = next(
        (
            item
            for item in previous_result.references
            if item.role == "preparation_request"
        ),
        None,
    )
    if request_ref is None:
        raise CookEvidenceError("previous result has no canonical preparation request")
    request_root = (
        Path(artifact_root).resolve()
        if artifact_root is not None
        else _local_path_for(request_ref.uri).parent
    )
    metadata = _request_metadata(request_ref, request_root)
    expected_source = cast(str, metadata["source"])
    expected_kind = MoldCookInputKind(cast(str, metadata["kind"]))
    expected_path_value = metadata["path"]
    expected_path = (
        None if expected_path_value is None else Path(cast(str, expected_path_value))
    )
    if source is None:
        source_value: str | Path | ClassifiedCookInput = ClassifiedCookInput(
            expected_kind,
            expected_source,
            expected_path,
            bool(metadata["explicit"]),
            (
                None
                if metadata["declared_kind"] is None
                else MoldCookInputKind(cast(str, metadata["declared_kind"]))
            ),
        )
    else:
        source_value = source
        candidate = (
            source
            if isinstance(source, ClassifiedCookInput)
            else classify_input(source, explicit_kind=explicit_kind)
        )
        if candidate.kind is not expected_kind or candidate.source != expected_source:
            raise CookInputError(
                "resubmission changed the preparation request identity"
            )
        if expected_path is not None and candidate.path is not None:
            if candidate.path.resolve() != expected_path:
                raise CookInputError("resubmission changed the preparation source path")
    expected_root = Path(cast(str, metadata["repository_root"])).resolve()
    repository = (
        expected_root if repository_root is None else Path(repository_root).resolve()
    )
    if repository != expected_root:
        raise CookInputError("resubmission changed repository_root")
    expected_artifacts = Path(cast(str, metadata["artifact_root"])).resolve()
    artifacts = (
        expected_artifacts if artifact_root is None else Path(artifact_root).resolve()
    )
    if artifacts != expected_artifacts:
        raise CookInputError("resubmission changed artifact_root")
    expected_mode = MoldCookMode(cast(str, metadata["mode"]))
    selected_mode = expected_mode if mode is None else MoldCookMode(mode)
    if selected_mode is not expected_mode:
        raise CookInputError("resubmission changed mode")
    retained_holds: list[CookExecutionHold] = []
    clearance_ids = [item.hold_id for item in clearances]
    if len(clearance_ids) != len(set(clearance_ids)):
        raise CookEvidenceError("hold clearances contain duplicate hold IDs")
    previous_hold_ids = {item.hold_id for item in previous_result.holds}
    unknown_clearances = set(clearance_ids) - previous_hold_ids
    if unknown_clearances:
        raise CookEvidenceError(
            f"hold clearance names unknown holds: {sorted(unknown_clearances)}"
        )
    clear_by_id = {item.hold_id: item for item in clearances}
    for hold in previous_result.holds:
        clearance = clear_by_id.get(hold.hold_id)
        if clearance is None:
            retained_holds.append(hold)
            continue
        _validate_hold_clearance(clearance, artifacts)
    retained_ids = {item.hold_id for item in retained_holds}
    retained_holds.extend(hold for hold in holds if hold.hold_id not in retained_ids)
    if spec_binding is None:
        spec_binding = next(
            (item for item in previous_result.references if item.role == "spec"),
            None,
        )
    return prepare(
        source_value,
        request_id=previous_result.request_id,
        repository_root=repository,
        artifact_root=artifacts,
        mode=selected_mode,
        explicit_kind=expected_kind,
        scope_approval=scope_approval,
        plan_approval=plan_approval,
        runner_approval=runner_approval,
        planner_result=planner_result,
        planner_view=planner_view,
        planner_dispatch=planner_dispatch,
        setup_authorization=setup_authorization,
        setup_evidence=setup_evidence,
        spec_binding=spec_binding,
        holds=tuple(retained_holds),
        previous=previous_result,
    )


def execute_accepted_handoff(
    pointer_source: CookPreparationResult | ArtifactRef | str | Path,
    *,
    artifact_root: str | Path | None = None,
    repository_root: str | Path = ".",
    dispatch_writer: workflow.WriterDispatch,
    dispatch_review: workflow.ReviewDispatch,
    dispatch_diagnosis: workflow.DiagnosisDispatch,
    evidence: Mapping[str, EvidenceRef] | None = None,
) -> CookExecutionOutcome:
    """Accept one canonical pointer and execute its exact approved coverage."""

    # The configured root is the containment root: a caller-supplied pointer
    # URI names a path inside it and never defines it.
    if artifact_root is None:
        raise ContractValidationError("execution requires a caller-supplied artifact_root")
    supplied_root = Path(artifact_root).resolve()
    if isinstance(pointer_source, CookPreparationResult):
        prepared = validate_preparation_result(pointer_source)
        if prepared.outcome is not CookPreparationOutcome.READY:
            raise ContractValidationError(
                "execution requires a READY preparation result"
            )
        if prepared.handoff_ref is None:
            raise ContractValidationError("READY preparation has no handoff pointer")
        handoff_ref = prepared.handoff_ref
        pointer_path = _local_path_for(handoff_ref.uri, supplied_root)
    elif isinstance(pointer_source, ArtifactRef):
        handoff_ref = pointer_source
        pointer_path = _local_path_for(pointer_source.uri, supplied_root)
    else:
        pointer_path = Path(pointer_source)
        handoff_ref = None
    resolved_artifact_root = supplied_root
    if handoff_ref is not None:
        pointer_bytes = _read_path(pointer_path)
        if handoff_ref.role not in {"handoff", "handoff_pointer"}:
            raise ContractValidationError("handoff reference has the wrong role")
        if len(pointer_bytes) != handoff_ref.size_bytes:
            raise ContractValidationError("handoff reference size does not match pointer")
        if digest_bytes(pointer_bytes) != handoff_ref.digest:
            raise ContractValidationError("handoff reference digest does not match pointer")
        if handoff_ref.media_type != "application/json":
            raise ContractValidationError("handoff reference media type is not JSON")
        if handoff_ref.schema_uri != f"{SCHEMA_ROOT}/handoff-pointer":
            raise ContractValidationError("handoff reference schema is not canonical")
    if not pointer_path.resolve().is_relative_to(resolved_artifact_root):
        raise ContractValidationError(
            "canonical pointer is outside artifact root "
            + repr(str(resolved_artifact_root))
        )
    accepted = accept_mold_cook_handoff(
        pointer_path,
        artifact_root=resolved_artifact_root,
    )
    handoff = cast(MoldCookHandoff, accepted.canonical.value)
    request = CookPreparationRequest(
        request_id=handoff.request_id,
        source=ClassifiedCookInput(
            MoldCookInputKind.CANONICAL_POINTER,
            str(pointer_path),
            pointer_path,
        ),
        repository_root=Path(repository_root).resolve(),
        artifact_root=resolved_artifact_root,
        mode=handoff.mode,
    )
    _validate_handoff_authority(handoff, request=request)
    if handoff.mode is not MoldCookMode.FULL:
        raise ContractValidationError(
            "workflow execution requires a Full handoff with an approved plan"
        )
    if handoff.planner_result_ref is None or handoff.plan_ref is None:
        raise ContractValidationError(
            "Full handoff is missing its canonical planner result or plan"
        )
    planner_value = _load_contract(
        handoff.planner_result_ref,
        PlannerResult,
        resolved_artifact_root,
    )
    plan_value = _load_contract(
        handoff.plan_ref,
        CurdPlan,
        resolved_artifact_root,
    )
    planner = cast(PlannerResult, planner_value)
    plan = cast(CurdPlan, plan_value)
    if planner.plan is None or canonical_bytes(planner.plan) != canonical_bytes(plan):
        raise ContractValidationError(
            "accepted handoff planner result and plan are detached"
        )
    selected = tuple(handoff.coverage.curd_ids)
    execution_results = workflow.cook(
        plan,
        repository_root=repository_root,
        artifact_directory=resolved_artifact_root,
        dispatch_writer=dispatch_writer,
        dispatch_review=dispatch_review,
        dispatch_diagnosis=dispatch_diagnosis,
        curd_ids=selected,
        evidence=evidence,
    )
    completed = tuple(
        result.source_curd_ref.curd_id
        for result in execution_results[1]
        if getattr(result.disposition, "value", result.disposition) == "passed"
    )
    whole_task_complete = not handoff.coverage.unresolved_work and set(
        completed
    ) == set(selected)
    resumable_ref = handoff_ref or _pointer_ref(
        pointer_path,
        request_id=handoff.request_id,
    )
    outcome_payload = {
        "request_id": handoff.request_id,
        "handoff_ref": resumable_ref,
        "planner_result_ref": handoff.planner_result_ref,
        "plan_ref": handoff.plan_ref,
        "coverage": handoff.coverage,
        "completed_curds": completed,
        "remainder": handoff.coverage.unresolved_work,
        "whole_task_complete": whole_task_complete,
        "resumable_ref": resumable_ref,
    }
    outcome_ref = _persist_value(
        resolved_artifact_root,
        outcome_payload,
        artifact_id=f"{handoff.request_id}/execution-outcome",
        role="execution_outcome",
        schema_uri=None,
    )
    return CookExecutionOutcome(
        request_id=handoff.request_id,
        handoff_ref=resumable_ref,
        planner_result_ref=handoff.planner_result_ref,
        plan_ref=handoff.plan_ref,
        coverage=handoff.coverage,
        completed_curds=completed,
        remainder=handoff.coverage.unresolved_work,
        whole_task_complete=whole_task_complete,
        resumable_ref=resumable_ref,
        execution_results=execution_results,
        outcome_ref=outcome_ref,
    )


__all__ = [
    "ClassifiedCookInput",
    "CookEvidenceError",
    "CookExecutionOutcome",
    "CookHoldClearance",
    "CookInputError",
    "CookPreparationRequest",
    "SetupEvidence",
    "classify_input",
    "execute_accepted_handoff",
    "load_preparation_result",
    "prepare",
    "resubmit",
    "validate_preparation_result",
]
