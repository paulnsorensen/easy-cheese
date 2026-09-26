"""Record one literal user response as a retained `MoldCookApproval`.

Mold finalization and Cook preparation both consume this record. The command
binds the response to the canonical proposal for one spec snapshot. It never
infers consent: a response outside the affirmative set records a rejection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import fromargs

from easy_cheese_schemas import (
    ArtifactRef,
    ContractValidationError,
    PlannerResult,
    canonical_bytes,
)
from easy_cheese_schemas.mold_cook import (
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
    MoldCookCoverage,
)
from easy_cheese.shared.mold_cook_handoff import (
    MoldCookSpecReadiness,
    bind_mold_cook_approval,
    canonical_mold_cook_proposal,
    evaluate_mold_cook_spec,
    host_scope_coverage,
    materialize_artifact_ref,
    resolve_contract_value,
    response_is_affirmative,
)
from easy_cheese.shared.wheypoint.canonical import digest_bytes

__all__ = ["ApprovalRecordError", "approve", "main"]

_PLAN_KINDS = frozenset({MoldCookApprovalKind.PLAN, MoldCookApprovalKind.PARTIAL_PLAN})


class ApprovalRecordError(ValueError):
    """The inputs cannot produce a bound approval record."""


def _retained_path(artifact_root: Path, digest: str) -> Path:
    return artifact_root / f"sha256-{digest.removeprefix('sha256:')}"


def _retain(artifact_root: Path, content: bytes, *, role: str, media: str) -> ArtifactRef:
    """Write content under its digest name and return its reference."""

    digest = digest_bytes(content)
    path = _retained_path(artifact_root, digest)
    _ = path.write_bytes(content)
    return materialize_artifact_ref(
        content,
        artifact_id=f"{role}-{digest.removeprefix('sha256:')[:16]}",
        role=role,
        uri=path.resolve().as_uri(),
        media_type=media,
    )


def _readiness(spec_bytes: bytes, spec_path: Path) -> MoldCookSpecReadiness | None:
    """Evaluate the spec; a spec outside the strict format declares no landing."""

    spec_ref = materialize_artifact_ref(
        spec_bytes,
        artifact_id="spec",
        role="spec",
        uri=spec_path.resolve().as_uri(),
        media_type="text/markdown",
    )
    try:
        return evaluate_mold_cook_spec(spec_bytes, spec_ref=spec_ref)
    except ContractValidationError:
        return None


def approve(
    spec_path: Path,
    *,
    artifact_root: Path,
    request_id: str,
    kind: MoldCookApprovalKind,
    response_text: str,
    planner_result: PlannerResult | None = None,
    coverage: MoldCookCoverage | None = None,
) -> tuple[MoldCookApproval, Path]:
    """Bind one response to the canonical proposal and retain the record."""

    if not response_text.strip():
        raise ApprovalRecordError("the literal user response is required")
    if kind not in _PLAN_KINDS and kind is not MoldCookApprovalKind.SCOPE:
        raise ApprovalRecordError(f"{kind.value} approval is not supported here")
    plan = None if planner_result is None else planner_result.plan
    if kind in _PLAN_KINDS and plan is None:
        raise ApprovalRecordError(f"{kind.value} approval requires --planner-result")
    try:
        spec_bytes = spec_path.read_bytes()
    except OSError as exc:
        raise ApprovalRecordError(f"cannot read spec {spec_path}: {exc}") from exc
    selected = coverage or host_scope_coverage(
        _readiness(spec_bytes, spec_path), planner_result
    )
    if selected is None:
        raise ApprovalRecordError(
            "no plan was supplied and the spec declares no readable landing; "
            + "name each covered curd with --curd-id"
        )
    in_plan = kind in _PLAN_KINDS
    plan_digest = plan.digest if in_plan and plan is not None else None
    spec_digest = digest_bytes(spec_bytes)
    try:
        proposal = canonical_mold_cook_proposal(
            request_id=request_id,
            kind=kind,
            spec_digest=spec_digest,
            coverage=selected,
            planner_result=planner_result if in_plan else None,
            plan_digest=plan_digest,
        )
        artifact_root.mkdir(parents=True, exist_ok=True)
        response_ref = _retain(
            artifact_root, response_text.encode(), role="response", media="text/plain"
        )
        approval = bind_mold_cook_approval(
            request_id=request_id,
            kind=kind,
            decision=(
                MoldCookApprovalDecision.APPROVED
                if response_is_affirmative(response_text)
                else MoldCookApprovalDecision.REJECTED
            ),
            source=MoldCookApprovalSource.USER_RESPONSE,
            spec_digest=spec_digest,
            proposal_ref=_retain(
                artifact_root, proposal, role="proposal", media="application/json"
            ),
            response_ref=response_ref,
            response_text=response_text,
            response_source=response_ref.artifact_id,
            coverage=selected,
            plan_digest=plan_digest,
        )
        record = _retain(
            artifact_root,
            canonical_bytes(approval),
            role="approval",
            media="application/json",
        )
    except (ContractValidationError, OSError, TypeError, ValueError) as exc:
        raise ApprovalRecordError(str(exc)) from exc
    return approval, _retained_path(artifact_root, record.digest)


def approve_cmd(
    spec: str,
    *,
    artifact_root: str,
    request_id: str,
    kind: str,
    response: Annotated[str, fromargs.Parameter(name="--response")],
    planner_result: str | None = None,
    curd_id: tuple[str, ...] = (),
) -> dict[str, object]:
    """Record the user's literal approval response for one spec.

    Parameters
    ----------
    spec
        Path to the mold spec markdown file.
    artifact_root
        Root directory the approval record is retained under.
    request_id
        Request id the approval is bound to.
    kind
        Approval kind: scope, plan, or partial-plan.
    response
        The user's reply, word for word.
    planner_result
        Optional path to a canonical PlannerResult JSON artifact.
    curd_id
        A curd the response covers; repeatable. Default is the full plan or landing.
    """
    allowed = {MoldCookApprovalKind.SCOPE.value, *sorted(k.value for k in _PLAN_KINDS)}
    if kind not in allowed:
        raise fromargs.CliError(
            f"invalid --kind {kind!r}; choose from {sorted(allowed)}", exit_code=2
        )
    planner_path = Path(planner_result) if planner_result is not None else None
    try:
        planner = (
            None
            if planner_path is None
            else resolve_contract_value(planner_path, PlannerResult, Path())
        )
        approval, path = approve(
            Path(spec),
            artifact_root=Path(artifact_root),
            request_id=request_id,
            kind=MoldCookApprovalKind(kind),
            response_text=response,
            planner_result=planner,
            coverage=(
                MoldCookCoverage(
                    curd_ids=curd_id,
                    unresolved_work=() if planner is None else planner.unresolved_work,
                )
                if curd_id
                else None
            ),
        )
    except (ContractValidationError, OSError, ValueError) as exc:
        raise fromargs.CliError(str(exc), exit_code=1) from exc
    return {
        "approval_path": str(path),
        "decision": approval.decision.value,
        "kind": approval.kind.value,
        "proposal_digest": approval.proposal_digest,
        "request_id": approval.request_id,
    }


def build_app() -> fromargs.App:
    return fromargs.App(
        "approve",
        help="Record the user's literal approval response for one spec.",
        help_formatter="plain",
        default_command=approve_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)
