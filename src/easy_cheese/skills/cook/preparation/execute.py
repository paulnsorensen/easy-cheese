"""Execution of one bound spec and plan."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import attrs

from easy_cheese_schemas import ArtifactRef, CurdDisposition, CurdPlan, CurdResult, EvidenceRef, RemediationState, validate_contract, supported_version_for, SourcePlanRef, canonical_bytes
from easy_cheese_schemas.mold_cook import MoldCookCoverage
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared import workflow
from easy_cheese.shared.artifacts import resolve_verified_bytes
from easy_cheese.shared.wheypoint.canonical import digest_bytes
from easy_cheese.shared.fanout.mode import select_mode
from easy_cheese.shared.mold_cook_handoff import validate_bound_execution
from easy_cheese.shared.remediation_artifacts import (
    REMEDIATION_STATE_ROLE,
    build_artifact_ref,
    contained_path,
    path_component,
)
from easy_cheese.shared.fanout.remediation_store import scope_state_path
from easy_cheese.shared.fanout.run_fan import PressDispatcher

from .fan_execute import execute_fan
from ._types import CookExecutionOutcome


def _require_valid_artifact_ids(template: ArtifactRef, artifact_ids: Sequence[str]) -> None:
    """Raise when ArtifactRef validation rejects any derived artifact id."""
    for artifact_id in artifact_ids:
        _ = attrs.evolve(template, artifact_id=artifact_id)


def execute_bound_plan(
    *,
    request_id: str,
    spec_ref: ArtifactRef,
    planner_result_ref: ArtifactRef,
    plan_ref: ArtifactRef,
    coverage: MoldCookCoverage,
    artifact_root: str | Path,
    repository_root: str | Path = ".",
    dispatch_writer: workflow.WriterDispatch,
    dispatch_review: workflow.ReviewDispatch,
    dispatch_diagnosis: workflow.DiagnosisDispatch,
    dispatch_press: PressDispatcher | None = None,
    evidence: Mapping[str, EvidenceRef] | None = None,
    runner_authorization_ref: ArtifactRef | None = None,
    runner_response_ref: ArtifactRef | None = None,
    setup_evidence_refs: Sequence[ArtifactRef] = (),
) -> CookExecutionOutcome:
    """Execute the selected, validated plan without a handoff envelope."""
    resolved_artifact_root = Path(artifact_root).resolve()
    plan = validate_bound_execution(
        spec_ref=spec_ref,
        planner_result_ref=planner_result_ref,
        plan_ref=plan_ref,
        coverage=coverage,
        artifact_root=resolved_artifact_root,
        runner_authorization_ref=runner_authorization_ref,
        runner_response_ref=runner_response_ref,
        setup_evidence_refs=setup_evidence_refs,
    )
    selected = tuple(coverage.curd_ids)
    execution_id = f"{plan.plan_id}-{request_id}"
    _require_valid_artifact_ids(
        plan_ref,
        (
            request_id,
            execution_id,
            f"{request_id}/execution-outcome",
            *(f"{request_id}/result/{curd_id}" for curd_id in selected),
        ),
    )
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
    ) and not coverage.unresolved_work and set(completed) == set(selected)
    result_refs = tuple(
        persist_value(resolved_artifact_root, result, artifact_id=f"{request_id}/result/{result.source_curd_ref.curd_id}", role="curd-result", schema_uri=result.contract_version.schema_uri)
        for result in execution_results[1]
    )
    outcome = CookExecutionOutcome(
        request_id=request_id,
        planner_result_ref=planner_result_ref,
        plan_ref=plan_ref,
        coverage=coverage,
        completed_curds=completed,
        remainder=coverage.unresolved_work,
        whole_task_complete=whole_task_complete,
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
        artifact_id=f"{request_id}/execution-outcome",
        role="execution_outcome",
        schema_uri=None,
    )
    return attrs.evolve(outcome, outcome_ref=outcome_ref)


def persist_value(
    root: Path,
    value: object,
    *,
    artifact_id: str,
    role: str,
    schema_uri: str | None,
) -> ArtifactRef:
    content = canonical_bytes(value)
    digest = digest_bytes(content)
    reference = ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=root.as_uri(),
        digest=digest,
        size_bytes=len(content),
        media_type="application/json",
        schema_uri=schema_uri,
    )
    retained = resolve_verified_bytes(reference, content, "application/json", root)
    return attrs.evolve(reference, uri=Path(retained.path).as_uri())


def _outcome_payload(outcome: CookExecutionOutcome) -> dict[str, object]:
    """Project the persisted execution outcome from the returned outcome."""
    return {
        "request_id": outcome.request_id,
        "planner_result_ref": outcome.planner_result_ref,
        "plan_ref": outcome.plan_ref,
        "coverage": outcome.coverage,
        "completed_curds": outcome.completed_curds,
        "remainder": outcome.remainder,
        "whole_task_complete": outcome.whole_task_complete,
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
