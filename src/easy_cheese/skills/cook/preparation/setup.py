"""Runner authorization and the bounded setup evidence Cook accepts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import attrs

from easy_cheese_schemas import (
    ArtifactRef,
    CurdPlan,
    canonical_digest,
    require_contract_version,
)
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    CookPreparationOutcome,
    CookPreparationResult,
    CookSetupAuthorization,
    MoldCookApproval,
    MoldCookApprovalKind,
    MoldCookCoverage,
    MoldCookHandoff,
)
from easy_cheese_schemas.validate import require_mapping, require_relative_path
from easy_cheese.shared.mold_cook_handoff import canonical_mold_cook_proposal
from easy_cheese.shared.wheypoint.canonical import digest_bytes

from ._types import (
    ClassifiedCookInput,
    CookEvidenceError,
    CookPreparationRequest,
    RunnerSetup,
    SetupEvidence,
    SetupExecutionFailed,
)
from .approval import approval_value, check_approval
from .evidence import is_regular_path, load_contract, read_path, resolve_ref
from .outcomes import hold_result
from .results import validate_preparation_result

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")


def _validate_setup(
    evidence: SetupEvidence | Mapping[str, object] | ArtifactRef | str | Path,
    *,
    authorization: CookSetupAuthorization,
    plan: CurdPlan,
    request: CookPreparationRequest,
) -> ArtifactRef:
    if isinstance(evidence, ArtifactRef):
        evidence_ref = evidence
        if evidence_ref.role != "setup_evidence":
            raise CookEvidenceError("setup evidence reference has the wrong role")
        raw = resolve_ref(evidence_ref, request.artifact_root)
    elif isinstance(evidence, (str, Path)):
        path = Path(evidence).expanduser().resolve()
        raw = read_path(path)
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
            schema_uri=None,
        )
    else:
        raise CookEvidenceError("setup evidence must be a durable host artifact")
    try:
        decoded = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CookEvidenceError("setup evidence is not valid JSON") from exc
    values = require_mapping(decoded, "setup evidence")
    parsed = SetupEvidence.from_mapping(values)
    if not parsed.environment_id.strip():
        raise CookEvidenceError("setup evidence environment_id must not be empty")
    if parsed.prerequisite_curd_id != authorization.prerequisite_curd_id:
        raise CookEvidenceError("setup evidence names a different prerequisite curd")
    if parsed.plan_digest != plan.digest:
        raise CookEvidenceError("setup evidence is stale for this plan")
    if parsed.authorization_digest != canonical_digest(authorization):
        raise CookEvidenceError("setup evidence is stale for this authorization")
    if parsed.runner_command not in authorization.allowed_commands:
        raise CookEvidenceError("setup command is outside approved commands")
    fixture = require_relative_path(parsed.fixture_path, "setup evidence fixture_path")
    allowed = tuple(
        require_relative_path(item, "setup authorization allowed_paths item")
        for item in authorization.allowed_paths
    )
    if not any(
        fixture == item or fixture.startswith(item.rstrip("/") + "/")
        for item in allowed
    ):
        raise CookEvidenceError("setup fixture path is outside approved paths")
    if not _DIGEST_RE.fullmatch(parsed.captured_output_digest):
        raise CookEvidenceError("setup output digest is invalid")
    output_path = request.artifact_root.resolve() / (
        f"sha256-{parsed.captured_output_digest.removeprefix('sha256:')}"
    )
    if not is_regular_path(output_path):
        raise CookEvidenceError("setup output was not retained by the host runner")
    if digest_bytes(read_path(output_path)) != parsed.captured_output_digest:
        raise CookEvidenceError("setup output digest does not match retained bytes")
    if parsed.exit_code != 0:
        raise SetupExecutionFailed("setup runner did not pass")
    return evidence_ref


def validate_handoff_authority(
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
    runner = load_contract(
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
    check_approval(
        runner,
        approval_ref=handoff.runner_approval_ref,
        request=request,
        spec_ref=handoff.spec_ref,
        expected=MoldCookApprovalKind.RUNNER,
        expected_proposal=expected_proposal,
    )
    if handoff.plan_ref is None:
        raise CookEvidenceError("setup evidence requires a materialized plan")
    plan = load_contract(handoff.plan_ref, CurdPlan, request.artifact_root)
    assert isinstance(plan, CurdPlan)
    for evidence_ref in handoff.setup_evidence_refs:
        _ = _validate_setup(
            evidence_ref,
            authorization=authorization,
            plan=plan,
            request=request,
        )


def apply_runner_setup(
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
    spec_ref: ArtifactRef,
    coverage: MoldCookCoverage,
    plan: CurdPlan,
    plan_ref: ArtifactRef,
) -> RunnerSetup | CookPreparationResult:
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
        runner, runner_ref = approval_value(
            runner_approval,
            request=authority_request,
        )
        authorization = runner.setup_authorization
        if authorization is None:
            raise CookEvidenceError("runner approval lacks setup authorization")
        runner_proposal = canonical_mold_cook_proposal(
            request_id=authority_request.request_id,
            kind=MoldCookApprovalKind.RUNNER,
            spec_digest=spec_ref.digest,
            coverage=coverage,
            setup_authorization=authorization,
        )
        check_approval(
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
                contract_version=require_contract_version(CookPreparationResult),
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
        except SetupExecutionFailed as exc:
            if isinstance(setup_evidence, ArtifactRef):
                refs.append(setup_evidence)
            return validate_preparation_result(
                hold_result(
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
    return RunnerSetup(
        runner_approval_ref=runner_handoff_ref,
        setup_evidence_refs=tuple(setup_refs),
    )
