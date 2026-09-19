"""Mold-owned canonical finalization and planner normalization.

The planner writer speaks in keys and envelopes.  This module is the host seam:
it materializes the writer view once, joins the resulting authority with a
strictly validated spec, explicit taste and approval evidence, and the spec's
landing declaration, then publishes only a canonical ``MoldCookHandoff``.
Incomplete work is represented as a blocked ``CookPreparationResult`` and is
never converted into a runnable pointer.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar, cast

from easy_cheese_schemas.contracts import (
    MAX_ARTIFACT_BYTES,
    # `contracts` owns the JSON projection canonical bytes already build, so
    # Mold borrows it instead of round-tripping bytes back through the decoder.
    _unstructure as unstructure_contract,  # pyright: ignore[reportPrivateUsage]
    AgentWriterView,
    ArtifactRef,
    CurdPlan,
    EvidenceRef,
    IdentityLineage,
    Landing,
    LandingShape,
    PlannerDisposition,
    PlannerRequest,
    PlannerResult,
    PlannerResultWriterView,
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
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.planner import materialize_planner_result

# `schema_runtime` owns typed structuring for every attrs contract but publishes
# no structuring entry point yet. Mold borrows the private one rather than keep
# a second field-by-field structuring path.
from easy_cheese_schemas.schema_runtime import (
    FORK_TASTE_VERDICT_SCHEMA_URI,
    TASTE_LEDGER_SCHEMA_URI,
    ContractValidationError,
    _typed_host as structure_contract_value,  # pyright: ignore[reportPrivateUsage]
    canonical_bytes,
    load_agent_writer_view,
    require_contract_version,
    validate_contract,
)
from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_verified_bytes,
)
from easy_cheese.shared.bounded_read import BoundedReadOverflow, read_bounded_file
from easy_cheese.shared.mold_cook_handoff import (
    canonical_mold_cook_proposal,
    evaluate_mold_cook_spec,
    materialize_artifact_ref,
    publish_mold_cook_handoff,
    resolve_contract_value,
    validate_mold_cook_approval,
)
from easy_cheese.shared.publication import PublicationError, atomic_write
from easy_cheese.shared.taste_test import (
    MAX_SPEC_BYTES,
    ForkTasteVerdict,
    TasteTestError,
    parse_spec_frontmatter,
    read_spec_text,
    validate_taste_result,
)
from easy_cheese.skills.mold.validate_spec import validate as validate_spec

__all__ = [
    "FinalizationError",
    "FinalizationOutcome",
    "finalize_mold",
    "normalize_planner_result",
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
        raw = read_bounded_file(path, limit=MAX_ARTIFACT_BYTES)
        decoded = cast(object, json.loads(raw))
        return decoded
    except (
        BoundedReadOverflow,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise FinalizationError(f"could not read JSON artifact {path}: {exc}") from exc


def _write_bounded(path: Path, payload: bytes) -> None:
    """Publish ``payload`` only while it stays inside the artifact size bound."""
    size = len(payload)
    if size > MAX_ARTIFACT_BYTES:
        overflow = f"{size} bytes exceeds {MAX_ARTIFACT_BYTES} bytes"
        raise FinalizationError(f"could not write artifact {path}: {overflow}")
    atomic_write(path, payload)


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
    """Validate one supplied contract value through the shared resolver.

    ``resolve_contract_value`` owns every accepted shape and the host version
    check.  A path a Mold command names is an operator input, not a retained
    artifact, so it is decoded here through the bounded reader instead of
    being confined to the artifact root the run retains under.
    """

    resolved = _read_json(value) if isinstance(value, Path) else value
    try:
        return resolve_contract_value(resolved, contract, Path())
    except ContractValidationError as exc:
        raise FinalizationError(f"invalid {contract.__name__}: {exc}") from exc


def _structured(value: object, contract: type[_ContractT], label: str) -> _ContractT:
    """Structure one host mapping into a value object through the shared path.

    ``schema_runtime`` already owns typed structuring for every attrs contract,
    including the nested references these value objects carry, and it names the
    failing field as a path under ``label``.
    """

    if isinstance(value, contract):
        return value
    try:
        return structure_contract_value(value, contract, label)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise FinalizationError(f"invalid {label}: {exc}") from exc


def _source_plan(value: object | None) -> CurdPlan | None:
    if value is None or isinstance(value, CurdPlan):
        return value
    return _load_contract(value, CurdPlan)


def _structured_map(
    values: Mapping[str, object] | None, contract: type[_ContractT], label: str
) -> dict[str, _ContractT]:
    """Structure one optional host mapping of contract values under ``label``."""

    if values is None:
        return {}
    return {
        key: _structured(item, contract, f"{label}.{key}")
        for key, item in values.items()
    }


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

    typed_artifacts = _structured_map(artifacts, ArtifactRef, "artifacts")
    typed_evidence = _structured_map(evidence, EvidenceRef, "evidence")
    typed_lineages = _structured_map(lineages, IdentityLineage, "lineages")
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


def _safe_segment(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        return value
    return "id-" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _persist(
    root: Path,
    *,
    value: object,
    role: str,
    media_type: str,
    schema_uri: str | None = None,
) -> _Persisted:
    """Retain one artifact through the shared content-addressed store.

    The shared store owns the ``<root>/sha256-<hex>`` layout, the size bound,
    the digest check, and the private permissions, so an artifact Mold retains
    resolves through ``resolve_artifact`` and through Cook's path ingress with
    the same artifact root.
    """

    payload = value if isinstance(value, bytes) else canonical_bytes(value)
    digest = hashlib.sha256(payload).hexdigest()
    retained = root.resolve() / f"sha256-{digest}"
    identity: dict[str, str] = {
        "artifact_id": f"{_safe_segment(role)}-{digest}",
        "role": role,
        "uri": retained.as_uri(),
        "media_type": media_type,
    }
    reference = materialize_artifact_ref(payload, **identity, schema_uri=schema_uri)
    try:
        resolved = resolve_verified_bytes(reference, payload, None, root)
    except (ArtifactDigestMismatchError, ArtifactResolutionError, OSError) as exc:
        raise FinalizationError(f"could not retain {role} artifact: {exc}") from exc
    if Path(resolved.path) != retained:
        raise FinalizationError(
            f"retained {role} artifact landed outside the artifact root: {resolved.path}"
        )
    return _Persisted(reference, value)


def _flow_items(body: str) -> list[str]:
    """Split one YAML flow sequence body on the commas outside quoted items."""

    items: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in body:
        if quote is not None:
            if char != quote:
                current.append(char)
            else:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    if quote is not None:
        raise FinalizationError("gates_overridden is malformed: unbalanced quote")
    items.append("".join(current))
    return items


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
            return tuple(_gate_item(part) for part in _flow_items(body))
        return (_gate_item(inline),)
    return ()


def _frontmatter(text: str) -> _Frontmatter:
    if not text.startswith("---"):
        raise FinalizationError("spec has no frontmatter")
    values = parse_spec_frontmatter(text)
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
    return CookUnmetRequirement(
        requirement_id=requirement_id,
        kind=kind,
        description=description,
    )


def _hold(hold_id: str, kind: CookHoldKind, reason: str) -> CookExecutionHold:
    return CookExecutionHold(
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
        _write_bounded(candidate, snapshot.content)
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
    raw = unstructure_contract(value)
    if not isinstance(raw, dict):
        raise FinalizationError("canonical output must be a JSON object")
    return cast(dict[str, object], raw)


def _save_result(root: Path, operation_id: str, output: Mapping[str, object]) -> Path:
    path = root / "results" / f"{_safe_segment(operation_id)}.json"
    _write_bounded(path, (json.dumps(output, sort_keys=True, indent=2) + "\n").encode())
    return path


def _host_coverage(
    proposed: MoldCookCoverage | Mapping[str, object] | Path | None,
    planner: PlannerResult | None,
    plan: CurdPlan | None,
) -> MoldCookCoverage | None:
    """Return the coverage Mold proposes, never the coverage an approval carries.

    An explicit host value wins.  Otherwise the canonical plan and its planner
    result are the proposal, so the approval under test supplies only one side
    of the coverage binding.
    """

    if proposed is not None:
        value = _read_json(proposed) if isinstance(proposed, Path) else proposed
        return _structured(value, MoldCookCoverage, "coverage")
    if planner is None or plan is None:
        return None
    try:
        return MoldCookCoverage(
            curd_ids=tuple(curd.curd_id for curd in plan.curds),
            unresolved_work=planner.unresolved_work,
        )
    except (TypeError, ValueError) as exc:
        raise FinalizationError(
            f"host coverage could not be derived from the canonical plan: {exc}"
        ) from exc


def _blocked_outcome(
    artifact_root: Path,
    operation_id: str,
    *,
    request_id: str,
    input_kind: MoldCookInputKind,
    ledger: _GateLedger,
    spec_ref: ArtifactRef,
) -> FinalizationOutcome:
    """Save incomplete work as a validated, blocked preparation result."""
    references = ledger.references
    holds = ledger.holds
    requirements = ledger.requirements
    version = require_contract_version(CookPreparationResult)
    preparation = CookPreparationResult(
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


@dataclass(frozen=True)
class _ApprovalEvidence:
    """Typed approval and its retained artifact, when both are available."""

    approval: MoldCookApproval | None
    persisted: _Persisted | None


@dataclass(frozen=True)
class _PlannerArtifacts:
    """Canonical planner authority and the artifacts retained for it."""

    planner: PlannerResult | None
    plan: CurdPlan | None
    planner_persisted: _Persisted | None
    plan_persisted: _Persisted | None


@dataclass(frozen=True)
class _TasteEvidence:
    """Retained taste verdict and taste decision ledger artifacts."""

    verdict_persisted: _Persisted | None
    ledger_persisted: _Persisted | None


@dataclass
class _GateLedger:
    """Findings the gates append, in gate order."""

    references: list[ArtifactRef] = field(default_factory=list)
    requirements: list[CookUnmetRequirement] = field(default_factory=list)
    holds: list[CookExecutionHold] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """Report whether any gate recorded a requirement or a hold."""
        return bool(self.requirements or self.holds)


def _gate_spec_validation(ledger: _GateLedger, snapshot: _SpecSnapshot) -> None:
    """Require strict Mold spec validation to pass."""
    requirements = ledger.requirements
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


def _gate_lifecycle(ledger: _GateLedger, frontmatter: _Frontmatter) -> None:
    """Hold work whose declared lifecycle is not a plain approval."""
    requirements = ledger.requirements
    holds = ledger.holds
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


def _gate_gate_override(ledger: _GateLedger, frontmatter: _Frontmatter) -> None:
    """Hold work that declares overridden handshake gates."""
    requirements = ledger.requirements
    holds = ledger.holds
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


def _gate_curdle_anyway(ledger: _GateLedger, *, curdle_anyway: bool) -> None:
    """Hold work saved through the curdle-anyway escape hatch."""
    requirements = ledger.requirements
    holds = ledger.holds
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


def _gate_user_directive(ledger: _GateLedger, frontmatter: _Frontmatter) -> None:
    """Hold work whose whole-request directive blocks execution."""
    requirements = ledger.requirements
    holds = ledger.holds
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


def _gate_approval_evidence(
    ledger: _GateLedger,
    *,
    approval: MoldCookApproval | Mapping[str, object] | Path | None,
    artifact_root: Path,
    request_id: str,
    spec_digest: str,
) -> _ApprovalEvidence:
    """Load, retain, and bind explicit approval evidence.

    Missing, unreadable, or unbound approval evidence is an unmet requirement,
    never a raised error.
    """
    requirements = ledger.requirements
    references = ledger.references
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
        if typed_approval.spec_digest != spec_digest:
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
    return _ApprovalEvidence(typed_approval, approval_persisted)


def _gate_planner_artifacts(
    ledger: _GateLedger,
    *,
    mode: MoldCookMode,
    planner_result: PlannerResult | Mapping[str, object] | Path | None,
    plan: CurdPlan | Mapping[str, object] | Path | None,
    artifact_root: Path,
) -> _PlannerArtifacts:
    """Materialize and retain the planner authority the tier requires.

    Invalid or absent planner artifacts are unmet requirements, never raised
    errors.
    """
    requirements = ledger.requirements
    references = ledger.references
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
    return _PlannerArtifacts(
        typed_planner, typed_plan, planner_persisted, plan_persisted
    )


def _gate_taste(
    ledger: _GateLedger,
    *,
    spec_text: str,
    taste_result: ForkTasteVerdict | Mapping[str, object] | Path | None,
    decision_ledger: object | None,
    artifact_root: Path,
) -> _TasteEvidence:
    """Validate and retain the taste verdict and its decision ledger."""
    requirements = ledger.requirements
    references = ledger.references
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
                schema_uri=FORK_TASTE_VERDICT_SCHEMA_URI,
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
                schema_uri=TASTE_LEDGER_SCHEMA_URI,
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
    return _TasteEvidence(taste_persisted, taste_ledger_persisted)


def _gate_landing(
    ledger: _GateLedger,
    *,
    snapshot: _SpecSnapshot,
    spec_ref: ArtifactRef,
    lifecycle: str,
    planner: _PlannerArtifacts,
    taste: _TasteEvidence,
) -> Landing | None:
    """Read the spec's landing declaration through the shared evaluator."""
    requirements = ledger.requirements
    holds = ledger.holds
    bound_taste = (
        taste.verdict_persisted is not None and taste.ledger_persisted is not None
    )
    try:
        readiness = evaluate_mold_cook_spec(
            snapshot.content,
            spec_ref=spec_ref,
            plan=planner.plan,
            lifecycle=lifecycle,
            taste_verdict_ref=(
                taste.verdict_persisted.reference
                if bound_taste and taste.verdict_persisted is not None
                else None
            ),
            taste_ledger_ref=(
                taste.ledger_persisted.reference
                if bound_taste and taste.ledger_persisted is not None
                else None
            ),
            holds=holds,
        )
    except (ContractValidationError, TypeError, ValueError) as exc:
        _append_requirement(
            requirements,
            _requirement(
                "landing-declaration", CookRequirementKind.INTEGRITY, str(exc)
            ),
        )
        return None
    return readiness.landing or Landing(shape=LandingShape.SINGLE)


def expected_plan_approval_kind(planner: PlannerResult) -> MoldCookApprovalKind:
    """Name the approval kind one Full-tier planner disposition requires.

    The shared seam owns the same test for Cook and for the handoff validator.
    This copy stays in Mold until a wave may edit ``shared/`` and host one.
    """

    return (
        MoldCookApprovalKind.PARTIAL_PLAN
        if planner.disposition is PlannerDisposition.PARTIAL
        else MoldCookApprovalKind.PLAN
    )


def _gate_host_coverage(
    ledger: _GateLedger,
    *,
    proposed: MoldCookCoverage | Mapping[str, object] | Path | None,
    planner: _PlannerArtifacts,
) -> MoldCookCoverage | None:
    """Derive the host coverage proposal, blocking on a malformed input.

    Host coverage is evidence, not a lifecycle control, so a value that cannot
    be read becomes an unmet requirement instead of a raised error.
    """
    try:
        return _host_coverage(proposed, planner.planner, planner.plan)
    except (FinalizationError, OSError) as exc:
        _append_requirement(
            ledger.requirements,
            _requirement(
                "host-coverage",
                CookRequirementKind.SCOPE,
                f"host-proposed scope coverage is unreadable or malformed: {exc}",
            ),
        )
        return None


def _gate_coverage(
    ledger: _GateLedger,
    *,
    mode: MoldCookMode,
    coverage: MoldCookCoverage | None,
    approval: _ApprovalEvidence,
    planner: _PlannerArtifacts,
    landing: Landing | None,
) -> None:
    """Check the host-proposed coverage against the tier and the plan."""
    requirements = ledger.requirements
    typed_approval = approval.approval
    typed_planner = planner.planner
    typed_plan = planner.plan
    if typed_approval is None:
        _append_requirement(
            requirements,
            _requirement(
                "scope-approval",
                CookRequirementKind.SCOPE,
                "approved scope coverage is required before finalization",
            ),
        )
    if coverage is None:
        _append_requirement(
            requirements,
            _requirement(
                "host-coverage",
                CookRequirementKind.SCOPE,
                "host-proposed scope coverage is required before finalization",
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
        expected_kind = expected_plan_approval_kind(typed_planner)
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
            if landing.shape is not LandingShape.SINGLE:
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


def _gate_coverage_binding(
    ledger: _GateLedger,
    *,
    approval: _ApprovalEvidence,
    coverage: MoldCookCoverage | None,
) -> None:
    """Require the approved coverage to still equal the host proposal."""
    requirements = ledger.requirements
    typed_approval = approval.approval
    if (
        typed_approval is not None
        and coverage is not None
        and typed_approval.coverage != coverage
    ):
        _append_requirement(
            requirements,
            _requirement(
                "coverage-binding",
                CookRequirementKind.INTEGRITY,
                "approval coverage changed during finalization",
            ),
        )


def _gate_approval_envelope(
    ledger: _GateLedger,
    *,
    mode: MoldCookMode,
    request_id: str,
    spec_digest: str,
    coverage: MoldCookCoverage | None,
    approval: _ApprovalEvidence,
    planner: _PlannerArtifacts,
    artifact_root: Path,
) -> None:
    """Bind the approval to the canonical proposal envelope and revalidate it."""
    requirements = ledger.requirements
    typed_approval = approval.approval
    if typed_approval is None:
        return
    typed_planner = planner.planner
    typed_plan = planner.plan
    expected_proposal: bytes | None = None
    if coverage is not None:
        proposal_kind: MoldCookApprovalKind | None = None
        proposal_planner: PlannerResult | None = None
        proposal_plan_digest: str | None = None
        if mode is MoldCookMode.LIGHT:
            proposal_kind = MoldCookApprovalKind.SCOPE
        elif typed_planner is not None and typed_plan is not None:
            proposal_kind = expected_plan_approval_kind(typed_planner)
            proposal_planner = typed_planner
            proposal_plan_digest = typed_plan.digest
        if proposal_kind is not None:
            try:
                expected_proposal = canonical_mold_cook_proposal(
                    request_id=request_id,
                    kind=proposal_kind,
                    spec_digest=spec_digest,
                    coverage=coverage,
                    planner_result=proposal_planner,
                    plan_digest=proposal_plan_digest,
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
            else:
                expected_digest = (
                    "sha256:" + hashlib.sha256(expected_proposal).hexdigest()
                )
                if typed_approval.proposal_digest != expected_digest:
                    _append_requirement(
                        requirements,
                        _requirement(
                            "approval-proposal",
                            CookRequirementKind.INTEGRITY,
                            "approval proposal is not the canonical envelope for this handoff",
                        ),
                    )
    # The shared validator binds the PLAN and PARTIAL_PLAN kinds only when
    # the host hands it the envelope those kinds cannot rebuild alone.
    try:
        _ = validate_mold_cook_approval(
            typed_approval,
            artifact_root=artifact_root,
            expected_proposal=expected_proposal,
        )
    except (ContractValidationError, OSError, TypeError, ValueError) as exc:
        _append_requirement(
            requirements,
            _requirement(
                "approval-evidence",
                CookRequirementKind.APPROVAL,
                f"explicit approval evidence is missing, unreadable, or stale: {exc}",
            ),
        )


def _finalize_publication(
    artifact_root: Path,
    operation_id: str,
    *,
    request_id: str,
    input_kind: MoldCookInputKind,
    mode: MoldCookMode,
    spec_ref: ArtifactRef,
    approval: _ApprovalEvidence,
    planner: _PlannerArtifacts,
    taste: _TasteEvidence,
    coverage: MoldCookCoverage | None,
    ledger: _GateLedger,
) -> FinalizationOutcome:
    """Publish the canonical handoff once every gate has cleared.

    A gap here is a host defect, not incomplete work, so a missing artifact
    raises.  Only a failed publication degrades to a blocked saved result.
    """
    requirements = ledger.requirements
    typed_approval = approval.approval
    approval_persisted = approval.persisted
    if typed_approval is None or approval_persisted is None:
        raise FinalizationError("ready finalization requires approval evidence")
    planner_ref: ArtifactRef | None = None
    plan_ref: ArtifactRef | None = None
    if mode is MoldCookMode.FULL:
        planner_persisted = planner.planner_persisted
        plan_persisted = planner.plan_persisted
        if (
            planner.planner is None
            or planner.plan is None
            or planner_persisted is None
            or plan_persisted is None
        ):
            raise FinalizationError(
                "ready Full-tier finalization requires planner artifacts"
            )
        planner_ref = planner_persisted.reference
        plan_ref = plan_persisted.reference
    handoff_version = require_contract_version(MoldCookHandoff)
    taste_persisted = taste.verdict_persisted
    taste_ledger_persisted = taste.ledger_persisted
    if coverage is None or taste_persisted is None or taste_ledger_persisted is None:
        raise FinalizationError(
            "ready finalization requires coverage and retained taste evidence"
        )
    handoff = MoldCookHandoff(
        contract_version=handoff_version,
        request_id=request_id,
        input_kind=input_kind,
        mode=mode,
        spec_ref=spec_ref,
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
        canonical = canonical_bytes(handoff)
        digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
        published = publish_mold_cook_handoff(
            handoff,
            request_digest=digest,
            operation_id=operation_id,
            artifact_root=artifact_root,
            canonical=canonical,
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
            ledger=ledger,
            spec_ref=spec_ref,
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
    proposed_coverage: MoldCookCoverage | Mapping[str, object] | Path | None = None,
    taste_result: ForkTasteVerdict | Mapping[str, object] | Path | None = None,
    decision_ledger: object | None = None,
    curdle_anyway: bool = False,
    overrides: Mapping[str, object] | None = None,
) -> FinalizationOutcome:
    """Join all Mold authority checks and publish only a ready handoff.

    Each gate appends to the ledger in a fixed order instead of raising, so
    incomplete but well-formed work returns a blocked saved result.  Malformed
    lifecycle or override controls raise ``FinalizationError``.
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
    frontmatter = snapshot.frontmatter
    spec_ref = _persist(
        artifact_root,
        value=snapshot.content,
        role="spec",
        media_type="text/markdown",
    ).reference
    ledger = _GateLedger(references=[spec_ref])
    _gate_spec_validation(ledger, snapshot)
    _gate_lifecycle(ledger, frontmatter)
    _gate_gate_override(ledger, frontmatter)
    _gate_curdle_anyway(ledger, curdle_anyway=curdle_anyway)
    _gate_user_directive(ledger, frontmatter)
    approval_evidence = _gate_approval_evidence(
        ledger,
        approval=approval,
        artifact_root=artifact_root,
        request_id=request_id,
        spec_digest=spec_ref.digest,
    )
    planner_artifacts = _gate_planner_artifacts(
        ledger,
        mode=mode,
        planner_result=planner_result,
        plan=plan,
        artifact_root=artifact_root,
    )
    taste_evidence = _gate_taste(
        ledger,
        spec_text=snapshot.text,
        taste_result=taste_result,
        decision_ledger=decision_ledger,
        artifact_root=artifact_root,
    )
    landing = _gate_landing(
        ledger,
        snapshot=snapshot,
        spec_ref=spec_ref,
        lifecycle=frontmatter.status,
        planner=planner_artifacts,
        taste=taste_evidence,
    )
    coverage = _gate_host_coverage(
        ledger, proposed=proposed_coverage, planner=planner_artifacts
    )
    _gate_coverage(
        ledger,
        mode=mode,
        coverage=coverage,
        approval=approval_evidence,
        planner=planner_artifacts,
        landing=landing,
    )
    _gate_coverage_binding(ledger, approval=approval_evidence, coverage=coverage)
    _gate_approval_envelope(
        ledger,
        mode=mode,
        request_id=request_id,
        spec_digest=spec_ref.digest,
        coverage=coverage,
        approval=approval_evidence,
        planner=planner_artifacts,
        artifact_root=artifact_root,
    )

    if ledger.blocked:
        return _blocked_outcome(
            artifact_root,
            operation_id,
            request_id=request_id,
            input_kind=input_kind,
            ledger=ledger,
            spec_ref=spec_ref,
        )
    return _finalize_publication(
        artifact_root,
        operation_id,
        request_id=request_id,
        input_kind=input_kind,
        mode=mode,
        spec_ref=spec_ref,
        approval=approval_evidence,
        planner=planner_artifacts,
        taste=taste_evidence,
        coverage=coverage,
        ledger=ledger,
    )
