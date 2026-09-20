"""The one ingress that still reads a historical CurdPlan pointer."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

import attrs

from easy_cheese_schemas import (
    CURD_PLAN_SCHEMA_URI,
    ArtifactRef,
    CurdPlan,
    HandoffPointer,
    PlannerDisposition,
    PlannerResult,
    require_contract_version,
    validate_contract,
)
from easy_cheese_schemas.compat import check_adapter_sunsets
from easy_cheese_schemas.mold_cook import (
    CookPreparationResult,
    CookRequirementKind,
    CookUnmetRequirement,
    MoldCookInputKind,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_artifact,
)
from easy_cheese.shared.mold_cook_handoff import evaluate_mold_cook_spec

from ._types import (
    ClassifiedCookInput,
    CookPreparationRequest,
    LegacyPlanMigration,
    PreparationFailure,
    ResolvedPreparationSource,
)
from .evidence import persist_value, read_path, resolve_ref
from .outcomes import hold_result
from .results import validate_preparation_result
from .spec import bound_spec_ref


def pointer_artifact_root(pointer_path: Path) -> Path:
    resolved = pointer_path.resolve()
    if resolved.parent.name == "pointers":
        return resolved.parent.parent
    return resolved.parent


def read_pointer(
    source: ClassifiedCookInput,
) -> tuple[HandoffPointer, list[ArtifactRef]]:
    if source.path is None:
        raise PreparationFailure(
            "missing-pointer", "canonical pointer input must name a file"
        )
    pointer_raw = (
        source.snapshot if source.snapshot is not None else read_path(source.path)
    )
    try:
        pointer = validate_contract(
            pointer_raw, HandoffPointer, require_contract_version(HandoffPointer)
        ).value
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise PreparationFailure(
            "invalid-pointer", str(exc), path=str(source.path)
        ) from exc
    assert isinstance(pointer, HandoffPointer)
    refs = [pointer.payload]
    if pointer.normalization_receipt is not None:
        refs.append(pointer.normalization_receipt)
    return pointer, refs


def legacy_plan(
    source: ClassifiedCookInput,
    *,
    artifact_root: Path,
) -> LegacyPlanMigration | None:
    if source.path is None:
        return None
    pointer, _ = read_pointer(source)
    if pointer.payload.schema_uri != CURD_PLAN_SCHEMA_URI:
        return None
    try:
        root = pointer_artifact_root(source.path)
        resolved = resolve_artifact(
            pointer.payload,
            repository_root=root,
            artifact_directory=artifact_root,
            allowed_local_root=root,
        )
        canonical = validate_contract(
            resolved.content,
            CurdPlan,
            require_contract_version(CurdPlan),
        )
        if pointer.normalization_receipt is not None:
            _ = resolve_artifact(
                attrs.evolve(pointer.normalization_receipt, schema_uri=None),
                repository_root=root,
                artifact_directory=artifact_root,
                allowed_local_root=root,
            )
    except (
        ArtifactDigestMismatchError,
        ArtifactResolutionError,
        ContractValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise PreparationFailure(
            "invalid-pointer", str(exc), path=str(source.path)
        ) from exc
    plan = cast(CurdPlan, canonical.value)
    return LegacyPlanMigration(
        plan=plan,
        plan_ref=attrs.evolve(pointer.payload, role="curd_plan"),
        normalization_receipt_ref=pointer.normalization_receipt,
    )


def adopt_legacy_plan(
    legacy: LegacyPlanMigration,
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
) -> ResolvedPreparationSource | CookPreparationResult:
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
            hold_result(
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
    spec_ref, bound_objective = bound_spec_ref(spec_binding, request=request)
    processing_source = ClassifiedCookInput(
        MoldCookInputKind.TASK,
        bound_objective,
    )
    readiness = evaluate_mold_cook_spec(
        resolve_ref(spec_ref, artifacts),
        spec_ref=spec_ref,
    )
    planner_value = PlannerResult(
        contract_version=require_contract_version(PlannerResult),
        request_id=request.request_id,
        disposition=PlannerDisposition.COMPLETE,
        plan=legacy.plan,
    )
    planner_ref = persist_value(
        artifacts,
        planner_value,
        artifact_id=f"{request.request_id}/planner-result",
        role="planner_result",
        schema_uri=require_contract_version(PlannerResult).schema_uri,
    )
    refs.append(planner_ref)
    return ResolvedPreparationSource(
        processing_source=processing_source,
        planner_value=planner_value,
        planner_ref=planner_ref,
        plan_ref=legacy.plan_ref,
        spec_ref=spec_ref,
        readiness=readiness,
        objective=objective,
        legacy_mode=True,
    )
