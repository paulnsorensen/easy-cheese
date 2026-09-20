"""Fan remediation orchestrator (mini-spec Sec6, Sec7, Sec9, Sec11, Sec12).

`run_fan` owns wave scheduling, initial-state creation, per-scope state
persistence, resume cursors, remediation routing, and blocked-dependency
propagation. It drives a typed dispatch seam -- a Cook worker, an Age reviewer,
and a Cure worker -- and never counts Cure passes or reads a phase from prose;
the pure decision core owns every transition.

Per curd, after a passing Cook worker the orchestrator creates the initial
``awaiting_review`` state and loops ``Age -> decision -> (Cure -> decision)``
until the scope is clean, stalled, or blocked. After every selected curd passes
and the caller has no partial coverage, it runs the same loop once more for the
post-merge scope. Publication is refused unless the post-merge review is clean.

Resume is cursor-driven: a scope with a published state reloads it and continues
from its persisted cursor. A crash after an accepted Cure republishes
``awaiting_review``, so resume dispatches Age and never repeats the Cure.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal

import attrs

from easy_cheese_schemas import (
    ArtifactRef,
    ContractVersion,
    CriterionDisposition,
    CriterionResult,
    CurdDisposition,
    CurdPlan,
    CurdResult,
    RemediationCureObservation,
    RemediationCursor,
    RemediationDisposition,
    RemediationScopeKey,
    RemediationScopeKind,
    RemediationState,
    ReviewResult,
    SemanticCurd,
    SourceCurdRef,
    SourcePlanRef,
    canonical_bytes,
    supported_version_for,
)

from easy_cheese.shared.fanout.remediation import decide_cure, decide_review
from easy_cheese.shared.fanout.remediation_store import (
    StateStoreError,
    initial_state,
    load_state,
    publish_state,
    scope_state_path,
)
from easy_cheese.shared.fanout.scheduler import schedule_wave
from easy_cheese.shared.publication import atomic_write

NextStep = Literal["done", "press", "mold"]
POSTMERGE_SCOPE_ID = "postmerge"


# Dispatch seam the orchestrator owns. Each worker is called positionally.
# CookWorker: implement one curd and return its typed CurdResult.
CookWorker = Callable[[SemanticCurd], CurdResult]
# AgeReviewer: review the current scope diff at (scope, review_round).
AgeReviewer = Callable[[RemediationScopeKey, int], ReviewResult]
# CureWorker: apply (scope, locked_selection, cure_round) and report the result.
CureWorker = Callable[
    [RemediationScopeKey, tuple[str, ...], int], RemediationCureObservation
]


@attrs.frozen
class FanContext:
    """Everything `run_fan` needs beyond the plan: identity, root, and dispatch."""

    run_id: str
    artifact_directory: Path
    cook: CookWorker
    age: AgeReviewer
    cure: CureWorker


@attrs.frozen
class FanExecutionOutcome:
    """The aggregate result of one fan run.

    ``results`` is one CurdResult per in-scope curd. ``scope_states`` maps each
    curd id (and ``postmerge``) to its final remediation state. ``next_step`` is
    the top-level Cook handoff verdict: ``done`` only when every curd and the
    post-merge review are clean, ``mold`` when a remediation request exists or
    work is incomplete, and ``press`` when curds are clean but no post-merge
    review ran (a partial-coverage run). ``remediation_scopes`` names every
    scope that stalled and needs Mold.
    """

    results: tuple[CurdResult, ...]
    scope_states: Mapping[str, RemediationState]
    postmerge_state: RemediationState | None
    next_step: NextStep
    remediation_scopes: tuple[str, ...]


def _plan_ref(plan: CurdPlan) -> SourcePlanRef:
    return SourcePlanRef(plan_id=plan.plan_id, revision=plan.revision, digest=plan.digest)


def _curd_scope(run_id: str, plan: CurdPlan, curd_id: str) -> RemediationScopeKey:
    return RemediationScopeKey(
        run_id=run_id,
        source_plan_ref=_plan_ref(plan),
        scope_kind=RemediationScopeKind.CURD,
        scope_id=curd_id,
    )


def _postmerge_scope(run_id: str, plan: CurdPlan) -> RemediationScopeKey:
    return RemediationScopeKey(
        run_id=run_id,
        source_plan_ref=_plan_ref(plan),
        scope_kind=RemediationScopeKind.POSTMERGE,
        scope_id=POSTMERGE_SCOPE_ID,
    )


def _persist_ref(
    context: FanContext, name: str, role: str, contract: object
) -> ArtifactRef:
    """Persist an agent artifact and build a host-owned reference to it."""
    raw = canonical_bytes(contract)
    path = Path(context.artifact_directory) / "remediation" / context.run_id / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, raw)
    return ArtifactRef(
        artifact_id=name,
        role=role,
        uri=path.resolve().as_uri(),
        digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        size_bytes=len(raw),
        media_type="application/json",
    )


def _drive_scope(
    scope: RemediationScopeKey, state_id: str, context: FanContext
) -> RemediationState:
    """Run one scope's Age/Cure remediation loop to a terminal cursor.

    Reloads a published state on resume; otherwise publishes the initial
    ``awaiting_review`` state. Every transition is published before the next
    dispatch, so a crash resumes from the persisted cursor.
    """
    path = scope_state_path(context.artifact_directory, scope)
    if path.exists():
        state = load_state(path)
        # AC-14: a resumed state whose plan identity, digest, scope kind, or
        # scope id no longer matches the current plan stops before dispatch.
        if state.scope != scope:
            raise StateStoreError(
                f"resumed scope {state.scope} does not match current plan scope {scope}"
            )
    else:
        state = publish_state(path, initial_state(scope, state_id=state_id))
    while state.cursor is not RemediationCursor.TERMINAL:
        this_round = len(state.receipts) + 1
        if state.cursor is RemediationCursor.AWAITING_REVIEW:
            review = context.age(scope, this_round)
            review_ref = _persist_ref(
                context, f"{scope.scope_id}-review-{this_round}", "review", review
            )
            state, _verdict = decide_review(state, review, review_ref)
        else:
            observation = context.cure(scope, state.locked_selection, this_round)
            cure_ref = _persist_ref(
                context, f"{scope.scope_id}-cure-{this_round}", "cure-result", observation
            )
            state, _verdict = decide_cure(
                state,
                cure_ref,
                observation.applied_finding_keys,
                observation.deferred_finding_keys,
                observation.gate_evidence,
                observation.touched_paths,
                new_gate_failures=bool(observation.new_gate_failures),
            )
        state = publish_state(path, state)
    return state


def _blocked_result(
    plan: CurdPlan, curd: SemanticCurd, *, reason: str, unresolved: tuple[str, ...]
) -> CurdResult:
    rows = tuple(
        CriterionResult(
            criterion_id=criterion.criterion_id,
            disposition=CriterionDisposition.BLOCKED,
            reason=reason,
        )
        for criterion in curd.criteria
    )
    version = supported_version_for(CurdResult)
    assert isinstance(version, ContractVersion)
    return CurdResult(
        contract_version=version,
        result_id=f"{curd.curd_id}-result",
        source_plan_ref=_plan_ref(plan),
        source_curd_ref=SourceCurdRef(curd_id=curd.curd_id, digest=plan.digest),
        disposition=CurdDisposition.BLOCKED,
        expected_criterion_ids=tuple(c.criterion_id for c in curd.criteria),
        criterion_results=rows,
        unresolved_work=unresolved,
    )


def _result_after_remediation(
    plan: CurdPlan, curd: SemanticCurd, cook_result: CurdResult, final: RemediationState
) -> CurdResult:
    """Map a curd's terminal remediation disposition onto its CurdResult.

    A clean scope keeps the passing Cook result. A stalled or blocked scope
    becomes a blocked CurdResult naming the deterministic stop reason.
    """
    if final.disposition is RemediationDisposition.CLEAN:
        return cook_result
    reason = _stop_reason(final) or f"remediation {final.disposition.value}"
    return _blocked_result(plan, curd, reason=reason, unresolved=(reason,))


def _stop_reason(state: RemediationState) -> str | None:
    return state.receipts[-1].stop_reason if state.receipts else None


def run_fan(
    plan: CurdPlan,
    context: FanContext,
    *,
    selected: Sequence[str] | None = None,
    results: Mapping[str, CurdResult] | None = None,
) -> FanExecutionOutcome:
    """Execute `plan` through the progress-aware fan remediation state machine.

    `selected` restricts execution to a dependency-closed coverage subset.
    `results` seeds already-recorded CurdResults for a resume; the orchestrator
    dispatches only incomplete scopes.
    """
    curds = {curd.curd_id: curd for curd in plan.curds}
    recorded: dict[str, CurdResult] = dict(results or {})
    scope_states: dict[str, RemediationState] = {}
    remediation_scopes: list[str] = []

    while True:
        decision = schedule_wave(plan, recorded, selected=selected)
        if decision.complete:
            break
        for blocked in decision.blocked:
            curd = curds[blocked.curd_id]
            reason = "dependency did not pass: " + ", ".join(blocked.blocked_by)
            recorded[blocked.curd_id] = _blocked_result(
                plan, curd, reason=reason, unresolved=blocked.blocked_by
            )
        if not decision.ready:
            # Only blocked curds remained this wave; loop to propagate them.
            if decision.blocked:
                continue
            break
        for curd_id in decision.ready:
            curd = curds[curd_id]
            cook_result = context.cook(curd)
            if cook_result.disposition is not CurdDisposition.PASSED:
                recorded[curd_id] = cook_result
                continue
            scope = _curd_scope(context.run_id, plan, curd_id)
            final = _drive_scope(scope, f"{curd_id}-state", context)
            scope_states[curd_id] = final
            if final.disposition is RemediationDisposition.STALLED:
                remediation_scopes.append(f"curd:{curd_id}")
            recorded[curd_id] = _result_after_remediation(
                plan, curd, cook_result, final
            )

    ordered_results = tuple(
        recorded[curd.curd_id]
        for curd in plan.curds
        if curd.curd_id in recorded
    )
    all_passed = bool(ordered_results) and all(
        result.disposition is CurdDisposition.PASSED for result in ordered_results
    )

    postmerge_state: RemediationState | None = None
    if all_passed and selected is None:
        postmerge_state = _drive_scope(
            _postmerge_scope(context.run_id, plan), "postmerge-state", context
        )
        scope_states[POSTMERGE_SCOPE_ID] = postmerge_state
        if postmerge_state.disposition is RemediationDisposition.STALLED:
            remediation_scopes.append(f"{POSTMERGE_SCOPE_ID}")

    next_step = _next_step(all_passed, postmerge_state, remediation_scopes)
    return FanExecutionOutcome(
        results=ordered_results,
        scope_states=scope_states,
        postmerge_state=postmerge_state,
        next_step=next_step,
        remediation_scopes=tuple(remediation_scopes),
    )


def _next_step(
    all_passed: bool,
    postmerge_state: RemediationState | None,
    remediation_scopes: Sequence[str],
) -> NextStep:
    if remediation_scopes:
        return "mold"
    if not all_passed:
        # Incomplete work never publishes and never presses (AC-12); route the
        # blocked curds to Mold for a replan.
        return "mold"
    if postmerge_state is None:
        # Curds are clean but no post-merge review ran (partial coverage).
        return "press"
    if postmerge_state.disposition is RemediationDisposition.CLEAN:
        return "done"
    # A non-clean post-merge review refuses publication (AC-10).
    return "mold"
