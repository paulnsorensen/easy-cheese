"""Execution of one accepted canonical Mold-to-Cook handoff."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import attrs

from easy_cheese_schemas import ArtifactRef, CurdDisposition, CurdPlan, CurdResult, EvidenceRef, RemediationState, validate_contract, supported_version_for, SourcePlanRef, canonical_bytes
from easy_cheese_schemas.mold_cook import (
    CookPreparationOutcome,
    CookPreparationResult,
    MoldCookHandoff,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared import workflow
from easy_cheese.shared.fanout.mode import select_mode
from easy_cheese.shared.mold_cook_handoff import accept_mold_cook_handoff
from easy_cheese.shared.remediation_artifacts import (
    REMEDIATION_STATE_ROLE,
    build_artifact_ref,
    contained_path,
    path_component,
)
from easy_cheese.shared.fanout.remediation_store import scope_state_path
from easy_cheese.shared.fanout.run_fan import PressDispatcher

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
    dispatch_press: PressDispatcher | None = None,
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
    execution_id = f"{plan.plan_id}-{handoff.request_id}"
    # Only a passed result for a selected curd is reusable. Every other
    # selected curd dispatches again.
    recorded = _load_execution_results(resolved_artifact_root, execution_id, plan)
    reusable = {
        curd_id: recorded[curd_id]
        for curd_id in selected
        if curd_id in recorded and recorded[curd_id].disposition is CurdDisposition.PASSED
    }
    fan_outcome = None
    remediation_state_refs: tuple[ArtifactRef, ...] = ()
    if select_mode(plan.curds) == "parallel" or any(curd.dependencies for curd in plan.curds):
        # The fan journal owns the execution record and pins its digest.
        fan_outcome = execute_fan(
            plan,
            repository_root=repository_root,
            artifact_directory=resolved_artifact_root,
            dispatch_writer=dispatch_writer,
            dispatch_review=dispatch_review,
            dispatch_diagnosis=dispatch_diagnosis,
            evidence=evidence,
            selected=selected,
            execution_id=execution_id,
            dispatch_press=dispatch_press,
            results=reusable,
        )
        execution_results: workflow.ExecutionResults = ((), fan_outcome.results)
        remediation_state_refs = tuple(
            _state_ref(resolved_artifact_root, state)
            for state in fan_outcome.scope_states.values()
        )
    else:
        pending = tuple(curd_id for curd_id in selected if curd_id not in reusable)
        branches: workflow.ExecutionResults = ((), ())
        if pending:
            branches = workflow.cook(
                plan,
                repository_root=repository_root,
                artifact_directory=resolved_artifact_root,
                dispatch_writer=dispatch_writer,
                dispatch_review=dispatch_review,
                dispatch_diagnosis=dispatch_diagnosis,
                curd_ids=pending,
                evidence=evidence,
            )
        fresh = {result.source_curd_ref.curd_id: result for result in branches[1]}
        merged = {**reusable, **fresh}
        execution_results = (
            branches[0],
            tuple(merged[curd_id] for curd_id in selected if curd_id in merged),
        )
        _persist_execution_results(resolved_artifact_root, execution_id, execution_results[1])
    completed = tuple(
        result.source_curd_ref.curd_id
        for result in execution_results[1]
        if result.disposition is CurdDisposition.PASSED
    )
    whole_task_complete = (
        fan_outcome is None or fan_outcome.next_step == "done"
    ) and not handoff.coverage.unresolved_work and set(completed) == set(selected)
    resumable_ref = handoff_ref or build_pointer_ref(
        pointer_path,
        request_id=handoff.request_id,
    )
    result_refs = tuple(
        persist_value(resolved_artifact_root, result, artifact_id=f"{handoff.request_id}/result/{result.source_curd_ref.curd_id}", role="curd-result", schema_uri=result.contract_version.schema_uri)
        for result in execution_results[1]
    )
    outcome = CookExecutionOutcome(
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
        fan_next_step=fan_outcome.next_step if fan_outcome else None,
        remediation_state_refs=remediation_state_refs,
        stop_evidence_refs=fan_outcome.stop_evidence_refs if fan_outcome else (),
        remediation_request_ref=fan_outcome.remediation_request_ref if fan_outcome else None,
        execution_result_refs=result_refs,
        scope_summaries=fan_outcome.scope_summaries if fan_outcome else {},
    )
    outcome_ref = persist_value(
        resolved_artifact_root,
        _outcome_payload(outcome),
        artifact_id=f"{handoff.request_id}/execution-outcome",
        role="execution_outcome",
        schema_uri=None,
    )
    return attrs.evolve(outcome, outcome_ref=outcome_ref)


def _outcome_payload(outcome: CookExecutionOutcome) -> dict[str, object]:
    """Project the persisted execution outcome from the returned outcome."""
    return {
        "request_id": outcome.request_id,
        "handoff_ref": outcome.handoff_ref,
        "planner_result_ref": outcome.planner_result_ref,
        "plan_ref": outcome.plan_ref,
        "coverage": outcome.coverage,
        "completed_curds": outcome.completed_curds,
        "remainder": outcome.remainder,
        "whole_task_complete": outcome.whole_task_complete,
        "resumable_ref": outcome.resumable_ref,
        "fan_next_step": outcome.fan_next_step,
        "remediation_state_refs": outcome.remediation_state_refs,
        "stop_evidence_refs": outcome.stop_evidence_refs,
        "remediation_request_ref": outcome.remediation_request_ref,
        "execution_result_refs": outcome.execution_result_refs,
        "scope_summaries": {
            scope_id: {
                "rounds": summary.rounds,
                "initial_debt": summary.initial_debt,
                "best_debt": summary.best_debt,
                "final_debt": summary.final_debt,
                "applied_count": summary.applied_count,
                "deferred_count": summary.deferred_count,
                "result": summary.result,
            }
            for scope_id, summary in outcome.scope_summaries.items()
        },
    }


def _execution_record_path(root: Path, execution_id: str) -> Path:
    resolved_root = root.resolve()
    return contained_path(
        resolved_root,
        resolved_root / "execution" / f"{path_component(execution_id)}.json",
    )


def _persist_execution_results(root: Path, execution_id: str, results: tuple[CurdResult, ...]) -> None:
    from easy_cheese.shared.publication import atomic_write
    path = _execution_record_path(root, execution_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, canonical_bytes({"request_id": execution_id, "results": list(results)}))


def _load_execution_results(root: Path, execution_id: str, plan: CurdPlan) -> dict[str, CurdResult]:
    path = _execution_record_path(root, execution_id)
    if not path.exists():
        return {}
    try:
        payload = cast(object, json.loads(path.read_text()))
        if not isinstance(payload, dict):
            raise ValueError("execution results must be an object")
        raw_results = cast(dict[str, object], payload).get("results")
        if not isinstance(raw_results, list):
            raise ValueError("execution results must be a list")
        results: dict[str, CurdResult] = {}
        version = supported_version_for(CurdResult)
        expected = SourcePlanRef(plan.plan_id, plan.revision, plan.digest)
        for value in cast(list[object], raw_results):
            encoded = json.dumps(value, sort_keys=True).encode()
            result = cast(CurdResult, validate_contract(encoded, CurdResult, version).value)
            if result.source_plan_ref != expected:
                raise ContractValidationError("cached result belongs to another plan")
            results[result.source_curd_ref.curd_id] = result
        return results
    except (OSError, KeyError, TypeError, ValueError, ContractValidationError) as error:
        raise ContractValidationError(f"invalid persisted execution results: {error}") from error


def _state_ref(root: Path, state: RemediationState) -> ArtifactRef:
    scope = state.scope
    path = scope_state_path(root, scope)
    raw = path.read_bytes()
    return build_artifact_ref(
        path,
        raw,
        artifact_id=(
            f"{scope.run_id}/{scope.scope_kind.value}/{scope.scope_id}/state"
        ),
        role=REMEDIATION_STATE_ROLE,
    )
