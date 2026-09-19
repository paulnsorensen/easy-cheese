"""Mold-owned canonical finalization and planner normalization.

The planner writer speaks in keys and envelopes.  This module is the host seam:
it materializes the writer view once, joins the resulting authority with a
strictly validated spec, explicit taste and approval evidence, and the spec's
landing declaration, then publishes only a canonical ``MoldCookHandoff``.
Incomplete work is represented as a blocked ``CookPreparationResult`` and is
never converted into a runnable pointer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeVar, cast
from easy_cheese_schemas.contracts import (
    MAX_ARTIFACT_BYTES,
    AgentWriterView,
    ArtifactRef,
    CurdPlan,
    EvidenceKind,
    EvidenceRef,
    IdentityAction,
    IdentityLineage,
    Landing,
    LandingShape,
    PlannerRequest,
    PlannerResult,
    PlannerResultWriterView,
    SourceLocation,
)
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    CookExecutionHold,
    CookHoldKind,
    CookPreparationOutcome,
    CookPreparationResult,
    CookRequirementKind,
    CookUnmetRequirement,
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookHandoff,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.planner import materialize_planner_result
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    canonical_bytes,
    load_agent_writer_view,
    supported_version_for,
    validate_contract,
)
from easy_cheese.shared.mold_cook_handoff import (
    canonical_mold_cook_proposal,
    evaluate_mold_cook_spec,
    materialize_artifact_ref,
    validate_mold_cook_approval,
)
from easy_cheese.shared.publication import (
    BoundedReadOverflow,
    PublicationError,
    atomic_write,
    publish_mold_cook_handoff,
    read_bounded,
)
from easy_cheese.shared.taste_test import (
    MAX_SPEC_BYTES,
    ForkTasteVerdict,
    TasteTestError,
    parse_spec_frontmatter as _canonical_frontmatter,
    read_spec_text,
    validate_taste_result,
)
from easy_cheese.skills.mold.validate_spec import validate as validate_spec

__all__ = [
    "FinalizationError",
    "FinalizationOutcome",
    "finalize_mold",
    "main",
    "normalize_planner_result",
    "normalize_planner_main",
]


class FinalizationError(ValueError):
    """The finalization request itself is malformed, not merely incomplete."""


_ALLOWED_LIFECYCLES = frozenset({"draft", "approved", "approved-with-prerequisites"})
_ALLOWED_OVERRIDE_KEYS = frozenset({"curdle_anyway"})
_REQUEST_DIRECTIVE_KEYS = frozenset(
    {"request_directive", "execution_directive", "whole_request_directive"}
)
_DIRECTIVE_FIELDS = frozenset(
    {"action", "decision", "directive", "disposition", "intent"}
)
_REQUEST_DIRECTIVE_HEADINGS = re.compile(
    r"(?im)^##\s+(?:request|execution|whole-request)\s+directive\s*$"
)
_ContractT = TypeVar("_ContractT")
_EnumT = TypeVar("_EnumT", bound=Enum)


@dataclass(frozen=True)
class FinalizationOutcome:
    """Stable Mold command output for ready and saved-not-ready work."""

    payload: Mapping[str, object]

    @property
    def status(self) -> str:
        value = self.payload.get("status")
        if not isinstance(value, str):
            raise FinalizationError("finalization payload has no status")
        return value

    @property
    def ready(self) -> bool:
        return self.payload.get("ready") is True

    @property
    def result_path(self) -> Path | None:
        value = self.payload.get("result_path")
        return Path(value) if isinstance(value, str) else None

    def to_dict(self) -> dict[str, object]:
        return dict(self.payload)


@dataclass(frozen=True)
class _Frontmatter:
    status: str
    gates_overridden: tuple[str, ...]
    request_directive: str | None


@dataclass(frozen=True)
class _SpecSnapshot:
    path: Path
    content: bytes
    text: str
    frontmatter: _Frontmatter


@dataclass(frozen=True)
class _Persisted:
    reference: ArtifactRef
    value: object


def _read_json(path: Path) -> object:
    try:
        raw = read_bounded(path, MAX_ARTIFACT_BYTES)
        decoded = cast(object, json.loads(raw))
        return decoded
    except (
        BoundedReadOverflow,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise FinalizationError(f"could not read JSON artifact {path}: {exc}") from exc


def _read_spec_snapshot(path: Path) -> _SpecSnapshot:
    try:
        text = read_spec_text(path)
    except (OSError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise FinalizationError(f"could not read spec snapshot {path}: {exc}") from exc
    content = text.encode("utf-8")
    if len(content) > MAX_SPEC_BYTES:
        raise FinalizationError(f"spec snapshot exceeds {MAX_SPEC_BYTES} bytes")
    return _SpecSnapshot(path, content, text, _frontmatter(text))


def _directive_value(value: object) -> str | None:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        for key in _DIRECTIVE_FIELDS:
            candidate = mapping.get(key)
            if isinstance(candidate, str):
                value = candidate
                break
        else:
            return None
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold().replace("_", "-").replace(" ", "-")
    return normalized if normalized in {"do-not-implement", "do-not-proceed"} else None


def _section_directive(text: str) -> str | None:
    match = _REQUEST_DIRECTIVE_HEADINGS.search(text)
    if match is None:
        return None
    next_heading = re.search(r"(?im)^##\s+", text[match.end() :])
    section = (
        text[match.end() : match.end() + next_heading.start()]
        if next_heading
        else text[match.end() :]
    )
    for line in section.splitlines():
        candidate = line.strip().lstrip("-*").strip()
        if ":" not in candidate:
            continue
        key, value = candidate.split(":", 1)
        if key.strip().casefold() in _DIRECTIVE_FIELDS:
            directive = _directive_value(value)
            if directive is not None:
                return directive
    return None


def _load_contract(value: object, contract: type[_ContractT]) -> _ContractT:
    if isinstance(value, contract):
        return value
    raw: object
    if isinstance(value, Path):
        raw = _read_json(value)
    elif isinstance(value, (str, bytes)):
        try:
            raw = cast(object, json.loads(value))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FinalizationError(
                f"invalid JSON for {contract.__name__}: {exc}"
            ) from exc
    else:
        raw = value
    version = supported_version_for(contract)
    if version is None:
        raise FinalizationError(
            f"{contract.__name__} has no supported contract version"
        )
    try:
        artifact = validate_contract(raw, contract, version)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise FinalizationError(f"invalid {contract.__name__}: {exc}") from exc
    return cast(_ContractT, artifact.value)


def _artifact_ref(value: object, label: str) -> ArtifactRef:
    if isinstance(value, ArtifactRef):
        return value
    if not isinstance(value, Mapping):
        raise FinalizationError(f"{label} must be an ArtifactRef object")
    mapping = cast(Mapping[str, object], value)
    try:
        return cast(Callable[..., ArtifactRef], ArtifactRef)(
            artifact_id=cast(str, mapping["artifact_id"]),
            role=cast(str, mapping["role"]),
            uri=cast(str, mapping["uri"]),
            digest=cast(str, mapping["digest"]),
            size_bytes=cast(int, mapping["size_bytes"]),
            media_type=cast(str, mapping["media_type"]),
            schema_uri=cast(str | None, mapping.get("schema_uri")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FinalizationError(f"invalid {label}: {exc}") from exc


def _source_location(value: object, label: str) -> SourceLocation | None:
    if value is None:
        return None
    if isinstance(value, SourceLocation):
        return value
    if not isinstance(value, Mapping):
        raise FinalizationError(f"{label} must be a SourceLocation object")
    mapping = cast(Mapping[str, object], value)
    try:
        return cast(Callable[..., SourceLocation], SourceLocation)(
            artifact_id=cast(str, mapping["artifact_id"]),
            path=cast(str, mapping["path"]),
            start_line=cast(int, mapping["start_line"]),
            end_line=cast(int, mapping["end_line"]),
            start_column=cast(int | None, mapping.get("start_column")),
            end_column=cast(int | None, mapping.get("end_column")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FinalizationError(f"invalid {label}: {exc}") from exc


def _evidence_ref(value: object, label: str) -> EvidenceRef:
    if isinstance(value, EvidenceRef):
        return value
    if not isinstance(value, Mapping):
        raise FinalizationError(f"{label} must be an EvidenceRef object")
    mapping = cast(Mapping[str, object], value)
    try:
        return cast(Callable[..., EvidenceRef], EvidenceRef)(
            evidence_id=cast(str, mapping["evidence_id"]),
            kind=EvidenceKind(cast(str, mapping["kind"])),
            artifact=_artifact_ref(mapping["artifact"], f"{label}.artifact"),
            location=_source_location(mapping.get("location"), f"{label}.location"),
            summary=cast(str | None, mapping.get("summary")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FinalizationError(f"invalid {label}: {exc}") from exc


def _lineage(value: object, label: str) -> IdentityLineage:
    if isinstance(value, IdentityLineage):
        return value
    if not isinstance(value, Mapping):
        raise FinalizationError(f"{label} must be an IdentityLineage object")
    mapping = cast(Mapping[str, object], value)
    try:
        return cast(Callable[..., IdentityLineage], IdentityLineage)(
            identity_action=IdentityAction(cast(str, mapping["identity_action"])),
            source_curd_ids=cast(Sequence[str], mapping.get("source_curd_ids", ())),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FinalizationError(f"invalid {label}: {exc}") from exc


def _source_plan(value: object | None) -> CurdPlan | None:
    if value is None or isinstance(value, CurdPlan):
        return value
    return _load_contract(value, CurdPlan)


def normalize_planner_result(
    request: PlannerRequest | Mapping[str, object] | Path,
    writer: PlannerResultWriterView | AgentWriterView | Mapping[str, object] | Path,
    *,
    plan_id: str | None,
    curd_ids: Mapping[str, str],
    artifacts: Mapping[str, ArtifactRef] | Mapping[str, object] | None = None,
    evidence: Mapping[str, EvidenceRef] | Mapping[str, object] | None = None,
    lineages: Mapping[str, IdentityLineage] | Mapping[str, object] | None = None,
    source_plan: CurdPlan | Mapping[str, object] | Path | None = None,
) -> PlannerResult:
    """Materialize one supported planner envelope through the host planner.

    No writer-view normalizer is used here.  The writer view is structured once,
    and ``materialize_planner_result`` remains the only authority that creates
    canonical planner and plan identities.
    """
    typed_request = (
        request
        if isinstance(request, PlannerRequest)
        else _load_contract(request, PlannerRequest)
    )
    typed_writer: PlannerResultWriterView
    if isinstance(writer, PlannerResultWriterView):
        typed_writer = writer
    else:
        try:
            envelope = (
                writer
                if isinstance(writer, AgentWriterView)
                else load_agent_writer_view(
                    _read_json(writer) if isinstance(writer, Path) else writer
                )
            )
        except ContractValidationError as exc:
            raise FinalizationError(f"invalid planner writer envelope: {exc}") from exc
        if envelope.kind.value != "planner_result":
            raise FinalizationError(
                f"planner normalization requires planner_result writer envelope, got {envelope.kind.value}"
            )
        if not isinstance(envelope.payload, PlannerResultWriterView):
            raise FinalizationError(
                "planner writer envelope payload has the wrong type"
            )
        typed_writer = envelope.payload

    typed_artifacts = (
        {}
        if artifacts is None
        else {
            key: _artifact_ref(item, f"artifacts.{key}")
            for key, item in artifacts.items()
        }
    )
    typed_evidence = (
        {}
        if evidence is None
        else {
            key: _evidence_ref(item, f"evidence.{key}")
            for key, item in evidence.items()
        }
    )
    typed_lineages = (
        {}
        if lineages is None
        else {key: _lineage(item, f"lineages.{key}") for key, item in lineages.items()}
    )
    try:
        return materialize_planner_result(
            typed_request,
            typed_writer,
            plan_id=plan_id,
            curd_ids=curd_ids,
            artifacts=typed_artifacts,
            evidence=typed_evidence,
            lineages=typed_lineages,
            source_plan=_source_plan(source_plan),
        )
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise FinalizationError(f"planner materialization failed: {exc}") from exc


def _contained_path(root: Path, *parts: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root_resolved.joinpath(*parts)).resolve()
    try:
        _ = candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise FinalizationError(
            f"artifact destination escapes artifact root: {candidate}"
        ) from exc
    return candidate


def _safe_segment(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        return value
    return "id-" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_bytes(path: Path, payload: bytes) -> None:
    """Bound the payload, then hand the durable write to the shared helper."""

    if len(payload) > MAX_ARTIFACT_BYTES:
        raise FinalizationError(
            f"artifact payload exceeds MAX_ARTIFACT_BYTES ({MAX_ARTIFACT_BYTES} bytes)"
        )
    atomic_write(path, payload)


def _persist(
    root: Path,
    *,
    value: object,
    role: str,
    media_type: str,
    schema_uri: str | None = None,
    suffix: str = ".json",
) -> _Persisted:
    payload = value if isinstance(value, bytes) else canonical_bytes(value)
    digest = hashlib.sha256(payload).hexdigest()
    directory = _contained_path(root, "mold-artifacts")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = _contained_path(root, "mold-artifacts", f"{digest}{suffix}")
    if path.is_symlink():
        raise FinalizationError(f"artifact destination is a symlink: {path}")
    if path.exists():
        try:
            existing = read_bounded(path, MAX_ARTIFACT_BYTES)
        except (BoundedReadOverflow, OSError) as exc:
            raise FinalizationError(
                f"could not read retained artifact {path}: {exc}"
            ) from exc
        if existing != payload:
            raise FinalizationError(
                f"content-addressed artifact {path} contains different bytes"
            )
    else:
        _write_bytes(path, payload)
    reference = materialize_artifact_ref(
        payload,
        artifact_id=f"{_safe_segment(role)}-{digest}",
        role=role,
        uri=path.as_uri(),
        media_type=media_type,
        schema_uri=schema_uri,
    )
    return _Persisted(reference, value)


def _gate_item(raw: str) -> str:
    item = raw.strip().strip("'\"").strip()
    if not item:
        raise FinalizationError("gates_overridden must be a list of strings")
    return item


def _gates_overridden(text: str) -> tuple[str, ...]:
    """Read ``gates_overridden`` as a YAML block list, flow list, or scalar.

    The shared frontmatter reader keeps only scalars, so a declared override
    list reaches this module as an empty mapping or as raw text.  A malformed
    declaration is a caller error, never a silently dropped safety hold.
    """
    lines = text.splitlines()
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise FinalizationError("spec frontmatter is not terminated") from None
    for index in range(1, end):
        match = re.match(r"^gates_overridden:\s*(.*)$", lines[index])
        if match is None:
            continue
        inline = match.group(1).strip()
        if inline in {"null", "~"}:
            return ()
        if not inline:
            key_indent = len(lines[index]) - len(lines[index].lstrip())
            items: list[str] = []
            for entry in lines[index + 1 : end]:
                stripped = entry.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                # A block sequence may sit at the key's own indentation, so the
                # item pattern must not require a deeper indent.
                item = re.match(r"^\s*-\s*(.*)$", entry)
                if item is None:
                    if len(entry) - len(entry.lstrip()) > key_indent:
                        # A nested value that is not a sequence item is a
                        # malformed declaration, never an absent override.
                        raise FinalizationError(
                            "gates_overridden must be a list of strings"
                        )
                    break
                items.append(_gate_item(item.group(1)))
            return tuple(items)
        if inline.startswith("["):
            if not inline.endswith("]"):
                raise FinalizationError("gates_overridden must be a list of strings")
            body = inline[1:-1].strip()
            if not body:
                return ()
            return tuple(_gate_item(part) for part in body.split(","))
        return (_gate_item(inline),)
    return ()


def _frontmatter(text: str) -> _Frontmatter:
    if not text.startswith("---"):
        raise FinalizationError("spec has no frontmatter")
    values = _canonical_frontmatter(text)
    status_value = values.get("status")
    if not isinstance(status_value, str) or status_value not in _ALLOWED_LIFECYCLES:
        raise FinalizationError(
            f"unsupported spec lifecycle {status_value!r}; expected one of {sorted(_ALLOWED_LIFECYCLES)}"
        )
    overrides = _gates_overridden(text)
    directive = next(
        (
            parsed
            for key, value in values.items()
            if key in _REQUEST_DIRECTIVE_KEYS
            for parsed in (_directive_value(value),)
            if parsed is not None
        ),
        None,
    ) or _section_directive(text)
    return _Frontmatter(
        status_value,
        overrides,
        directive,
    )


def _requirement(
    requirement_id: str,
    kind: CookRequirementKind,
    description: str,
) -> CookUnmetRequirement:
    return cast(Callable[..., CookUnmetRequirement], CookUnmetRequirement)(
        requirement_id=requirement_id,
        kind=kind,
        description=description,
    )


def _hold(hold_id: str, kind: CookHoldKind, reason: str) -> CookExecutionHold:
    return cast(Callable[..., CookExecutionHold], CookExecutionHold)(
        hold_id=hold_id,
        kind=kind,
        reason=reason,
    )


def _append_requirement(
    requirements: list[CookUnmetRequirement], item: CookUnmetRequirement
) -> None:
    if item.requirement_id not in {
        existing.requirement_id for existing in requirements
    }:
        requirements.append(item)


def _append_hold(holds: list[CookExecutionHold], item: CookExecutionHold) -> None:
    if item.hold_id not in {existing.hold_id for existing in holds}:
        holds.append(item)


def _validate_spec_snapshot(snapshot: _SpecSnapshot) -> tuple[list[str], str | None]:
    with tempfile.TemporaryDirectory(prefix=".mold-spec-") as directory:
        candidate = Path(directory) / snapshot.path.name
        _write_bytes(candidate, snapshot.content)
        return validate_spec(candidate, strict=True)


def _check_taste(
    spec_text: str,
    taste_result: object | None,
    decision_ledger: object | None,
) -> tuple[ForkTasteVerdict | None, str]:
    if taste_result is None:
        return None, "taste verdict is required and was not supplied"
    try:
        verdict = validate_taste_result(
            taste_result,
            draft=spec_text,
            decision_ledger=decision_ledger,
        )
    except (TasteTestError, OSError, TypeError, ValueError) as exc:
        return None, f"taste verdict is invalid: {exc}"
    if not verdict.passed:
        blockers = ", ".join(verdict.blockers) or "verdict was not pass"
        return verdict, f"taste verdict did not pass: {blockers}"
    return verdict, ""


def _canonical_output(value: object) -> dict[str, object]:
    raw: object = cast(object, json.loads(canonical_bytes(value)))
    if not isinstance(raw, dict):
        raise FinalizationError("canonical output must be a JSON object")
    return cast(dict[str, object], raw)


def _save_result(root: Path, operation_id: str, output: Mapping[str, object]) -> Path:
    filename = f"{_safe_segment(operation_id)}.json"
    path = _contained_path(root, "results", filename)
    _write_bytes(path, (json.dumps(output, sort_keys=True, indent=2) + "\n").encode())
    return path


def _blocked_outcome(
    artifact_root: Path,
    operation_id: str,
    *,
    request_id: str,
    input_kind: MoldCookInputKind,
    references: Sequence[ArtifactRef],
    holds: Sequence[CookExecutionHold],
    requirements: Sequence[CookUnmetRequirement],
    spec_ref: ArtifactRef,
) -> FinalizationOutcome:
    """Save incomplete work as a validated, blocked preparation result."""
    version = supported_version_for(CookPreparationResult)
    if version is None:
        raise FinalizationError(
            "CookPreparationResult has no supported contract version"
        )
    preparation = cast(Callable[..., CookPreparationResult], CookPreparationResult)(
        contract_version=version,
        request_id=request_id,
        input_kind=input_kind,
        outcome=CookPreparationOutcome.BLOCKED,
        references=tuple(references),
        holds=tuple(holds),
        requirements=tuple(requirements),
    )
    preparation_artifact = validate_contract(
        canonical_bytes(preparation), CookPreparationResult, version
    )
    output: dict[str, object] = {
        "status": "saved-not-ready",
        "ready": False,
        "saved": True,
        "spec_ref": _canonical_output(spec_ref),
        "preparation_result": _canonical_output(preparation_artifact.value),
        "requirements": [_canonical_output(item) for item in requirements],
        "holds": [_canonical_output(item) for item in holds],
    }
    result_path = _save_result(artifact_root, operation_id, output)
    output["result_path"] = str(result_path)
    return FinalizationOutcome(output)


def finalize_mold(
    spec_path: Path,
    *,
    artifact_root: Path,
    operation_id: str,
    request_id: str,
    input_kind: MoldCookInputKind = MoldCookInputKind.DIRECT_SPEC,
    mode: MoldCookMode = MoldCookMode.FULL,
    approval: MoldCookApproval | Mapping[str, object] | Path | None = None,
    planner_result: PlannerResult | Mapping[str, object] | Path | None = None,
    plan: CurdPlan | Mapping[str, object] | Path | None = None,
    taste_result: ForkTasteVerdict | Mapping[str, object] | Path | None = None,
    decision_ledger: object | None = None,
    curdle_anyway: bool = False,
    overrides: Mapping[str, object] | None = None,
) -> FinalizationOutcome:
    """Join all Mold authority checks and publish only a ready handoff.

    This function deliberately returns a blocked saved result for incomplete
    but well-formed work.  Malformed lifecycle or override controls are caller
    errors and raise ``FinalizationError`` instead of being silently treated as
    an approval.
    """
    if overrides is not None:
        unknown = set(overrides) - _ALLOWED_OVERRIDE_KEYS
        if unknown:
            raise FinalizationError(
                "unknown finalization override(s): " + ", ".join(sorted(unknown))
            )
        curdle_anyway = bool(overrides.get("curdle_anyway", curdle_anyway))
    artifact_root = artifact_root.resolve()
    snapshot = _read_spec_snapshot(spec_path)
    spec_text = snapshot.text
    frontmatter = snapshot.frontmatter
    spec_persisted = _persist(
        artifact_root,
        value=snapshot.content,
        role="spec",
        media_type="text/markdown",
        suffix=".md",
    )
    references: list[ArtifactRef] = [spec_persisted.reference]
    requirements: list[CookUnmetRequirement] = []
    holds: list[CookExecutionHold] = []

    errors, _notice = _validate_spec_snapshot(snapshot)
    if errors:
        _append_requirement(
            requirements,
            _requirement(
                "spec-validation",
                CookRequirementKind.INTEGRITY,
                "strict Mold spec validation must pass before publication: "
                + "; ".join(errors),
            ),
        )

    if frontmatter.status == "draft":
        _append_hold(
            holds,
            _hold(
                "lifecycle-draft",
                CookHoldKind.PREPARATION,
                "draft specs require explicit approval before execution",
            ),
        )
        _append_requirement(
            requirements,
            _requirement(
                "lifecycle-approval",
                CookRequirementKind.APPROVAL,
                "spec lifecycle must be approved before publication",
            ),
        )
    elif frontmatter.status == "approved-with-prerequisites":
        _append_hold(
            holds,
            _hold(
                "lifecycle-prerequisites",
                CookHoldKind.PREPARATION,
                "approved-with-prerequisites requires explicit bound prerequisite clearance",
            ),
        )
        _append_requirement(
            requirements,
            _requirement(
                "lifecycle-prerequisites",
                CookRequirementKind.EVIDENCE,
                "named lifecycle prerequisites must be cleared by bound evidence before publication",
            ),
        )

    if frontmatter.gates_overridden:
        _append_hold(
            holds,
            _hold(
                "curdle-anyway",
                CookHoldKind.PREPARATION,
                "curdle anyway saved this design with unchecked handshake items: "
                + ", ".join(frontmatter.gates_overridden),
            ),
        )
        _append_requirement(
            requirements,
            _requirement(
                "handshake-coherence",
                CookRequirementKind.EVIDENCE,
                "unchecked handshake items require explicit follow-up before execution",
            ),
        )
    if curdle_anyway:
        _append_hold(
            holds,
            _hold(
                "curdle-anyway",
                CookHoldKind.PREPARATION,
                "curdle anyway is save-only and never waives execution readiness",
            ),
        )
        _append_requirement(
            requirements,
            _requirement(
                "handshake-coherence",
                CookRequirementKind.EVIDENCE,
                "the agent coherence key was overridden; complete the named checks before execution",
            ),
        )
    if frontmatter.request_directive is not None:
        _append_hold(
            holds,
            _hold(
                (
                    "user-do-not-implement"
                    if frontmatter.request_directive == "do-not-implement"
                    else "user-do-not-proceed"
                ),
                CookHoldKind.USER_INTENT,
                f"whole-request directive {frontmatter.request_directive!r} blocks execution",
            ),
        )
        _append_requirement(
            requirements,
            _requirement(
                "user-intent",
                CookRequirementKind.SCOPE,
                "the whole-request directive must be cleared by a new bound user response",
            ),
        )

    typed_approval: MoldCookApproval | None = None
    approval_persisted: _Persisted | None = None
    if approval is None:
        _append_requirement(
            requirements,
            _requirement(
                "approval-evidence",
                CookRequirementKind.APPROVAL,
                "explicit approval evidence is required before publication",
            ),
        )
    else:
        try:
            typed_approval = _load_contract(approval, MoldCookApproval)
            approval_persisted = _persist(
                artifact_root,
                value=typed_approval,
                role="approval",
                media_type="application/json",
                schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
            )
            references.append(approval_persisted.reference)
            _ = validate_mold_cook_approval(typed_approval, artifact_root=artifact_root)
        except (
            FinalizationError,
            ContractValidationError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            _append_requirement(
                requirements,
                _requirement(
                    "approval-evidence",
                    CookRequirementKind.APPROVAL,
                    f"explicit approval evidence is missing, unreadable, or stale: {exc}",
                ),
            )

    if typed_approval is not None:
        if typed_approval.request_id != request_id:
            _append_requirement(
                requirements,
                _requirement(
                    "approval-request",
                    CookRequirementKind.APPROVAL,
                    "approval request identity does not match the finalization request",
                ),
            )
        if typed_approval.spec_digest != spec_persisted.reference.digest:
            _append_requirement(
                requirements,
                _requirement(
                    "approval-spec",
                    CookRequirementKind.INTEGRITY,
                    "approval is bound to a different spec digest",
                ),
            )
        if typed_approval.decision is not MoldCookApprovalDecision.APPROVED:
            _append_requirement(
                requirements,
                _requirement(
                    "approval-decision",
                    CookRequirementKind.APPROVAL,
                    "only an explicit approved response can authorize execution",
                ),
            )

    typed_planner: PlannerResult | None = None
    typed_plan: CurdPlan | None = None
    planner_persisted: _Persisted | None = None
    plan_persisted: _Persisted | None = None
    if mode is MoldCookMode.FULL:
        try:
            if planner_result is not None:
                typed_planner = _load_contract(planner_result, PlannerResult)
                planner_persisted = _persist(
                    artifact_root,
                    value=typed_planner,
                    role="planner_result",
                    media_type="application/json",
                    schema_uri="https://schemas.easy-cheese.dev/planner-result",
                )
                references.append(planner_persisted.reference)
            else:
                _append_requirement(
                    requirements,
                    _requirement(
                        "planner-result",
                        CookRequirementKind.PLAN,
                        "Full-tier work requires a canonical PlannerResult",
                    ),
                )
            if plan is not None:
                typed_plan = _load_contract(plan, CurdPlan)
            elif typed_planner is not None:
                typed_plan = typed_planner.plan
            if typed_plan is None:
                _append_requirement(
                    requirements,
                    _requirement(
                        "curd-plan",
                        CookRequirementKind.PLAN,
                        "Full-tier work requires a materialized canonical CurdPlan",
                    ),
                )
            else:
                plan_persisted = _persist(
                    artifact_root,
                    value=typed_plan,
                    role="curd_plan",
                    media_type="application/json",
                    schema_uri="https://schemas.easy-cheese.dev/curd-plan",
                )
                references.append(plan_persisted.reference)
        except (
            FinalizationError,
            ContractValidationError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            _append_requirement(
                requirements,
                _requirement(
                    "planner-artifacts",
                    CookRequirementKind.PLAN,
                    f"planner artifacts are invalid or stale: {exc}",
                ),
            )
    elif planner_result is not None or plan is not None:
        _append_requirement(
            requirements,
            _requirement(
                "light-authority",
                CookRequirementKind.PLAN,
                "Light-tier work must not carry planner artifacts",
            ),
        )

    taste_verdict, taste_reason = _check_taste(spec_text, taste_result, decision_ledger)
    taste_persisted: _Persisted | None = None
    taste_ledger_persisted: _Persisted | None = None
    if taste_verdict is None or taste_reason:
        _append_requirement(
            requirements,
            _requirement("taste-verdict", CookRequirementKind.EVIDENCE, taste_reason),
        )
    else:
        try:
            taste_persisted = _persist(
                artifact_root,
                value=taste_verdict.to_dict(),
                schema_uri="https://schemas.easy-cheese.dev/taste-verdict",
                role="taste_verdict",
                media_type="application/json",
            )
            references.append(taste_persisted.reference)
        except (FinalizationError, OSError, TypeError, ValueError) as exc:
            _append_requirement(
                requirements,
                _requirement(
                    "taste-verdict",
                    CookRequirementKind.EVIDENCE,
                    f"taste verdict could not be retained: {exc}",
                ),
            )
    if decision_ledger is None:
        _append_requirement(
            requirements,
            _requirement(
                "taste-ledger",
                CookRequirementKind.EVIDENCE,
                "a protected taste decision ledger reference is required",
            ),
        )
    else:
        try:
            ledger_value = (
                _read_json(decision_ledger)
                if isinstance(decision_ledger, Path)
                else decision_ledger
            )
            taste_ledger_persisted = _persist(
                artifact_root,
                value=ledger_value,
                schema_uri="https://schemas.easy-cheese.dev/taste-ledger",
                role="taste_ledger",
                media_type="application/json",
            )
            references.append(taste_ledger_persisted.reference)
        except (FinalizationError, OSError, TypeError, ValueError) as exc:
            _append_requirement(
                requirements,
                _requirement(
                    "taste-ledger",
                    CookRequirementKind.EVIDENCE,
                    f"taste decision ledger could not be retained: {exc}",
                ),
            )

    landing: Landing | None = None
    try:
        readiness = evaluate_mold_cook_spec(
            snapshot.content,
            spec_ref=spec_persisted.reference,
            plan=typed_plan,
            lifecycle=frontmatter.status,
            taste_verdict_ref=(
                taste_persisted.reference
                if taste_persisted is not None and taste_ledger_persisted is not None
                else None
            ),
            taste_ledger_ref=(
                taste_ledger_persisted.reference
                if taste_persisted is not None and taste_ledger_persisted is not None
                else None
            ),
            holds=holds,
        )
        landing = readiness.landing or cast(Callable[..., Landing], Landing)(
            shape=LandingShape.SINGLE
        )
    except (ContractValidationError, TypeError, ValueError) as exc:
        _append_requirement(
            requirements,
            _requirement(
                "landing-declaration", CookRequirementKind.INTEGRITY, str(exc)
            ),
        )

    coverage = typed_approval.coverage if typed_approval is not None else None
    if coverage is None:
        _append_requirement(
            requirements,
            _requirement(
                "scope-approval",
                CookRequirementKind.SCOPE,
                "approved scope coverage is required before finalization",
            ),
        )
    elif mode is MoldCookMode.LIGHT:
        if (
            typed_approval is not None
            and typed_approval.kind is not MoldCookApprovalKind.SCOPE
        ):
            _append_requirement(
                requirements,
                _requirement(
                    "scope-approval-kind",
                    CookRequirementKind.SCOPE,
                    "Light-tier work requires scope approval, not plan or status approval",
                ),
            )
        if len(coverage.curd_ids) != 1:
            _append_requirement(
                requirements,
                _requirement(
                    "light-coverage",
                    CookRequirementKind.SCOPE,
                    "Light-tier handoffs authorize exactly one canonical curd",
                ),
            )
        if coverage.unresolved_work:
            _append_requirement(
                requirements,
                _requirement(
                    "light-remainder",
                    CookRequirementKind.PLAN,
                    "Light-tier handoffs cannot discard unresolved planner work",
                ),
            )
    elif typed_planner is not None and typed_plan is not None:
        expected_kind = (
            MoldCookApprovalKind.PARTIAL_PLAN
            if typed_planner.disposition.value == "partial"
            else MoldCookApprovalKind.PLAN
        )
        if typed_approval is None or typed_approval.kind is not expected_kind:
            _append_requirement(
                requirements,
                _requirement(
                    "plan-approval-kind",
                    CookRequirementKind.APPROVAL,
                    f"Full-tier {typed_planner.disposition.value} work requires {expected_kind.value} approval",
                ),
            )
        if typed_planner.plan is None or canonical_bytes(
            typed_planner.plan
        ) != canonical_bytes(typed_plan):
            _append_requirement(
                requirements,
                _requirement(
                    "plan-binding",
                    CookRequirementKind.INTEGRITY,
                    "PlannerResult and CurdPlan references must name identical canonical bytes",
                ),
            )
        if landing is not None:
            declared_ids = tuple(curd.curd_id for curd in typed_plan.curds)
            if landing.shape is LandingShape.SINGLE:
                expected_landing = set(declared_ids)
            else:
                expected_landing = {
                    curd_id for layer in landing.layers for curd_id in layer
                }
            if expected_landing != set(declared_ids):
                _append_requirement(
                    requirements,
                    _requirement(
                        "landing-coverage",
                        CookRequirementKind.INTEGRITY,
                        "landing coverage must cover exactly the canonical plan curds",
                    ),
                )
            if not set(coverage.curd_ids).issubset(set(declared_ids)):
                _append_requirement(
                    requirements,
                    _requirement(
                        "coverage-ids",
                        CookRequirementKind.INTEGRITY,
                        "approved coverage names unknown canonical curd IDs",
                    ),
                )
    elif mode is MoldCookMode.FULL:
        _append_requirement(
            requirements,
            _requirement(
                "full-coverage",
                CookRequirementKind.PLAN,
                "Full-tier work cannot publish without a valid planner result and plan",
            ),
        )

    if typed_approval is not None and typed_approval.coverage != coverage:
        _append_requirement(
            requirements,
            _requirement(
                "coverage-binding",
                CookRequirementKind.INTEGRITY,
                "approval coverage changed during finalization",
            ),
        )
    if typed_approval is not None and coverage is not None:
        proposal_kind: MoldCookApprovalKind | None = None
        proposal_planner: PlannerResult | None = None
        proposal_plan_digest: str | None = None
        if mode is MoldCookMode.LIGHT:
            proposal_kind = MoldCookApprovalKind.SCOPE
        elif typed_planner is not None and typed_plan is not None:
            proposal_kind = (
                MoldCookApprovalKind.PARTIAL_PLAN
                if typed_planner.disposition.value == "partial"
                else MoldCookApprovalKind.PLAN
            )
            proposal_planner = typed_planner
            proposal_plan_digest = typed_plan.digest
        if proposal_kind is not None:
            try:
                proposal = canonical_mold_cook_proposal(
                    request_id=request_id,
                    kind=proposal_kind,
                    spec_digest=spec_persisted.reference.digest,
                    coverage=coverage,
                    planner_result=proposal_planner,
                    plan_digest=proposal_plan_digest,
                )
                expected_digest = "sha256:" + hashlib.sha256(proposal).hexdigest()
                if typed_approval.proposal_digest != expected_digest:
                    _append_requirement(
                        requirements,
                        _requirement(
                            "approval-proposal",
                            CookRequirementKind.INTEGRITY,
                            "approval proposal is not the canonical envelope for this handoff",
                        ),
                    )
            except (ContractValidationError, TypeError, ValueError) as exc:
                _append_requirement(
                    requirements,
                    _requirement(
                        "approval-proposal",
                        CookRequirementKind.INTEGRITY,
                        f"canonical approval proposal could not be built: {exc}",
                    ),
                )

    if requirements or holds:
        return _blocked_outcome(
            artifact_root,
            operation_id,
            request_id=request_id,
            input_kind=input_kind,
            references=references,
            holds=holds,
            requirements=requirements,
            spec_ref=spec_persisted.reference,
        )

    if typed_approval is None or approval_persisted is None:
        raise FinalizationError("ready finalization requires approval evidence")
    if mode is MoldCookMode.FULL and (
        typed_planner is None
        or typed_plan is None
        or planner_persisted is None
        or plan_persisted is None
    ):
        raise FinalizationError(
            "ready Full-tier finalization requires planner artifacts"
        )

    assert approval_persisted is not None
    assert coverage is not None
    planner_ref: ArtifactRef | None = None
    plan_ref: ArtifactRef | None = None
    if mode is MoldCookMode.FULL:
        assert planner_persisted is not None
        assert plan_persisted is not None
        planner_ref = planner_persisted.reference
        plan_ref = plan_persisted.reference
    handoff_version = supported_version_for(MoldCookHandoff)
    if handoff_version is None:
        raise FinalizationError("MoldCookHandoff has no supported contract version")
    assert taste_persisted is not None
    assert taste_ledger_persisted is not None
    handoff = cast(Callable[..., MoldCookHandoff], MoldCookHandoff)(
        contract_version=handoff_version,
        request_id=request_id,
        input_kind=input_kind,
        mode=mode,
        spec_ref=spec_persisted.reference,
        approval_ref=approval_persisted.reference,
        coverage=coverage,
        planner_result_ref=planner_ref,
        plan_ref=plan_ref,
        taste_verdict_ref=taste_persisted.reference,
        taste_ledger_ref=taste_ledger_persisted.reference,
        runner_approval_ref=None,
        setup_evidence_refs=(),
    )
    try:
        digest = "sha256:" + hashlib.sha256(canonical_bytes(handoff)).hexdigest()
        published = publish_mold_cook_handoff(
            handoff,
            request_digest=digest,
            operation_id=operation_id,
            artifact_root=artifact_root,
        )
    except (ContractValidationError, PublicationError, TypeError, ValueError) as exc:
        _append_requirement(
            requirements,
            _requirement(
                "handoff-integrity",
                CookRequirementKind.INTEGRITY,
                f"canonical handoff failed shared validation or publication: {exc}",
            ),
        )
        return _blocked_outcome(
            artifact_root,
            operation_id,
            request_id=request_id,
            input_kind=input_kind,
            references=references,
            holds=holds,
            requirements=requirements,
            spec_ref=spec_persisted.reference,
        )

    pointer = _canonical_output(published.pointer)
    output: dict[str, object] = {
        "status": "ready",
        "ready": True,
        "saved": True,
        "next": "cook",
        "command": [
            "/cook",
            "--auto",
            str(artifact_root / "pointers" / f"{_safe_segment(operation_id)}.json"),
        ],
        "pointer": pointer,
        "handoff": _canonical_output(published.canonical.value),
    }
    result_path = _save_result(artifact_root, operation_id, output)
    output["result_path"] = str(result_path)
    return FinalizationOutcome(output)


def _write_json_output(value: object, output: Path | None) -> None:
    text = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if output is None:
        _ = sys.stdout.write(text)
    else:
        _write_bytes(output, text.encode())
        _ = sys.stdout.write(text)


def normalize_planner_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="normalize-planner",
        description="Materialize a planner writer envelope into a canonical PlannerResult.",
    )
    _ = parser.add_argument("writer", type=Path)
    _ = parser.add_argument("--request", required=True, type=Path)
    _ = parser.add_argument("--invocation", required=True, type=Path)
    _ = parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        writer_raw = _read_json(cast(Path, args.writer))
        request_raw = _read_json(cast(Path, args.request))
        invocation = _read_json(cast(Path, args.invocation))
        if not isinstance(invocation, Mapping):
            raise FinalizationError("invocation must be a JSON object")
        invocation_mapping = cast(Mapping[str, object], invocation)
        host_raw = invocation_mapping.get("planner", invocation_mapping)
        if not isinstance(host_raw, Mapping):
            raise FinalizationError("invocation.planner must be a JSON object")
        host = cast(Mapping[str, object], host_raw)
        plan_id_raw = host.get("plan_id")
        curd_ids_raw = host.get("curd_ids")
        if not isinstance(plan_id_raw, str) or not plan_id_raw.strip():
            raise FinalizationError("invocation.plan_id is required")
        if not isinstance(curd_ids_raw, Mapping):
            raise FinalizationError("invocation.curd_ids is required")
        if not isinstance(request_raw, Mapping) or not isinstance(writer_raw, Mapping):
            raise FinalizationError("request and writer must be JSON objects")
        result = normalize_planner_result(
            cast(Mapping[str, object], request_raw),
            cast(Mapping[str, object], writer_raw),
            plan_id=plan_id_raw,
            curd_ids={
                cast(str, key): cast(str, value)
                for key, value in cast(Mapping[object, object], curd_ids_raw).items()
            },
            artifacts=cast(Mapping[str, object] | None, host.get("artifacts")),
            evidence=cast(Mapping[str, object] | None, host.get("evidence")),
            lineages=cast(Mapping[str, object] | None, host.get("lineages")),
            source_plan=cast(
                CurdPlan | Mapping[str, object] | Path | None,
                host.get("source_plan"),
            ),
        )
        _write_json_output(_canonical_output(result), cast(Path | None, args.output))
        return 0
    except (
        FinalizationError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _parse_enum(value: str, enum: type[_EnumT], label: str) -> _EnumT:
    try:
        return enum(value)
    except ValueError as exc:
        raise FinalizationError(f"invalid {label}: {value!r}") from exc


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="finalize",
        description="Finalize a Mold spec and publish only a consumer-valid handoff.",
    )
    _ = parser.add_argument("spec", type=Path)
    _ = parser.add_argument("--approval", type=Path)
    _ = parser.add_argument("--artifact-root", required=True, type=Path)
    _ = parser.add_argument("--operation-id", required=True)
    _ = parser.add_argument("--request-id", required=True)
    _ = parser.add_argument("--input-kind", default=MoldCookInputKind.DIRECT_SPEC.value)
    _ = parser.add_argument("--mode", default=MoldCookMode.FULL.value)
    _ = parser.add_argument("--planner-result", type=Path)
    _ = parser.add_argument("--plan", type=Path)
    _ = parser.add_argument("--taste-result", type=Path)
    _ = parser.add_argument("--ledger", type=Path)
    _ = parser.add_argument("--curdle-anyway", action="store_true")
    args = parser.parse_args(argv)
    try:
        taste_path = cast(Path | None, args.taste_result)
        ledger_path = cast(Path | None, args.ledger)
        taste: object | None = None if taste_path is None else _read_json(taste_path)
        ledger: object | None = None if ledger_path is None else _read_json(ledger_path)
        outcome = finalize_mold(
            cast(Path, args.spec),
            artifact_root=cast(Path, args.artifact_root),
            operation_id=cast(str, args.operation_id),
            request_id=cast(str, args.request_id),
            input_kind=_parse_enum(
                cast(str, args.input_kind), MoldCookInputKind, "input kind"
            ),
            mode=_parse_enum(cast(str, args.mode), MoldCookMode, "mode"),
            approval=cast(Path | None, args.approval),
            planner_result=cast(Path | None, args.planner_result),
            plan=cast(Path | None, args.plan),
            taste_result=cast(
                ForkTasteVerdict | Mapping[str, object] | Path | None, taste
            ),
            decision_ledger=ledger,
            curdle_anyway=cast(bool, args.curdle_anyway),
        )
        _write_json_output(outcome.to_dict(), None)
        return 0
    except (
        FinalizationError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
