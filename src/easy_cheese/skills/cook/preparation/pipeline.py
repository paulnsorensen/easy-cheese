"""The preparation entry points that drive one round to a closed result."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import attrs

from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookPreparationResult,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared.mold_cook_handoff import dialogue_authorizes_execution

from ._types import (
    ClassifiedCookInput,
    CookEvidenceError,
    CookHoldClearance,
    CookInputError,
    PreparationEvidence,
    PreparationFailure,
)
from .classify import classify_input
from .evidence import local_path_for, request_metadata, resolve_ref
from .outcomes import hold_result, invalid_result
from .plan_stages import (
    stage_plan_approval,
    stage_plan_material,
    stage_planner_result,
    stage_runner_setup,
)
from .results import validate_preparation_result
from .sources import bind_previous_result, classify_request, resolve_preparation_source
from .stages import stage_scope_approval, stage_spec_binding


def prepare(
    source: str | Path | ClassifiedCookInput,
    *,
    request_id: str | None = None,
    repository_root: str | Path = ".",
    artifact_root: str | Path = ".cheese/cook",
    mode: MoldCookMode = MoldCookMode.FULL,
    explicit_kind: MoldCookInputKind | str | None = None,
    evidence: PreparationEvidence | None = None,
) -> CookPreparationResult:
    """Recompute one preparation outcome from host-owned evidence."""

    evidence = PreparationEvidence() if evidence is None else evidence
    ctx = classify_request(
        source,
        request_id=request_id,
        root=Path(repository_root).resolve(),
        artifacts=Path(artifact_root).resolve(),
        mode=MoldCookMode(mode),
        explicit_kind=explicit_kind,
        evidence=evidence,
    )
    if isinstance(ctx, CookPreparationResult):
        return ctx
    request = ctx.request
    classified = ctx.classified
    refs = ctx.refs
    try:
        ctx = bind_previous_result(ctx)
        if request.holds:
            return validate_preparation_result(
                hold_result(request, classified, refs, request.holds)
            )
        resolved = resolve_preparation_source(ctx)
        if isinstance(resolved, CookPreparationResult):
            return resolved
        spec = stage_spec_binding(ctx, resolved)
        if isinstance(spec, CookPreparationResult):
            return spec
        if (
            evidence.setup_authorization is not None
            or evidence.setup_evidence is not None
        ) and evidence.runner_approval is None:
            raise CookEvidenceError(
                "setup authority and evidence must be derived from runner approval"
            )
        scope_ref = stage_scope_approval(ctx, spec, resolved)
        if isinstance(scope_ref, CookPreparationResult):
            return scope_ref
        planner_value = stage_planner_result(ctx, spec, resolved, scope_ref)
        if isinstance(planner_value, CookPreparationResult):
            return planner_value
        material = stage_plan_material(ctx, spec, resolved, planner_value, scope_ref)
        if isinstance(material, CookPreparationResult):
            return material
        approved = stage_plan_approval(ctx, spec, planner_value, material, scope_ref)
        if isinstance(approved, CookPreparationResult):
            return approved
        return stage_runner_setup(ctx, spec, material, approved)
    except PreparationFailure as failure:
        return validate_preparation_result(
            invalid_result(request, classified, refs, failure)
        )
    except CookEvidenceError as failure:
        return validate_preparation_result(
            invalid_result(
                request,
                classified,
                refs,
                PreparationFailure("invalid-evidence", str(failure)),
            )
        )
    except (ContractValidationError, OSError, ValueError) as failure:
        return validate_preparation_result(
            invalid_result(request, classified, refs, failure)
        )
    except TypeError as failure:
        # A TypeError reaching here is a host defect, not bad user evidence;
        # the code keeps the two apart for whoever reads the result.
        return validate_preparation_result(
            invalid_result(
                request,
                classified,
                refs,
                PreparationFailure("internal-error", str(failure)),
            )
        )


def _validate_hold_clearance(clearance: CookHoldClearance, root: Path) -> None:
    if clearance.response_ref.role != "dialogue":
        raise CookEvidenceError("hold clearance must reference local dialogue")
    raw = resolve_ref(clearance.response_ref, root)
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
    evidence: PreparationEvidence | None = None,
) -> CookPreparationResult:
    supplied = PreparationEvidence() if evidence is None else evidence
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
        else local_path_for(request_ref.uri).parent
    )
    metadata = request_metadata(request_ref, request_root)
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
    clearance_ids = [item.hold_id for item in supplied.clearances]
    if len(clearance_ids) != len(set(clearance_ids)):
        raise CookEvidenceError("hold clearances contain duplicate hold IDs")
    previous_hold_ids = {item.hold_id for item in previous_result.holds}
    unknown_clearances = set(clearance_ids) - previous_hold_ids
    if unknown_clearances:
        raise CookEvidenceError(
            f"hold clearance names unknown holds: {sorted(unknown_clearances)}"
        )
    clear_by_id = {item.hold_id: item for item in supplied.clearances}
    for hold in previous_result.holds:
        clearance = clear_by_id.get(hold.hold_id)
        if clearance is None:
            retained_holds.append(hold)
            continue
        _validate_hold_clearance(clearance, artifacts)
    retained_ids = {item.hold_id for item in retained_holds}
    retained_holds.extend(
        hold for hold in supplied.holds if hold.hold_id not in retained_ids
    )
    spec_binding = supplied.spec_binding
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
        evidence=attrs.evolve(
            supplied,
            spec_binding=spec_binding,
            holds=tuple(retained_holds),
            previous=previous_result,
        ),
    )
