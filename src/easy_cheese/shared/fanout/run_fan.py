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
from typing import Literal, cast

import attrs

from easy_cheese_schemas import (
    ArtifactRef,
    ContractVersion,
    EvidenceRef,
    EvidenceKind,
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
    PlannerRequest,
    PlannerRequestKind,
    ReviewDisposition,
    ReviewResult,
    SemanticCurd,
    SourceCurdRef,
    SourcePlanRef,
    canonical_bytes,
    supported_version_for,
)

from easy_cheese.shared.fanout.remediation import (
    PressGateResult,
    PressStopClassification,
    PressStopRecord,
    bind_event_identity,
)
from easy_cheese.shared.fanout.remediation_decision import apply_event
from easy_cheese.shared.fanout.remediation_store import (
    StateStoreError,
    initial_state,
    load_state,
    publish_state,
    scope_state_path,
)
from easy_cheese.shared.fanout.scheduler import schedule_wave
from easy_cheese.shared.publication import atomic_write

PressDispatcher = Callable[[RemediationScopeKey, int], PressGateResult]


def _normalize_press_result(value: PressGateResult) -> PressGateResult:
    if not value.baseline_id:
        raise ValueError("Press gate result requires a baseline identity")
    return value


NextStep = Literal["done", "press", "mold"]
POSTMERGE_SCOPE_ID = "postmerge"


@attrs.frozen
class RemediationEventContext:
    """Immutable host context passed to one downstream remediation dispatch."""

    scope: RemediationScopeKey
    state_id: str
    cursor: RemediationCursor
    round_number: int
    locked_selection: tuple[str, ...] = ()


@attrs.frozen
class ReviewDispatchOutcome:
    """Host-owned review result paired with the exact request digest."""

    result: ReviewResult
    request_digest: str


@attrs.frozen
class CureDispatchOutcome:
    """Host-owned Cure observation paired with the exact request digest."""

    observation: RemediationCureObservation
    request_digest: str


# Dispatch seam the orchestrator owns. Each worker receives immutable context.
CookWorker = Callable[[SemanticCurd], CurdResult]
AgeReviewer = Callable[[RemediationEventContext], ReviewDispatchOutcome]
CureWorker = Callable[[RemediationEventContext], CureDispatchOutcome]


@attrs.frozen
class ScopeRemediationSummary:
    """Deterministic remediation summary for one fan scope."""

    rounds: int  # noqa: V101
    initial_debt: int | None  # noqa: V101
    best_debt: int | None  # noqa: V101
    final_debt: int | None  # noqa: V101
    applied_count: int  # noqa: V101
    deferred_count: int  # noqa: V101
    result: str


@attrs.frozen
class FanContext:
    """Everything `run_fan` needs beyond the plan: identity, root, and dispatch."""

    run_id: str
    artifact_directory: Path
    cook: CookWorker
    age: AgeReviewer
    cure: CureWorker
    press: PressDispatcher | None = None
    result_sink: Callable[[CurdResult], None] | None = None
    checkpoint_sink: Callable[[], None] | None = None


@attrs.frozen
class FanExecutionOutcome:
    """The aggregate result of one fan run.

    ``results`` is one CurdResult per in-scope curd. ``scope_states`` maps each
    curd id (and ``postmerge``) to its final remediation state. ``next_step`` is
    the top-level Cook handoff verdict: ``done`` only when every curd and the
    post-merge review are clean, ``mold`` when coverage or remediation is
    incomplete, and ``press`` only for a complete clean run without post-merge.
    ``remediation_scopes`` names every scope that stalled and needs Mold.
    """

    results: tuple[CurdResult, ...]
    scope_states: Mapping[str, RemediationState]
    postmerge_state: RemediationState | None
    next_step: NextStep
    remediation_scopes: tuple[str, ...]
    stop_evidence_refs: tuple[ArtifactRef, ...] = ()
    remediation_request_ref: ArtifactRef | None = None
    scope_summaries: Mapping[str, ScopeRemediationSummary] = attrs.field(factory=lambda: cast(Mapping[str, ScopeRemediationSummary], {}))


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


def _path_component(value: str) -> str:
    """Encode opaque identifiers before using them as path components."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _contained_path(root: Path, target: Path) -> Path:
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    try:
        _ = resolved_target.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"remediation path escapes artifact root: {target}") from error
    return resolved_target


def _persist_ref(
    context: FanContext, name: str, role: str, contract: object
) -> ArtifactRef:
    """Persist an agent artifact and build a host-owned reference to it."""
    raw = canonical_bytes(contract)
    root = Path(context.artifact_directory).resolve()
    path = _contained_path(
        root,
        root / "remediation" / _path_component(context.run_id)
        / _path_component(role) / f"{_path_component(name)}.json",
    )
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

def _persist_press_stop(
    context: FanContext,
    scope: RemediationScopeKey,
    *,
    gate_round: int,
    baseline_id: str | None,
    classification: PressStopClassification,
    failure_reason: str,
    evidence: tuple[EvidenceRef, ...] = (),
) -> ArtifactRef:
    record = PressStopRecord(
        scope=scope,
        gate_round=gate_round,
        baseline_id=baseline_id,
        classification=classification,
        failure_reason=failure_reason[:512],
        evidence=evidence,
    )
    return _persist_ref(context, f"{scope.scope_id}-press-stop-{gate_round}", "press-stop", record)



def _fallback_request_digest(state: RemediationState, event: str) -> str:
    """Digest the host failure envelope when downstream dispatch cannot start."""
    raw = canonical_bytes(
        {
            "event": event,
            "scope": state.scope,
            "state_id": state.state_id,
            "cursor": state.cursor,
            "round_number": len(state.receipts) + 1,
        }
    )
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _dispatch_review(
    context: FanContext, state: RemediationState, round_number: int
) -> tuple[ReviewResult, str]:
    event = RemediationEventContext(
        scope=state.scope,
        state_id=state.state_id,
        cursor=state.cursor,
        round_number=round_number,
    )
    outcome = context.age(event)
    if type(outcome) is not ReviewDispatchOutcome:
        raise TypeError("Age callback must return ReviewDispatchOutcome")
    if outcome.result.event_identity is not None:
        raise ValueError("Age output must not author event identity")
    identity = bind_event_identity(state, outcome.request_digest, event="review")
    return attrs.evolve(outcome.result, event_identity=identity), outcome.request_digest


def _dispatch_cure(
    context: FanContext, state: RemediationState, round_number: int
) -> tuple[RemediationCureObservation, str]:
    event = RemediationEventContext(
        scope=state.scope,
        state_id=state.state_id,
        cursor=state.cursor,
        round_number=round_number,
        locked_selection=state.locked_selection,
    )
    outcome = context.cure(event)
    if type(outcome) is not CureDispatchOutcome:
        raise TypeError("Cure callback must return CureDispatchOutcome")
    if outcome.observation.event_identity is not None:
        raise ValueError("Cure output must not author event identity")
    identity = bind_event_identity(state, outcome.request_digest, event="cure")
    return attrs.evolve(outcome.observation, event_identity=identity), outcome.request_digest


def _drive_scope(
    scope: RemediationScopeKey,
    state_id: str,
    context: FanContext,
    *,
    postmerge: bool = False,
) -> RemediationState:
    """Run one scope's Age/Cure remediation loop to a terminal cursor.

    Reloads a published state on resume; otherwise publishes the initial
    ``awaiting_review`` state. Every transition is published before the next
    dispatch, so a crash resumes from the persisted cursor.
    """
    path = scope_state_path(context.artifact_directory, scope)
    initial_postmerge_gate_evidence: tuple[EvidenceRef, ...] = ()
    if path.exists():
        state = load_state(path)
        # AC-14: a resumed state whose plan identity, digest, scope kind, or
        # scope id no longer matches the current plan stops before dispatch.
        if state.scope != scope:
            raise StateStoreError(
                f"resumed scope {state.scope} does not match current plan scope {scope}"
            )
    else:
        state = initial_state(scope, state_id=state_id)
        if postmerge:
            if context.press is None:
                _ = _persist_press_stop(
                    context,
                    scope,
                    gate_round=1,
                    baseline_id=None,
                    classification=PressStopClassification.ABSENT,
                    failure_reason="initial Press gate is absent",
                )
                state = attrs.evolve(
                    state,
                    cursor=RemediationCursor.TERMINAL,
                    disposition=RemediationDisposition.BLOCKED,
                )
                return publish_state(path, state)
            try:
                gate = _normalize_press_result(context.press(scope, 1))
                initial_postmerge_gate_evidence = gate.evidence
                if not gate.passed or gate.new_failures:
                    _ = _persist_press_stop(
                        context,
                        scope,
                        gate_round=1,
                        baseline_id=gate.baseline_id,
                        classification=PressStopClassification.FAILED,
                        failure_reason="; ".join(gate.new_failures) or "initial Press gate failed",
                        evidence=gate.evidence,
                    )
                    state = attrs.evolve(
                        state,
                        cursor=RemediationCursor.TERMINAL,
                        disposition=RemediationDisposition.BLOCKED,
                    )
                    return publish_state(path, state)
            except Exception as error:
                state = attrs.evolve(
                    state,
                    cursor=RemediationCursor.TERMINAL,
                    disposition=RemediationDisposition.BLOCKED,
                )
                _ = _persist_press_stop(
                    context,
                    scope,
                    gate_round=1,
                    baseline_id=None,
                    classification=PressStopClassification.ERROR,
                    failure_reason=_failure_reason("project gate callback failed", error),
                )
                return publish_state(path, state)
        state = publish_state(path, state)
    while state.cursor is not RemediationCursor.TERMINAL:
        this_round = len(state.receipts) + 1
        if state.cursor is RemediationCursor.AWAITING_REVIEW:
            try:
                review, request_digest = _dispatch_review(context, state, this_round)
            except Exception as error:
                review = _blocked_review(scope, this_round, error)
                request_digest = _fallback_request_digest(state, "review")
                review = attrs.evolve(
                    review,
                    event_identity=bind_event_identity(
                        state, request_digest, event="review"
                    ),
                )
            review_ref = _persist_ref(
                context, f"{scope.scope_id}-review-{this_round}", "review", review
            )
            state, _verdict = apply_event(
                state,
                event="review",
                artifact_ref=review_ref,
                request_digest=request_digest,
                review=review,
                publish=lambda value: publish_state(path, value),
            )
        else:
            try:
                observation, request_digest = _dispatch_cure(context, state, this_round)
            except Exception as error:
                observation = _blocked_cure_observation(state.locked_selection, error)
                request_digest = _fallback_request_digest(state, "cure")
                observation = attrs.evolve(
                    observation,
                    event_identity=bind_event_identity(
                        state, request_digest, event="cure"
                    ),
                )
            if (
                context.press is not None
                and scope.scope_kind is RemediationScopeKind.POSTMERGE
            ):
                try:
                    gate = _normalize_press_result(context.press(scope, this_round))
                    observation = attrs.evolve(
                        observation,
                        gate_evidence=(
                            *initial_postmerge_gate_evidence,
                            *observation.gate_evidence,
                            *gate.evidence,
                        ),
                        new_gate_failures=(
                            *observation.new_gate_failures,
                            *gate.new_failures,
                            *(() if gate.passed else ("press-gate-failed",)),
                        ),
                    )
                except Exception as error:
                    observation = _blocked_cure_observation(
                        state.locked_selection, error
                    )
                    observation = attrs.evolve(
                        observation,
                        event_identity=bind_event_identity(
                            state, request_digest, event="cure"
                        ),
                    )
            cure_ref = _persist_ref(
                context, f"{scope.scope_id}-cure-{this_round}", "cure-result", observation
            )
            state, _verdict = apply_event(
                state,
                event="cure",
                artifact_ref=cure_ref,
                request_digest=request_digest,
                observation=observation,
                publish=lambda value: publish_state(path, value),
            )
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
    for curd_id in recorded:
        path = scope_state_path(
            context.artifact_directory, _curd_scope(context.run_id, plan, curd_id)
        )
        if path.exists():
            scope_states[curd_id] = load_state(path)
    remediation_scopes: list[str] = []
    for curd_id, state in tuple(scope_states.items()):
        if curd_id == POSTMERGE_SCOPE_ID:
            continue
        recorded_result = recorded.get(curd_id)
        if recorded_result is None or recorded_result.disposition is not CurdDisposition.PASSED:
            continue
        scope = _curd_scope(context.run_id, plan, curd_id)
        final = (
            _drive_scope(scope, f"{curd_id}-state", context)
            if state.cursor is not RemediationCursor.TERMINAL
            else state
        )
        scope_states[curd_id] = final
        recorded[curd_id] = _result_after_remediation(
            plan, curds[curd_id], recorded_result, final
        )

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
            if context.result_sink is not None:
                context.result_sink(recorded[blocked.curd_id])
            if context.checkpoint_sink is not None:
                context.checkpoint_sink()
        if not decision.ready:
            # Only blocked curds remained this wave; loop to propagate them.
            if decision.blocked:
                continue
            break
        for curd_id in decision.ready:
            curd = curds[curd_id]
            cook_result = context.cook(curd)
            if cook_result.disposition is not CurdDisposition.PASSED:
                scope = _curd_scope(context.run_id, plan, curd_id)
                blocked_state = attrs.evolve(
                    initial_state(scope, state_id=f"{curd_id}-state"),
                    cursor=RemediationCursor.TERMINAL,
                    disposition=RemediationDisposition.BLOCKED,
                )
                scope_states[curd_id] = publish_state(
                    scope_state_path(context.artifact_directory, scope), blocked_state
                )
                recorded[curd_id] = cook_result
                if context.result_sink is not None:
                    context.result_sink(cook_result)
                if context.checkpoint_sink is not None:
                    context.checkpoint_sink()
                continue
            scope = _curd_scope(context.run_id, plan, curd_id)
            final = _drive_scope(scope, f"{curd_id}-state", context)
            scope_states[curd_id] = final
            if final.disposition is RemediationDisposition.STALLED:
                remediation_scopes.append(f"curd:{curd_id}")
            recorded[curd_id] = _result_after_remediation(
                plan, curd, cook_result, final
            )
            if context.result_sink is not None:
                context.result_sink(recorded[curd_id])
            if context.checkpoint_sink is not None:
                context.checkpoint_sink()

    ordered_results = tuple(
        recorded[curd.curd_id]
        for curd in plan.curds
        if curd.curd_id in recorded
    )
    all_passed = bool(ordered_results) and all(
        result.disposition is CurdDisposition.PASSED for result in ordered_results
    )

    postmerge_state: RemediationState | None = None
    full_coverage = selected is None or set(selected) == set(curds)
    if all_passed and full_coverage:
        postmerge_state = _drive_scope(
            _postmerge_scope(context.run_id, plan),
            "postmerge-state",
            context,
            postmerge=True,
        )
        scope_states[POSTMERGE_SCOPE_ID] = postmerge_state
        if postmerge_state.disposition is RemediationDisposition.STALLED:
            remediation_scopes.append(f"{POSTMERGE_SCOPE_ID}")

    next_step = _next_step(
        all_passed, postmerge_state, remediation_scopes, full_coverage=full_coverage
    )
    stop_evidence_refs = _load_stop_evidence_refs(context)
    remediation_request_ref = None
    if next_step == "mold":
        evidence_refs = list(stop_evidence_refs)
        evidence_refs.extend(
            _scope_state_ref(context, state) for state in scope_states.values()
        )
        evidence_refs.extend(
            _persist_ref(
                context,
                f"result-{result.source_curd_ref.curd_id}",
                "curd-result",
                result,
            )
            for result in ordered_results
        )
        evidence = tuple(
            EvidenceRef(
                evidence_id=f"planner-evidence-{index}",
                kind=EvidenceKind.RUNTIME,
                artifact=ref,
                summary=f"fan remediation evidence: {ref.role}",
            )
            for index, ref in enumerate(evidence_refs, start=1)
        )
        if evidence:
            request_version = supported_version_for(PlannerRequest)
            if request_version is None:
                raise RuntimeError("planner request has no supported version")
            request = PlannerRequest(
                contract_version=request_version,
                request_id=f"{context.run_id}-remediate",
                kind=PlannerRequestKind.REMEDIATE,
                objective=f"Remediate stalled fan execution for plan {plan.plan_id}",
                evidence=evidence,
                source_plan_ref=_plan_ref(plan),
            )
            remediation_request_ref = _persist_ref(
                context, "planner-remediation-request", "planner-request", request
            )
            if context.checkpoint_sink is not None:
                context.checkpoint_sink()
    summaries: dict[str, ScopeRemediationSummary] = {
        scope_id: _scope_summary(state)
        for scope_id, state in scope_states.items()
    }
    return FanExecutionOutcome(
        results=ordered_results,
        scope_states=scope_states,
        postmerge_state=postmerge_state,
        next_step=next_step,
        remediation_scopes=tuple(remediation_scopes),
        stop_evidence_refs=stop_evidence_refs,
        remediation_request_ref=remediation_request_ref,
        scope_summaries=summaries,
    )


def _scope_summary(state: RemediationState) -> ScopeRemediationSummary:
    receipts = state.receipts
    debts = tuple(receipt.debt.score for receipt in receipts)
    applied = sum(len(receipt.applied_finding_keys) for receipt in receipts)
    deferred = sum(len(receipt.deferred_finding_keys) for receipt in receipts)
    best_debt = min(debts) if debts else (0 if state.disposition is RemediationDisposition.CLEAN else None)
    return ScopeRemediationSummary(
        rounds=len(receipts),
        initial_debt=debts[0] if debts else None,
        best_debt=best_debt,
        final_debt=debts[-1] if debts else None,
        applied_count=applied,
        deferred_count=deferred,
        result=state.disposition.value,
    )


def _scope_state_ref(context: FanContext, state: RemediationState) -> ArtifactRef:
    path = scope_state_path(context.artifact_directory, state.scope)
    raw = path.read_bytes()
    return ArtifactRef(
        artifact_id=f"{state.scope.run_id}/{state.scope.scope_id}/state",
        role="remediation_state",
        uri=path.resolve().as_uri(),
        digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        size_bytes=len(raw),
        media_type="application/json",
    )


def _load_stop_evidence_refs(context: FanContext) -> tuple[ArtifactRef, ...]:
    root = Path(context.artifact_directory).resolve() / "remediation" / _path_component(context.run_id) / _path_component("press-stop")
    if not root.exists():
        return ()
    refs: list[ArtifactRef] = []
    for path in sorted(root.glob("*.json")):
        raw = path.read_bytes()
        refs.append(ArtifactRef(
            artifact_id=path.stem,
            role="press-stop",
            uri=path.resolve().as_uri(),
            digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
            size_bytes=len(raw),
            media_type="application/json",
        ))
    return tuple(refs)


def _failure_reason(prefix: str, error: Exception) -> str:
    return f"{prefix}: {error}"[:512]


def _blocked_review(
    scope: RemediationScopeKey, review_round: int, error: Exception
) -> ReviewResult:
    version = supported_version_for(ReviewResult)
    assert isinstance(version, ContractVersion)
    return ReviewResult(
        contract_version=version,
        review_id=f"{scope.scope_id}-review-{review_round}-blocked",
        disposition=ReviewDisposition.BLOCKED,
        findings=(),
        coverage=(),
        reason=_failure_reason("review callback failed", error),
    )


def _blocked_cure_observation(
    locked_selection: tuple[str, ...], error: Exception
) -> RemediationCureObservation:
    version = supported_version_for(RemediationCureObservation)
    assert isinstance(version, ContractVersion)
    return RemediationCureObservation(
        contract_version=version,
        applied_finding_keys=(),
        deferred_finding_keys=locked_selection,
        touched_paths=(),
        gate_evidence=(),
        new_gate_failures=(f"cure-callback-failed:{type(error).__name__}",),
    )


def _next_step(
    all_passed: bool,
    postmerge_state: RemediationState | None,
    remediation_scopes: Sequence[str],
    *,
    full_coverage: bool = True,
) -> NextStep:
    if remediation_scopes:
        return "mold"
    if not all_passed:
        # Incomplete work never publishes and never presses (AC-12); route the
        # blocked curds to Mold for a replan.
        return "mold"
    if postmerge_state is None:
        # Partial coverage needs Mold to plan the omitted work.
        return "mold" if not full_coverage else "press"
    if postmerge_state.disposition is RemediationDisposition.CLEAN:
        return "done"
    # A non-clean post-merge review refuses publication (AC-10).
    return "mold"
