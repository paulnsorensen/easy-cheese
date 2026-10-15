"""Mold spec and planner finalization for direct Cook inputs."""

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
    PlannerRequest,
    PlannerResult,
    PlannerResultWriterView,
)
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    CookRequirementKind,
    CookUnmetRequirement,
    MoldCookCoverage,
)
from easy_cheese_schemas.planner import materialize_planner_result

# `schema_runtime` owns typed structuring for every attrs contract but publishes
# no structuring entry point yet. Mold borrows the private one rather than keep
# a second field-by-field structuring path.
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    _typed_host as structure_contract_value,  # pyright: ignore[reportPrivateUsage]
    canonical_bytes,
    load_agent_writer_view,
)
from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_verified_bytes,
)
from easy_cheese.shared.bounded_read import BoundedReadOverflow, read_bounded_file
from easy_cheese.shared.frontmatter_lists import frontmatter_string_list
from easy_cheese.shared.mold_cook_handoff import (
    evaluate_mold_cook_spec,
    materialize_artifact_ref,
    request_directive,
    validate_bound_execution,
    resolve_contract_value,
)
from easy_cheese.shared.publication import atomic_write
from easy_cheese.shared.taste_test import (
    MAX_SPEC_BYTES,
    parse_spec_frontmatter,
    read_spec_text,
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
_ALLOWED_OVERRIDE_KEYS = frozenset({"save_approved"})
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
    execution_holds: tuple[str, ...]


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


def _string_list_field(text: str, key: str) -> tuple[str, ...]:
    """Read frontmatter ``key`` as a list; a malformed list is a caller error."""
    try:
        return frontmatter_string_list(text, key)
    except ValueError as exc:
        raise FinalizationError(str(exc)) from exc


def _frontmatter(text: str) -> _Frontmatter:
    if not text.startswith("---"):
        raise FinalizationError("spec has no frontmatter")
    values = parse_spec_frontmatter(text)
    status_value = values.get("status")
    if not isinstance(status_value, str) or status_value not in _ALLOWED_LIFECYCLES:
        raise FinalizationError(
            f"unsupported spec lifecycle {status_value!r}; expected one of {sorted(_ALLOWED_LIFECYCLES)}"
        )
    overrides = _string_list_field(text, "gates_overridden")
    holds = _string_list_field(text, "execution_holds")
    directive = request_directive(text)
    return _Frontmatter(
        status_value,
        overrides,
        directive,
        holds,
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




def _canonical_output(value: object) -> dict[str, object]:
    raw = unstructure_contract(value)
    if not isinstance(raw, dict):
        raise FinalizationError("canonical output must be a JSON object")
    return cast(dict[str, object], raw)


def _result_path(root: Path, operation_id: str) -> Path:
    return root / "results" / f"{_safe_segment(operation_id)}.json"


def _save_result(root: Path, operation_id: str, output: Mapping[str, object]) -> Path:
    path = _result_path(root, operation_id)
    payload = (json.dumps(output, sort_keys=True, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != payload:
            raise FinalizationError(
                f"operation id {operation_id!r} already holds a different ready result"
            )
        return path
    _write_bounded(path, payload)
    return path


def _host_coverage(
    proposed: MoldCookCoverage | Mapping[str, object] | Path | None,
    planner: PlannerResult | None,
    plan: CurdPlan | None,
) -> MoldCookCoverage | None:
    """Return the coverage Mold proposes.

    An explicit host value wins.  Otherwise the canonical plan and its planner
    result are the proposal.
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
    ledger: _GateLedger,
    spec_ref: ArtifactRef,
) -> FinalizationOutcome:
    """Save incomplete work without creating a Cook entry contract."""
    output: dict[str, object] = {
        "status": "saved-not-ready",
        "ready": False,
        "saved": True,
        "request_id": request_id,
        "spec_ref": _canonical_output(spec_ref),
        "references": [_canonical_output(item) for item in ledger.references],
        "requirements": [_canonical_output(item) for item in ledger.requirements],
        "holds": [_canonical_output(item) for item in ledger.holds],
    }
    result_path = _save_result(artifact_root, operation_id, output)
    output["result_path"] = str(result_path)
    return FinalizationOutcome(output)


@dataclass(frozen=True)
class _PlannerArtifacts:
    """Canonical planner authority and the artifacts retained for it."""

    planner: PlannerResult | None
    plan: CurdPlan | None
    planner_persisted: _Persisted | None
    plan_persisted: _Persisted | None



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
                "gates-overridden",
                CookHoldKind.PREPARATION,
                "user approved saving this design with unchecked handshake items: "
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


def _gate_execution_holds(ledger: _GateLedger, frontmatter: _Frontmatter) -> None:
    """Hold work that carries an unresolved named execution hold.

    Mold may save a draft with a named hold from the scope audit table, an
    unresolved ALIAS or NEW ENTITY binding, or an unchecked coherence box.
    Finalization is the chokepoint that runs that table: it blocks while any
    ``execution_holds`` entry remains, so it never returns ready for a draft
    that still carries one.
    """
    requirements = ledger.requirements
    holds = ledger.holds
    for index, entry in enumerate(frontmatter.execution_holds, start=1):
        _append_hold(
            holds,
            _hold(
                f"execution-hold-{index}",
                CookHoldKind.PREPARATION,
                f"unresolved execution hold: {entry}",
            ),
        )
        _append_requirement(
            requirements,
            _requirement(
                f"execution-hold-{index}",
                CookRequirementKind.EVIDENCE,
                f"execution hold {entry!r} must be resolved before publication",
            ),
        )


def _gate_save_approved(ledger: _GateLedger, *, save_approved: bool) -> None:
    """Hold work saved after the user approved saving with unchecked items."""
    requirements = ledger.requirements
    holds = ledger.holds
    if save_approved:
        _append_hold(
            holds,
            _hold(
                "save-approved",
                CookHoldKind.PREPARATION,
                "save approval is save-only and never waives execution readiness",
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


def _gate_planner_artifacts(
    ledger: _GateLedger,
    *,
    planner_result: PlannerResult | Mapping[str, object] | Path | None,
    plan: CurdPlan | Mapping[str, object] | Path | None,
    artifact_root: Path,
) -> _PlannerArtifacts:
    """Retain the planner result and its materialized plan."""
    typed_planner: PlannerResult | None = None
    typed_plan: CurdPlan | None = None
    planner_persisted: _Persisted | None = None
    plan_persisted: _Persisted | None = None
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
            ledger.references.append(planner_persisted.reference)
        if plan is not None:
            typed_plan = _load_contract(plan, CurdPlan)
        elif typed_planner is not None:
            typed_plan = typed_planner.plan
        if typed_plan is not None:
            plan_persisted = _persist(
                artifact_root,
                value=typed_plan,
                role="curd_plan",
                media_type="application/json",
                schema_uri="https://schemas.easy-cheese.dev/curd-plan",
            )
            ledger.references.append(plan_persisted.reference)
    except (FinalizationError, ContractValidationError, OSError, TypeError, ValueError) as exc:
        _append_requirement(
            ledger.requirements,
            _requirement(
                "planner-artifacts",
                CookRequirementKind.PLAN,
                f"planner artifacts are invalid or stale: {exc}",
            ),
        )
    if typed_planner is None or typed_plan is None:
        _append_requirement(
            ledger.requirements,
            _requirement(
                "planner-artifacts",
                CookRequirementKind.PLAN,
                "Cook needs a PlannerResult and materialized CurdPlan",
            ),
        )
    return _PlannerArtifacts(
        typed_planner, typed_plan, planner_persisted, plan_persisted
    )




def _gate_landing(
    ledger: _GateLedger,
    *,
    snapshot: _SpecSnapshot,
    spec_ref: ArtifactRef,
    lifecycle: str,
    planner: _PlannerArtifacts,
) -> Landing | None:
    """Read the spec landing declaration against its plan."""
    try:
        readiness = evaluate_mold_cook_spec(
            snapshot.content,
            spec_ref=spec_ref,
            plan=planner.plan,
            lifecycle=lifecycle,
            holds=ledger.holds,
        )
    except (ContractValidationError, TypeError, ValueError) as exc:
        _append_requirement(
            ledger.requirements,
            _requirement(
                "landing-declaration", CookRequirementKind.INTEGRITY, str(exc)
            ),
        )
        return None
    return readiness.landing or Landing(shape=LandingShape.SINGLE)


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
    coverage: MoldCookCoverage | None,
    planner: _PlannerArtifacts,
    landing: Landing | None,
) -> None:
    """Check selected scope against the bound plan and landing declaration."""
    if coverage is None:
        _append_requirement(
            ledger.requirements,
            _requirement(
                "host-coverage",
                CookRequirementKind.SCOPE,
                "selected scope is required before finalization",
            ),
        )
        return
    plan = planner.plan
    if plan is None:
        return
    declared_ids = {curd.curd_id for curd in plan.curds}
    if not set(coverage.curd_ids).issubset(declared_ids):
        _append_requirement(
            ledger.requirements,
            _requirement(
                "coverage-ids",
                CookRequirementKind.INTEGRITY,
                "selected scope names unknown canonical curd IDs",
            ),
        )
    if landing is not None and landing.shape is not LandingShape.SINGLE:
        expected = {curd_id for layer in landing.layers for curd_id in layer}
        if expected != declared_ids:
            _append_requirement(
                ledger.requirements,
                _requirement(
                    "landing-coverage",
                    CookRequirementKind.INTEGRITY,
                    "landing coverage must cover exactly the canonical plan curds",
                ),
            )


def _finalize_publication(
    artifact_root: Path,
    operation_id: str,
    *,
    request_id: str,
    spec_ref: ArtifactRef,
    planner: _PlannerArtifacts,
    coverage: MoldCookCoverage | None,
    ledger: _GateLedger,
) -> FinalizationOutcome:
    """Save direct Cook inputs after validating their exact references."""
    if (
        planner.planner_persisted is None
        or planner.plan_persisted is None
        or coverage is None
    ):
        raise FinalizationError("ready finalization requires a planner, plan, and scope")
    planner_ref = planner.planner_persisted.reference
    plan_ref = planner.plan_persisted.reference
    try:
        _ = validate_bound_execution(
            spec_ref=spec_ref,
            planner_result_ref=planner_ref,
            plan_ref=plan_ref,
            coverage=coverage,
            artifact_root=artifact_root,
        )
    except (ContractValidationError, TypeError, ValueError) as exc:
        _append_requirement(
            ledger.requirements,
            _requirement(
                "execution-inputs",
                CookRequirementKind.INTEGRITY,
                f"bound Cook inputs are invalid: {exc}",
            ),
        )
        return _blocked_outcome(
            artifact_root, operation_id,
            request_id=request_id, ledger=ledger, spec_ref=spec_ref,
        )
    result_path = _result_path(artifact_root, operation_id)
    output: dict[str, object] = {
        "status": "ready",
        "ready": True,
        "saved": True,
        "next": "cook",
        "command": ["/cook", "--auto", "--result", str(result_path)],
        "request_id": request_id,
        "spec_ref": _canonical_output(spec_ref),
        "planner_result_ref": _canonical_output(planner_ref),
        "plan_ref": _canonical_output(plan_ref),
        "coverage": _canonical_output(coverage),
    }
    _ = _save_result(artifact_root, operation_id, output)
    output["result_path"] = str(result_path)
    return FinalizationOutcome(output)


def finalize_mold(
    spec_path: Path,
    *,
    artifact_root: Path,
    operation_id: str,
    request_id: str,
    planner_result: PlannerResult | Mapping[str, object] | Path | None = None,
    plan: CurdPlan | Mapping[str, object] | Path | None = None,
    proposed_coverage: MoldCookCoverage | Mapping[str, object] | Path | None = None,
    save_approved: bool = False,
    overrides: Mapping[str, object] | None = None,
) -> FinalizationOutcome:
    """Save incomplete work or return direct validated Cook inputs."""
    if overrides is not None:
        unknown = set(overrides) - _ALLOWED_OVERRIDE_KEYS
        if unknown:
            raise FinalizationError(
                "unknown finalization override(s): " + ", ".join(sorted(unknown))
            )
        save_approved = bool(overrides.get("save_approved", save_approved))
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
    _gate_execution_holds(ledger, frontmatter)
    _gate_save_approved(ledger, save_approved=save_approved)
    _gate_user_directive(ledger, frontmatter)
    planner_artifacts = _gate_planner_artifacts(
        ledger,
        planner_result=planner_result,
        plan=plan,
        artifact_root=artifact_root,
    )
    landing = _gate_landing(
        ledger,
        snapshot=snapshot,
        spec_ref=spec_ref,
        lifecycle=frontmatter.status,
        planner=planner_artifacts,
    )
    coverage = _gate_host_coverage(
        ledger, proposed=proposed_coverage, planner=planner_artifacts
    )
    _gate_coverage(
        ledger,
        coverage=coverage,
        planner=planner_artifacts,
        landing=landing,
    )
    if ledger.blocked:
        return _blocked_outcome(
            artifact_root, operation_id,
            request_id=request_id, ledger=ledger, spec_ref=spec_ref,
        )
    return _finalize_publication(
        artifact_root,
        operation_id,
        request_id=request_id,
        spec_ref=spec_ref,
        planner=planner_artifacts,
        coverage=coverage,
        ledger=ledger,
    )
