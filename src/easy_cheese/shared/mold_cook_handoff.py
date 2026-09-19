"""Host-side validation and binding for the Mold-to-Cook handoff.

The schema package defines only deterministic value invariants. This module is
the host seam that resolves the referenced bytes, validates each referenced
contract, and checks that approval covers exactly the handoff being accepted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit
import attrs
from easy_cheese_schemas.contracts import (
    ArtifactRef,
    ContractVersion,
    CurdPlan,
    Landing,
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
    MoldCookApprovalSource,
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import (
    CanonicalArtifact,
    ContractValidationError,
    supported_version_for,
    validate_contract,
)

from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_artifact,
)
from easy_cheese.shared.taste_test import typed_mold_document
from easy_cheese.shared.wheypoint.canonical import digest_bytes


__all__ = [
    "MOLD_COOK_APPROVAL_SCHEMA_URI",
    "MOLD_COOK_HANDOFF_SCHEMA_URI",
    "MoldCookSpecReadiness",
    "bind_mold_cook_approval",
    "canonical_mold_cook_proposal",
    "dialogue_authorizes_execution",
    "evaluate_mold_cook_spec",
    "materialize_artifact_ref",
    "validate_mold_cook_approval",
    "validate_mold_cook_handoff",
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


def bind_mold_cook_approval(
    *,
    request_id: str,
    kind: MoldCookApprovalKind,
    decision: MoldCookApprovalDecision,
    source: MoldCookApprovalSource,
    spec_digest: str,
    proposal_ref: ArtifactRef,
    response_ref: ArtifactRef,
    response_text: str,
    response_source: str,
    coverage: MoldCookCoverage,
    plan_digest: str | None = None,
    setup_authorization: CookSetupAuthorization | None = None,
) -> MoldCookApproval:
    """Bind explicit response evidence to stable proposal and response refs."""

    version = ContractVersion(
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
        major="1",
        minor="0",
    )
    return MoldCookApproval(
        contract_version=version,
        request_id=request_id,
        kind=kind,
        decision=decision,
        source=source,
        spec_digest=spec_digest,
        proposal_ref=proposal_ref,
        proposal_digest=proposal_ref.digest,
        response_ref=response_ref,
        response_digest=response_ref.digest,
        response_text=response_text,
        response_source=response_source,
        coverage=coverage,
        plan_digest=plan_digest,
        setup_authorization=setup_authorization,
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


def _resolve_contract(
    ref: ArtifactRef,
    contract_type: type,
    artifact_root: str | Path,
) -> CanonicalArtifact:
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
        if not isinstance(decoded, Mapping):
            raise ContractValidationError("approval proposal must be a JSON object")
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
        if not isinstance(parsed, dict):
            raise ContractValidationError("local dialogue artifact must be an object")
        dialogue = cast(dict[str, object], parsed)
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
        if approval.setup_authorization is None:
            raise ContractValidationError(
                "runner approval must carry the authorized setup envelope"
            )
        return canonical_mold_cook_proposal(
            request_id=approval.request_id,
            kind=approval.kind,
            spec_digest=approval.spec_digest,
            coverage=approval.coverage,
            setup_authorization=approval.setup_authorization,
        )
    return None


def validate_mold_cook_approval(
    approval: object, artifact_root: str | Path
) -> MoldCookApproval:
    """Validate durable proposal/response evidence for one approval."""

    if not isinstance(approval, MoldCookApproval):
        raise TypeError(
            f"validate_mold_cook_approval expects MoldCookApproval, not {type(approval).__name__}"
        )
    _ = _validate_response(approval, artifact_root)
    _ = _validate_proposal(
        approval, artifact_root, expected=_self_bound_proposal(approval)
    )
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
) -> None:
    if handoff.setup_evidence_refs and handoff.runner_approval_ref is None:
        raise ContractValidationError(
            "setup evidence requires a bound runner approval reference"
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
    runner_artifact = _resolve_contract(
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
    _validate_authority_refs(handoff, approval=approval, artifact_root=artifact_root)


def validate_mold_cook_handoff(
    handoff: object, artifact_root: str | Path
) -> MoldCookHandoff:
    """Resolve and validate all authority bound by a canonical handoff."""

    if not isinstance(handoff, MoldCookHandoff):
        raise TypeError(
            f"validate_mold_cook_handoff expects MoldCookHandoff, not {type(handoff).__name__}"
        )
    spec_content = _resolve_bytes(handoff.spec_ref, artifact_root)
    approval_artifact = _resolve_contract(
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
    planner_artifact = _resolve_contract(
        handoff.planner_result_ref, PlannerResult, artifact_root
    )
    plan_artifact = _resolve_contract(handoff.plan_ref, CurdPlan, artifact_root)
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
