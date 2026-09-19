"""Execution of one accepted canonical Mold-to-Cook handoff."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from easy_cheese_schemas import ArtifactRef, CurdPlan, EvidenceRef, RemediationState
from easy_cheese_schemas.mold_cook import (
    CookPreparationOutcome,
    CookPreparationResult,
    MoldCookHandoff,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared import workflow
from easy_cheese.shared.mold_cook_handoff import accept_mold_cook_handoff
from easy_cheese.shared.fanout.remediation_store import scope_state_path

from .fan_execute import execute_fan

from ._types import (
    ClassifiedCookInput,
    CookExecutionOutcome,
    CookPreparationRequest,
)
from .evidence import load_contract, local_path_for, persist_value
from .legacy import pointer_artifact_root
from .outcomes import build_pointer_ref
from .results import validate_preparation_result
from .setup import validate_handoff_authority


def execute_accepted_handoff(
    pointer_source: CookPreparationResult | ArtifactRef | str | Path,
    *,
    artifact_root: str | Path | None = None,
    repository_root: str | Path = ".",
    dispatch_writer: workflow.WriterDispatch,
    dispatch_review: workflow.ReviewDispatch,
    dispatch_diagnosis: workflow.DiagnosisDispatch,
    dispatch_press: workflow.PressDispatch | None = None,
    evidence: Mapping[str, EvidenceRef] | None = None,
) -> CookExecutionOutcome:
    """Accept one canonical pointer and execute its exact approved coverage."""

    # The configured root is the containment root: a caller-supplied pointer
    # URI names a path inside it and never defines it.
    supplied_root = Path(artifact_root).resolve() if artifact_root is not None else None
    if isinstance(pointer_source, CookPreparationResult):
        prepared = validate_preparation_result(pointer_source)
        if prepared.outcome is not CookPreparationOutcome.READY:
            raise ContractValidationError(
                "execution requires a READY preparation result"
            )
        if prepared.handoff_ref is None:
            raise ContractValidationError("READY preparation has no handoff pointer")
        handoff_ref = prepared.handoff_ref
        pointer_path = local_path_for(handoff_ref.uri, supplied_root)
    elif isinstance(pointer_source, ArtifactRef):
        handoff_ref = pointer_source
        pointer_path = local_path_for(pointer_source.uri, supplied_root)
    else:
        pointer_path = Path(pointer_source)
        handoff_ref = None
    resolved_artifact_root = (
        supplied_root
        if supplied_root is not None
        else pointer_artifact_root(pointer_path)
    )
    if not pointer_path.resolve().is_relative_to(resolved_artifact_root):
        raise ContractValidationError(
            "canonical pointer is outside artifact root "
            + repr(str(resolved_artifact_root))
        )
    accepted = accept_mold_cook_handoff(
        pointer_path,
        artifact_root=resolved_artifact_root,
    )
    handoff = cast(MoldCookHandoff, accepted.canonical.value)
    request = CookPreparationRequest(
        request_id=handoff.request_id,
        source=ClassifiedCookInput(
            MoldCookInputKind.CANONICAL_POINTER,
            str(pointer_path),
            pointer_path,
        ),
        repository_root=Path(repository_root).resolve(),
        artifact_root=resolved_artifact_root,
        mode=handoff.mode,
    )
    validate_handoff_authority(handoff, request=request)
    if handoff.mode is not MoldCookMode.FULL:
        raise ContractValidationError(
            "workflow execution requires a Full handoff with an approved plan"
        )
    if handoff.planner_result_ref is None or handoff.plan_ref is None:
        raise ContractValidationError(
            "Full handoff is missing its canonical planner result or plan"
        )
    plan_value = load_contract(
        handoff.plan_ref,
        CurdPlan,
        resolved_artifact_root,
    )
    plan = cast(CurdPlan, plan_value)
    # `accept_mold_cook_handoff` already proved the planner result and the plan
    # are attached and that the coverage is a dependency-closed plan subset.
    selected = tuple(handoff.coverage.curd_ids)
    fan_outcome = None
    remediation_state_refs: tuple[ArtifactRef, ...] = ()
    fan_topology = len(plan.curds) > 1 or any(curd.dependencies for curd in plan.curds)
    if fan_topology:
        fan_outcome = execute_fan(
            plan,
            repository_root=repository_root,
            artifact_directory=resolved_artifact_root,
            dispatch_writer=dispatch_writer,
            dispatch_review=dispatch_review,
            dispatch_diagnosis=dispatch_diagnosis,
            evidence=evidence,
            selected=selected,
            execution_id=f"{plan.plan_id}-{handoff.request_id}",
            dispatch_press=dispatch_press,
        )
        execution_results = ((), fan_outcome.results)
        remediation_state_refs = tuple(
            _state_ref(resolved_artifact_root, state)
            for state in fan_outcome.scope_states.values()
        )
    else:
        execution_results = workflow.cook(
            plan,
            repository_root=repository_root,
            artifact_directory=resolved_artifact_root,
            dispatch_writer=dispatch_writer,
            dispatch_review=dispatch_review,
            dispatch_diagnosis=dispatch_diagnosis,
            curd_ids=selected,
            evidence=evidence,
        )
    completed = tuple(
        result.source_curd_ref.curd_id
        for result in execution_results[1]
        if getattr(result.disposition, "value", result.disposition) == "passed"
    )
    whole_task_complete = (
        fan_outcome is None or fan_outcome.next_step == "done"
    ) and not handoff.coverage.unresolved_work and set(completed) == set(selected)
    resumable_ref = handoff_ref or build_pointer_ref(
        pointer_path,
        request_id=handoff.request_id,
    )
    outcome_payload = {
        "request_id": handoff.request_id,
        "handoff_ref": resumable_ref,
        "planner_result_ref": handoff.planner_result_ref,
        "plan_ref": handoff.plan_ref,
        "coverage": handoff.coverage,
        "completed_curds": completed,
        "remainder": handoff.coverage.unresolved_work,
        "whole_task_complete": whole_task_complete,
        "resumable_ref": resumable_ref,
        "fan_next_step": fan_outcome.next_step if fan_outcome else None,
        "remediation_state_refs": remediation_state_refs,
    }
    outcome_ref = persist_value(
        resolved_artifact_root,
        outcome_payload,
        artifact_id=f"{handoff.request_id}/execution-outcome",
        role="execution_outcome",
        schema_uri=None,
    )
    return CookExecutionOutcome(
        request_id=handoff.request_id,
        handoff_ref=resumable_ref,
        planner_result_ref=handoff.planner_result_ref,
        plan_ref=handoff.plan_ref,
        coverage=handoff.coverage,
        completed_curds=completed,
        remainder=handoff.coverage.unresolved_work,
        whole_task_complete=whole_task_complete,
        resumable_ref=resumable_ref,
        execution_results=execution_results,
        outcome_ref=outcome_ref,
        fan_next_step=fan_outcome.next_step if fan_outcome else None,
        remediation_state_refs=remediation_state_refs,
    )



def _state_ref(root: Path, state: RemediationState) -> ArtifactRef:
    scope = state.scope
    path = scope_state_path(root, scope)
    raw = path.read_bytes()
    return ArtifactRef(
        artifact_id=f"{scope.run_id}/{scope.scope_id}/state",
        role="remediation_state",
        uri=path.resolve().as_uri(),
        digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        size_bytes=len(raw),
        media_type="application/json",
    )
