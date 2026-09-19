"""Acceptance of one canonical Mold-to-Cook handoff pointer."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import attrs

from easy_cheese_schemas import (
    ArtifactRef,
    CurdPlan,
    require_contract_version,
)
from easy_cheese_schemas.mold_cook import (
    CookPreparationResult,
    CookSetupAuthorization,
    MoldCookApproval,
    MoldCookHandoff,
)
from easy_cheese.shared.mold_cook_handoff import accept_mold_cook_handoff

from ._types import (
    ClassifiedCookInput,
    CookEvidenceError,
    CookPreparationRequest,
    PreparationFailure,
    SetupEvidence,
)
from .evidence import load_contract
from .legacy import read_pointer
from .outcomes import build_pointer_ref, publish_handoff, ready_result
from .results import validate_preparation_result
from .setup import apply_runner_setup, validate_handoff_authority


def resolve_canonical_pointer(
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
    pointer, refs = read_pointer(source)
    expected_schema = require_contract_version(MoldCookHandoff).schema_uri
    if pointer.payload.schema_uri != expected_schema:
        raise PreparationFailure(
            "unsupported-pointer-schema",
            f"pointer payload schema {pointer.payload.schema_uri!r} is not supported by Cook",
            path=str(source.path),
        )
    assert source.path is not None
    pointer_root = request.artifact_root.resolve()
    if not source.path.resolve().is_relative_to(pointer_root):
        raise PreparationFailure(
            "pointer-outside-artifact-root",
            f"canonical pointer is outside artifact root {str(pointer_root)!r}",
            path=str(source.path),
        )
    accepted = accept_mold_cook_handoff(
        source.path,
        artifact_root=pointer_root,
    )
    # `accept_mold_cook_handoff` already ran the shared deep validator under
    # `pointer_root`; only the setup authority Cook itself owns is left.
    handoff = cast(MoldCookHandoff, accepted.canonical.value)
    validate_handoff_authority(handoff, request=request)
    pointer_ref = build_pointer_ref(
        source.path, request_id=request.request_id, raw=source.snapshot
    )
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
        return ready_result(request, source, refs, pointer_ref, handoff.coverage)
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
    plan = load_contract(handoff.plan_ref, CurdPlan, pointer_root)
    assert isinstance(plan, CurdPlan)
    authority_request = attrs.evolve(request, request_id=handoff.request_id)
    applied = apply_runner_setup(
        request,
        source,
        refs,
        authority_request=authority_request,
        runner_approval=runner_approval,
        setup_evidence=setup_evidence,
        spec_ref=handoff.spec_ref,
        coverage=handoff.coverage,
        plan=plan,
        plan_ref=handoff.plan_ref,
    )
    if isinstance(applied, CookPreparationResult):
        return applied
    handoff_ref = publish_handoff(
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
        ready_result(request, source, refs, handoff_ref, handoff.coverage)
    )
