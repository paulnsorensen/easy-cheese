"""Host-side validation and binding for the Mold-to-Cook handoff.

The schema package defines only deterministic value invariants. This module is
the host seam that resolves the referenced bytes, validates each referenced
contract, and checks that approval covers exactly the handoff being accepted.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, cast
from urllib.parse import urlsplit

import attrs
from easy_cheese_schemas import SCHEMA_ROOT
from easy_cheese_schemas.contracts import (
    ArtifactRef,
    CurdPlan,
    Landing,
    MAX_CONTRACT_BYTES,
    NormalizationReceipt,
    PlannerDisposition,
    PlannerResult,
    canonical_bytes,
    landing_layer_errors,
)
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    MOLD_COOK_HANDOFF_SCHEMA_URI,
    CookExecutionHold,
    CookSetupAuthorization,
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import (
    AcceptedArtifact,
    CanonicalArtifact,
    ContractValidationError,
    PublishedArtifact,
    require_contract_version,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.validate import (
    require_exact_keys,
    require_int,
    require_mapping,
    require_relative_path,
    require_str,
)

from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_artifact,
)
from easy_cheese.shared.bounded_read import read_bounded_file
from easy_cheese.shared.publication import (
    accept,
    publish_canonical,
    register_deep_validator,
)
from easy_cheese.shared.taste_test import typed_mold_document
from easy_cheese.shared.wheypoint.canonical import digest_bytes


SETUP_EVIDENCE_SCHEMA_URI = f"{SCHEMA_ROOT}/setup-evidence"


__all__ = [
    "MOLD_COOK_APPROVAL_SCHEMA_URI",
    "MOLD_COOK_HANDOFF_SCHEMA_URI",
    "MoldCookSpecReadiness",
    "SETUP_EVIDENCE_SCHEMA_URI",
    "SetupEvidence",
    "SetupEvidenceExecutionError",
    "accept_mold_cook_handoff",
    "canonical_mold_cook_proposal",
    "dialogue_authorizes_execution",
    "evaluate_mold_cook_spec",
    "materialize_artifact_ref",
    "publish_mold_cook_handoff",
    "resolve_contract",
    "resolve_contract_value",
    "validate_mold_cook_approval",
    "validate_mold_cook_handoff",
    "validate_mold_cook_setup_evidence",
]


@dataclass(frozen=True, slots=True)
class MoldCookSpecReadiness:
    """One bounded spec snapshot and the authority it is fit to support."""

    spec_ref: ArtifactRef
    spec_slug: str
    landing: Landing | None
    lifecycle: str | None
    taste_verdict_ref: ArtifactRef | None
    taste_ledger_ref: ArtifactRef | None
    holds: tuple[CookExecutionHold, ...]


@attrs.define(frozen=True)
class SetupEvidence:
    """Bounded host-runner evidence required before setup execution."""

    prerequisite_curd_id: str
    plan_digest: str
    authorization_digest: str
    runner_command: str
    fixture_path: str
    environment_id: str
    exit_code: int
    captured_output_digest: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "SetupEvidence":
        values = require_mapping(raw, "setup evidence")
        required = (
            "prerequisite_curd_id",
            "plan_digest",
            "authorization_digest",
            "runner_command",
            "fixture_path",
            "environment_id",
            "exit_code",
            "captured_output_digest",
        )
        try:
            require_exact_keys(values, required, "setup evidence")
            return cls(
                prerequisite_curd_id=require_str(
                    values["prerequisite_curd_id"],
                    "setup evidence prerequisite_curd_id",
                ),
                plan_digest=require_str(
                    values["plan_digest"], "setup evidence plan_digest"
                ),
                authorization_digest=require_str(
                    values["authorization_digest"],
                    "setup evidence authorization_digest",
                ),
                runner_command=require_str(
                    values["runner_command"], "setup evidence runner_command"
                ),
                fixture_path=require_relative_path(
                    values["fixture_path"], "setup evidence fixture_path"
                ),
                environment_id=require_str(
                    values["environment_id"], "setup evidence environment_id"
                ),
                exit_code=require_int(values["exit_code"], "setup evidence exit_code"),
                captured_output_digest=require_str(
                    values["captured_output_digest"],
                    "setup evidence captured_output_digest",
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(str(exc)) from exc


class SetupEvidenceExecutionError(ContractValidationError):
    """Setup evidence records a non-zero host-runner exit."""


def validate_mold_cook_setup_evidence(
    evidence_ref: ArtifactRef,
    *,
    authorization: CookSetupAuthorization,
    plan: CurdPlan,
    artifact_root: str | Path,
) -> SetupEvidence:
    """Validate durable setup evidence and its retained runner output."""
    if evidence_ref.role != "setup_evidence":
        raise ContractValidationError("setup evidence reference has the wrong role")
    if evidence_ref.schema_uri != SETUP_EVIDENCE_SCHEMA_URI:
        raise ContractValidationError(
            "setup evidence reference has the wrong schema URI"
        )
    raw = _resolve_bytes(evidence_ref, artifact_root)
    try:
        decoded = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("setup evidence is not valid JSON") from exc
    try:
        values = require_mapping(decoded, "setup evidence")
        parsed = SetupEvidence.from_mapping(values)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(str(exc)) from exc
    if not parsed.environment_id.strip():
        raise ContractValidationError("setup evidence environment_id must not be empty")
    if parsed.prerequisite_curd_id != authorization.prerequisite_curd_id:
        raise ContractValidationError("setup evidence names a different prerequisite curd")
    if parsed.plan_digest != plan.digest:
        raise ContractValidationError("setup evidence is stale for this plan")
    if parsed.authorization_digest != digest_bytes(canonical_bytes(authorization)):
        raise ContractValidationError("setup evidence is stale for this authorization")
    if parsed.runner_command not in authorization.allowed_commands:
        raise ContractValidationError("setup command is outside approved commands")
    fixture = require_relative_path(parsed.fixture_path, "setup evidence fixture_path")
    allowed = tuple(
        require_relative_path(item, "setup authorization allowed_paths item")
        for item in authorization.allowed_paths
    )
    if not any(
        fixture == item or fixture.startswith(item.rstrip("/") + "/")
        for item in allowed
    ):
        raise ContractValidationError("setup fixture path is outside approved paths")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", parsed.captured_output_digest) is None:
        raise ContractValidationError("setup output digest is invalid")
    root = Path(artifact_root).resolve()
    output_path = root / (
        f"sha256-{parsed.captured_output_digest.removeprefix('sha256:')}"
    )
    try:
        size = output_path.stat().st_size
        output_ref = ArtifactRef(
            artifact_id=f"{evidence_ref.artifact_id}/output",
            role="setup_output",
            uri=output_path.as_uri(),
            digest=parsed.captured_output_digest,
            size_bytes=size,
            media_type="text/plain",
        )
        _ = resolve_artifact(
            output_ref,
            repository_root=root,
            artifact_directory=root,
            allowed_local_root=root,
        )
    except (ArtifactDigestMismatchError, ArtifactResolutionError, OSError, ValueError) as exc:
        raise ContractValidationError(
            "setup output digest does not match retained bytes"
        ) from exc
    if parsed.exit_code != 0:
        raise SetupEvidenceExecutionError("setup runner did not pass")
    return parsed


def evaluate_mold_cook_spec(
    content: bytes,
    *,
    spec_ref: ArtifactRef,
    plan: CurdPlan | None = None,
    lifecycle: str | None = None,
    taste_verdict_ref: ArtifactRef | None = None,
    taste_ledger_ref: ArtifactRef | None = None,
    holds: Sequence[CookExecutionHold] = (),
) -> MoldCookSpecReadiness:
    """Evaluate one immutable spec snapshot without rereading its path.

    The shared seam owns strict typed Mold parsing, snapshot identity, landing
    parsing, and landing/plan consistency. Taste policy remains host-owned:
    callers pass only the protected typed references that they have verified.
    """

    if len(content) != spec_ref.size_bytes:
        raise ContractValidationError("spec snapshot size does not match spec_ref")
    if digest_bytes(content) != spec_ref.digest:
        raise ContractValidationError("spec snapshot digest does not match spec_ref")
    if (taste_verdict_ref is None) != (taste_ledger_ref is None):
        raise ContractValidationError(
            "taste_verdict_ref and taste_ledger_ref must be supplied together"
        )
    try:
        text = content.decode("utf-8")
        document, _, _ = typed_mold_document(text)
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            f"spec snapshot is not a valid Mold document: {exc}"
        ) from exc
    parsed_lifecycle = document.frontmatter.status
    if lifecycle is not None and lifecycle != parsed_lifecycle:
        raise ContractValidationError(
            "supplied lifecycle is detached from the spec snapshot"
        )
    landing = document.frontmatter.landing
    if plan is not None and landing is not None:
        errors = landing_layer_errors(plan, landing)
        if errors:
            raise ContractValidationError(
                "spec landing does not match plan: " + "; ".join(errors)
            )
    return MoldCookSpecReadiness(
        spec_ref=spec_ref,
        spec_slug=document.frontmatter.slug,
        landing=landing,
        lifecycle=parsed_lifecycle,
        taste_verdict_ref=taste_verdict_ref,
        taste_ledger_ref=taste_ledger_ref,
        holds=tuple(holds),
    )


def _content_for(value: object) -> bytes:
    if isinstance(value, CanonicalArtifact):
        return value.canonical_bytes
    if isinstance(value, bytes):
        return value
    return canonical_bytes(value)


def materialize_artifact_ref(
    value: object,
    *,
    artifact_id: str,
    role: str,
    uri: str,
    media_type: str = "application/json",
    schema_uri: str | None = None,
) -> ArtifactRef:
    """Create a deterministic reference without changing the caller's identity.

    Storage is deliberately separate: the caller chooses the durable URI and
    can call this helper again with the same identity on a retry. The digest is
    always computed from the exact bytes that will be resolved by the consumer.
    """

    content = _content_for(value)
    return ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=uri,
        digest=digest_bytes(content),
        size_bytes=len(content),
        media_type=media_type,
        schema_uri=schema_uri,
    )


def canonical_mold_cook_proposal(
    *,
    request_id: str,
    kind: MoldCookApprovalKind,
    spec_digest: str,
    coverage: MoldCookCoverage,
    planner_result: PlannerResult | None = None,
    plan_digest: str | None = None,
    setup_authorization: CookSetupAuthorization | None = None,
) -> bytes:
    """Render the one canonical proposal envelope for an approval kind."""

    envelope: dict[str, object] = {
        "kind": kind.value,
        "request_id": request_id,
        "spec_digest": spec_digest,
        "coverage": coverage,
    }
    if kind is MoldCookApprovalKind.SCOPE:
        if (
            planner_result is not None
            or plan_digest is not None
            or setup_authorization is not None
        ):
            raise ValueError("scope proposal must not carry plan or runner authority")
    elif kind in {MoldCookApprovalKind.PLAN, MoldCookApprovalKind.PARTIAL_PLAN}:
        if setup_authorization is not None:
            raise ValueError("plan proposal must not carry runner authority")
        if planner_result is None or plan_digest is None or planner_result.plan is None:
            raise ValueError(f"{kind.value} proposal requires a materialized plan")
        if planner_result.plan.digest != plan_digest:
            raise ValueError("proposal plan_digest does not match planner_result.plan")
        envelope.update(
            {
                "plan_digest": plan_digest,
                "planner_result": planner_result,
            }
        )
    elif kind is MoldCookApprovalKind.RUNNER:
        if planner_result is not None or plan_digest is not None:
            raise ValueError("runner proposal must not carry planner authority")
        if setup_authorization is None:
            raise ValueError("runner proposal requires setup_authorization")
        envelope["setup_authorization"] = setup_authorization
    else:
        raise ValueError(f"unsupported Mold-to-Cook proposal kind {kind.value!r}")
    return canonical_bytes(envelope)


_LOCAL_ARTIFACT_SCHEMES = frozenset({"file", "repo"})


def _resolve_bytes(ref: ArtifactRef, artifact_root: str | Path) -> bytes:
    try:
        scheme = urlsplit(ref.uri).scheme
    except ValueError as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} has an invalid URI"
        ) from exc
    if scheme not in _LOCAL_ARTIFACT_SCHEMES:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} uses unsupported URI scheme {scheme!r}"
        )
    root = Path(artifact_root).resolve()
    try:
        resolved = resolve_artifact(
            attrs.evolve(ref, schema_uri=None),
            repository_root=root,
            artifact_directory=root,
            allowed_local_root=root,
        )
    except ArtifactDigestMismatchError as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} is stale or corrupt: {exc}"
        ) from exc
    except ArtifactResolutionError as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} is unreadable: {exc}"
        ) from exc
    if not resolved.content:
        raise ContractValidationError(f"artifact {ref.artifact_id!r} is empty")
    return resolved.content


def resolve_contract(
    ref: ArtifactRef,
    contract_type: type,
    artifact_root: str | Path,
) -> CanonicalArtifact:
    """Resolve one artifact reference into a validated canonical contract.

    The reference must resolve to non-empty bytes that parse as the given
    contract type at a host-supported version.
    """

    content = _resolve_bytes(ref, artifact_root)
    version = supported_version_for(contract_type)
    if version is None:
        raise ContractValidationError(
            f"{contract_type.__name__} has no host-supported contract version"
        )
    try:
        return validate_contract(content, contract_type, version)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} does not contain a valid {contract_type.__name__}: {exc}"
        ) from exc


_ContractT = TypeVar("_ContractT")


def _read_contract_path(path: Path) -> bytes:
    """Read one operator-named contract file under the contract size cap.

    The path comes from the caller's own command line, not from inside an
    artifact, so it is not confined to the artifact root: an operator may
    keep an approval or a planner result anywhere. The shared reader still
    refuses a final symlink and anything that is not a regular file, and
    still stops at `MAX_CONTRACT_BYTES`. Containment stays on the `file://`
    references that an artifact carries, which `resolve_artifact` resolves.
    """

    try:
        return read_bounded_file(path, limit=MAX_CONTRACT_BYTES)
    except OSError as exc:
        raise ContractValidationError(
            f"contract path {path} is unreadable: {exc}"
        ) from exc


def resolve_contract_value(
    value: object,
    contract_type: type[_ContractT],
    artifact_root: str | Path,  # pyright: ignore[reportUnusedParameter]
) -> _ContractT:
    """Resolve one raw producer value into its validated contract instance.

    A producer holds a contract as a local path, raw bytes, a decoded mapping,
    or an already typed instance. Every shape passes the same host-supported
    version check here, so a typed instance a producer built in memory is
    trusted no further than bytes it just read. `artifact_root` stays in the
    signature because every producer seam names its retention root here, and
    because a shape that resolves a reference would need it; the operator-named
    path shape does not.
    """

    raw: object
    if isinstance(value, Path):
        raw = _read_contract_path(value)
    elif isinstance(value, contract_type):
        raw = canonical_bytes(value)
    elif isinstance(value, (bytes, Mapping)):
        raw = cast(object, value)
    else:
        raise ContractValidationError(
            f"cannot resolve a {contract_type.__name__} "
            + f"from a {type(value).__name__} value"
        )
    version = supported_version_for(contract_type)
    if version is None:
        raise ContractValidationError(
            f"{contract_type.__name__} has no host-supported contract version"
        )
    try:
        artifact = validate_contract(raw, contract_type, version)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            f"value is not a valid {contract_type.__name__}: {exc}"
        ) from exc
    return cast(_ContractT, artifact.value)


def _validate_proposal(
    approval: MoldCookApproval,
    artifact_root: str | Path,
    *,
    expected: bytes | None = None,
) -> bytes:
    content = _resolve_bytes(approval.proposal_ref, artifact_root)
    if approval.proposal_ref.media_type.split(";", 1)[0] == "application/json":
        try:
            decoded = cast(object, json.loads(content))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ContractValidationError(
                "approval proposal is not valid JSON"
            ) from exc
        try:
            _ = require_mapping(decoded, "approval proposal")
        except ValueError as exc:
            raise ContractValidationError(str(exc)) from exc
    if expected is not None and content != expected:
        raise ContractValidationError(
            "approval proposal is not the canonical envelope for the bound handoff"
        )
    return content


_AFFIRMATIVE_RESPONSES = frozenset(
    {"approved", "approve", "yes", "y", "ok", "lgtm", "confirmed"}
)


def _response_is_affirmative(response_text: str) -> bool:
    normalized = response_text.strip().casefold().rstrip(" \t.!,;:")
    return normalized in _AFFIRMATIVE_RESPONSES


def dialogue_authorizes_execution(dialogue: Mapping[str, object]) -> bool:
    """Report whether one local dialogue explicitly authorizes execution.

    Authorization is affirmative and explicit: the dialogue must name the holds
    it clears and must carry `execution_authorized` as the literal `True`. A
    missing key is never consent.
    """

    clear_holds = dialogue.get("clear_holds")
    if not isinstance(clear_holds, list) or not clear_holds:
        return False
    cleared = cast("list[object]", clear_holds)
    if any(not isinstance(item, str) or not item.strip() for item in cleared):
        return False
    return dialogue.get("execution_authorized") is True


def _validate_response(approval: MoldCookApproval, artifact_root: str | Path) -> bytes:
    content = _resolve_bytes(approval.response_ref, artifact_root)
    if approval.decision is not MoldCookApprovalDecision.APPROVED:
        raise ContractValidationError(
            f"{approval.kind.value} approval carries {approval.decision.value} response"
        )
    if not _response_is_affirmative(approval.response_text):
        raise ContractValidationError("approval response is negative or unresolved")

    if approval.response_ref.role == "response":
        try:
            actual = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractValidationError("response artifact is not UTF-8") from exc
        if actual != approval.response_text:
            raise ContractValidationError(
                "approval response text is detached from response artifact"
            )
    else:
        try:
            parsed = cast(object, json.loads(content))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ContractValidationError(
                "local dialogue artifact is not valid JSON"
            ) from exc
        try:
            dialogue = require_mapping(parsed, "local dialogue artifact")
        except ValueError as exc:
            raise ContractValidationError(str(exc)) from exc
        question = dialogue.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ContractValidationError(
                "local dialogue artifact must record the presented question"
            )
        recorded = dialogue.get("response")
        if recorded != approval.response_text:
            raise ContractValidationError(
                "approval response text is absent from or detached from local dialogue"
            )
        if dialogue.get("hold") or dialogue.get("holds"):
            raise ContractValidationError(
                "approval dialogue preserves an execution hold"
            )
        if not dialogue_authorizes_execution(dialogue):
            raise ContractValidationError(
                "approval dialogue does not authorize execution"
            )
    return content


def _self_bound_proposal(approval: MoldCookApproval) -> bytes | None:
    """Rebuild the canonical envelope an approval binds on its own fields.

    A plan approval names a plan digest but not the planner result that its
    envelope carries, so only the handoff path can supply that envelope.
    """

    if approval.kind is MoldCookApprovalKind.SCOPE:
        return canonical_mold_cook_proposal(
            request_id=approval.request_id,
            kind=approval.kind,
            spec_digest=approval.spec_digest,
            coverage=approval.coverage,
        )
    if approval.kind is MoldCookApprovalKind.RUNNER:
        # `MoldCookApproval.__attrs_post_init__` (see
        # `src/easy_cheese_schemas/mold_cook.py:479-481`) rejects a runner
        # approval without a setup authorization, so it is never None here.
        return canonical_mold_cook_proposal(
            request_id=approval.request_id,
            kind=approval.kind,
            spec_digest=approval.spec_digest,
            coverage=approval.coverage,
            setup_authorization=approval.setup_authorization,
        )
    return None


def validate_mold_cook_approval(
    approval: object,
    artifact_root: str | Path,
    *,
    expected_proposal: bytes | None = None,
) -> MoldCookApproval:
    """Validate durable proposal/response evidence for one approval.

    A supplied `expected_proposal` binds the approval to that canonical
    envelope for every approval kind, including the plan kinds that cannot
    rebuild their own envelope. Without it, only the self-bound kinds are
    checked against an envelope.
    """

    if not isinstance(approval, MoldCookApproval):
        raise TypeError(
            f"validate_mold_cook_approval expects MoldCookApproval, not {type(approval).__name__}"
        )
    expected = (
        expected_proposal
        if expected_proposal is not None
        else _self_bound_proposal(approval)
    )
    _ = _validate_proposal(approval, artifact_root, expected=expected)
    _ = _validate_response(approval, artifact_root)
    return approval


def _check_coverage_against_plan(
    coverage: MoldCookCoverage,
    planner: PlannerResult,
    plan: CurdPlan,
) -> None:
    declared = {curd.curd_id: curd for curd in plan.curds}
    selected = set(coverage.curd_ids)
    unknown = selected - declared.keys()
    if unknown:
        raise ContractValidationError(
            "coverage names unknown canonical curd IDs: " + ", ".join(sorted(unknown))
        )
    if planner.disposition is PlannerDisposition.COMPLETE:
        if tuple(coverage.curd_ids) != tuple(curd.curd_id for curd in plan.curds):
            raise ContractValidationError(
                "complete planner result requires coverage of every canonical curd"
            )
        if coverage.unresolved_work:
            raise ContractValidationError(
                "complete planner result cannot retain unresolved work"
            )
    elif planner.disposition is PlannerDisposition.PARTIAL:
        if not coverage.unresolved_work:
            raise ContractValidationError(
                "partial coverage must acknowledge unresolved work"
            )
        if coverage.unresolved_work != planner.unresolved_work:
            raise ContractValidationError(
                "partial coverage does not preserve the PlannerResult remainder"
            )
    else:
        raise ContractValidationError(
            f"planner disposition {planner.disposition.value} cannot authorize a handoff"
        )
    for curd_id in coverage.curd_ids:
        missing = set(declared[curd_id].dependencies) - selected
        if missing:
            raise ContractValidationError(
                f"coverage for {curd_id!r} omits dependencies: {', '.join(sorted(missing))}"
            )


def _validate_authority_refs(
    handoff: MoldCookHandoff,
    *,
    approval: MoldCookApproval,
    artifact_root: str | Path,
    plan: CurdPlan | None,
) -> None:
    if handoff.setup_evidence_refs and handoff.runner_approval_ref is None:
        raise ContractValidationError(
            "setup evidence requires a bound runner approval reference"
        )
    if handoff.runner_approval_ref is not None and not handoff.setup_evidence_refs:
        raise ContractValidationError(
            "runner approval requires passing setup evidence before execution"
        )
    for reference in (
        handoff.taste_verdict_ref,
        handoff.taste_ledger_ref,
        *handoff.setup_evidence_refs,
    ):
        if reference is not None:
            _ = _resolve_bytes(reference, artifact_root)
    if handoff.runner_approval_ref is None:
        return
    runner_artifact = resolve_contract(
        handoff.runner_approval_ref, MoldCookApproval, artifact_root
    )
    runner = cast(MoldCookApproval, runner_artifact.value)
    if runner.kind is not MoldCookApprovalKind.RUNNER:
        raise ContractValidationError(
            "runner_approval_ref must reference runner approval"
        )
    if runner.request_id != handoff.request_id:
        raise ContractValidationError(
            "runner approval request_id does not match handoff"
        )
    if runner.spec_digest != handoff.spec_ref.digest:
        raise ContractValidationError("runner approval is bound to a different spec")
    if runner.coverage != handoff.coverage:
        raise ContractValidationError("runner approval coverage does not match handoff")
    if approval.kind is MoldCookApprovalKind.RUNNER:
        raise ContractValidationError(
            "handoff approval and runner approval must be distinct"
        )
    _ = validate_mold_cook_approval(runner, artifact_root)
    if handoff.setup_evidence_refs:
        if plan is None:
            raise ContractValidationError(
                "setup evidence requires a materialized plan"
            )
        authorization = runner.setup_authorization
        if authorization is None:
            raise ContractValidationError(
                "runner approval has no setup authorization"
            )
        for evidence_ref in handoff.setup_evidence_refs:
            _ = validate_mold_cook_setup_evidence(
                evidence_ref,
                authorization=authorization,
                plan=plan,
                artifact_root=artifact_root,
            )


def _validate_bound_evidence(
    handoff: MoldCookHandoff,
    approval: MoldCookApproval,
    artifact_root: str | Path,
    *,
    spec_content: bytes,
    plan: CurdPlan | None = None,
    planner: PlannerResult | None = None,
) -> None:
    """Check the spec snapshot, the envelope, the response, and the authority."""

    _ = evaluate_mold_cook_spec(
        spec_content,
        spec_ref=handoff.spec_ref,
        plan=plan,
        taste_verdict_ref=handoff.taste_verdict_ref,
        taste_ledger_ref=handoff.taste_ledger_ref,
    )
    expected = canonical_mold_cook_proposal(
        request_id=handoff.request_id,
        kind=approval.kind,
        spec_digest=handoff.spec_ref.digest,
        coverage=handoff.coverage,
        planner_result=planner,
        plan_digest=None if plan is None else plan.digest,
    )
    _ = _validate_proposal(approval, artifact_root, expected=expected)
    _ = _validate_response(approval, artifact_root)
    _validate_authority_refs(
        handoff,
        approval=approval,
        artifact_root=artifact_root,
        plan=plan,
    )


def validate_mold_cook_handoff(
    handoff: object, artifact_root: str | Path
) -> MoldCookHandoff:
    """Resolve and validate all authority bound by a canonical handoff."""

    if not isinstance(handoff, MoldCookHandoff):
        raise TypeError(
            f"validate_mold_cook_handoff expects MoldCookHandoff, not {type(handoff).__name__}"
        )
    spec_content = _resolve_bytes(handoff.spec_ref, artifact_root)
    approval_artifact = resolve_contract(
        handoff.approval_ref, MoldCookApproval, artifact_root
    )
    approval = cast(MoldCookApproval, approval_artifact.value)
    if approval.request_id != handoff.request_id:
        raise ContractValidationError("approval request_id does not match handoff")
    if approval.spec_digest != handoff.spec_ref.digest:
        raise ContractValidationError("approval is bound to a different spec")
    if approval.coverage != handoff.coverage:
        raise ContractValidationError(
            "approval coverage does not match handoff coverage"
        )

    if handoff.mode is MoldCookMode.LIGHT:
        if approval.kind is not MoldCookApprovalKind.SCOPE:
            raise ContractValidationError("light handoff requires scope approval")
        if approval.plan_digest is not None:
            raise ContractValidationError(
                "light handoff approval must not carry a plan digest"
            )
        if handoff.planner_result_ref is not None or handoff.plan_ref is not None:
            raise ContractValidationError(
                "light handoff must not reference planner artifacts"
            )
        if handoff.coverage.unresolved_work:
            raise ContractValidationError(
                "light handoff cannot discard unresolved work"
            )
        _validate_bound_evidence(
            handoff,
            approval,
            artifact_root,
            spec_content=spec_content,
        )
        return handoff

    if handoff.planner_result_ref is None or handoff.plan_ref is None:
        raise ContractValidationError(
            "full handoff is missing planner or plan reference"
        )
    planner_artifact = resolve_contract(
        handoff.planner_result_ref, PlannerResult, artifact_root
    )
    plan_artifact = resolve_contract(handoff.plan_ref, CurdPlan, artifact_root)
    planner = cast(PlannerResult, planner_artifact.value)
    plan = cast(CurdPlan, plan_artifact.value)
    if planner.plan is None:
        raise ContractValidationError(
            "full handoff planner result has no materialized plan"
        )
    if canonical_bytes(planner.plan) != plan_artifact.canonical_bytes:
        raise ContractValidationError("planner and plan references are detached")
    if approval.plan_digest != plan.digest:
        raise ContractValidationError("approval is bound to a different plan")
    expected_kind = (
        MoldCookApprovalKind.PARTIAL_PLAN
        if planner.disposition is PlannerDisposition.PARTIAL
        else MoldCookApprovalKind.PLAN
    )
    if approval.kind is not expected_kind:
        raise ContractValidationError(
            f"full handoff requires {expected_kind.value} approval, got {approval.kind.value}"
        )
    _check_coverage_against_plan(handoff.coverage, planner, plan)
    _validate_bound_evidence(
        handoff,
        approval,
        artifact_root,
        spec_content=spec_content,
        plan=plan,
        planner=planner,
    )
    return handoff


def publish_mold_cook_handoff(
    handoff: MoldCookHandoff,
    *,
    request_digest: str,
    operation_id: str,
    artifact_root: str | Path,
    canonical: bytes | None = None,
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    """Publish an already materialized, strictly validated Mold handoff.

    A caller that already serialized ``handoff`` -- to derive the request
    digest, for example -- passes those bytes as ``canonical`` so the handoff
    is serialized once for both uses.
    """

    try:
        version = require_contract_version(MoldCookHandoff)
    except TypeError as exc:
        # The publish seam answers with one error type. A host that cannot
        # name a supported version is a defect here, not a `TypeError` the
        # caller must also catch.
        raise ContractValidationError(str(exc)) from exc

    def prepare() -> tuple[CanonicalArtifact, NormalizationReceipt | None]:
        return (
            validate_contract(
                canonical if canonical is not None else canonical_bytes(handoff),
                MoldCookHandoff,
                version,
            ),
            None,
        )

    return publish_canonical(
        request_digest=request_digest,
        source_phase="mold",
        destination_phase="cook",
        payload_schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI,
        operation_id=operation_id,
        artifact_root=artifact_root,
        prepare=prepare,
        _before_reveal=_before_reveal,
    )


def accept_mold_cook_handoff(
    pointer_path: str | Path,
    *,
    artifact_root: str | Path | None = None,
) -> AcceptedArtifact:
    """Accept a Mold-to-Cook pointer through the shared strict validator."""

    return accept(
        pointer_path,
        destination_phase="cook",
        payload_schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI,
        artifact_root=artifact_root,
    )


register_deep_validator(MOLD_COOK_HANDOFF_SCHEMA_URI, validate_mold_cook_handoff)
