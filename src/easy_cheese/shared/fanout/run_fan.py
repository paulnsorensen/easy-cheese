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
``awaiting_review``, so resume dispatches Age and never repeats the Cure. A
A prepared-only dispatch intent blocks with zero applied findings and an
unknown outcome. A completed intent replays its recorded evidence before the
remaining gates.
"""
from __future__ import annotations

import json
import traceback
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
    canonical_digest,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError

from easy_cheese.shared.fanout.acceptance_types import (
    AcceptanceCheckResult,
    AcceptanceStopClassification,
    AcceptanceStopRecord,
    PressOutcome,
    PressRequest,
    PressRoundRecord,
    PressRoundResult,
    normalize_gate_failures,
)
from easy_cheese.shared.fanout.remediation import bind_event_identity
from easy_cheese.shared.fanout.remediation_decision import apply_event
from easy_cheese.shared.fanout.remediation_store import (
    StateStoreError,
    initial_state,
    load_state,
    publish_state,
    run_lock,
    scope_state_path,
)
from easy_cheese.shared.fanout.scheduler import schedule_wave
from easy_cheese.shared.publication import PublicationError, atomic_write
from easy_cheese.shared.remediation_artifacts import (
    REMEDIATION_STATE_ROLE,
    build_artifact_ref,
    contained_path,
    path_component,
)

AcceptanceChecker = Callable[[RemediationScopeKey, int], AcceptanceCheckResult]


# Host programming errors propagate; they never become a blocked scope.
_HOST_BUGS = (TypeError, AttributeError, NameError, AssertionError, KeyError)
_MAX_REASON = 2048
_TRACEBACK_FRAMES = 6
_DIGEST_SUFFIX_LENGTH = 12
CALLBACK_FAULT_ROLE = "callback-fault"
ACCEPTANCE_STOP_ROLE = "acceptance-stop"
CURE_INTENT_ROLE = "cure-intent"
PRESS_ROUND_ROLE = "press-round"
LEGACY_PRESS_ROLES = ("press-result", "press-stop")
MAX_PRESS_CORRECTIONS = 2
MAX_COVERAGE_RETRIES = 1
MAX_PRESS_ROUNDS = 6


def _require_acceptance_baseline(value: AcceptanceCheckResult) -> AcceptanceCheckResult:
    if not value.baseline_id:
        raise ValueError("Acceptance check result requires a baseline identity")
    return value


NextStep = Literal["done", "mold"]
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
PressDispatcher = Callable[[SemanticCurd, PressRequest], PressRoundResult]
CookCorrector = Callable[[SemanticCurd, PressRoundResult], CurdResult]
AgeReviewer = Callable[[RemediationEventContext], ReviewDispatchOutcome]
CureWorker = Callable[[RemediationEventContext], CureDispatchOutcome]


@attrs.frozen
class ScopeRemediationSummary:
    """Deterministic remediation summary for one fan scope."""

    rounds: int
    initial_debt: int | None
    best_debt: int | None
    final_debt: int | None
    applied_count: int
    deferred_count: int
    result: str


@attrs.frozen
class FanContext:
    """Everything `run_fan` needs beyond the plan: identity, root, and dispatch."""

    run_id: str
    artifact_directory: Path
    cook: CookWorker
    age: AgeReviewer
    cure: CureWorker
    acceptance_check: AcceptanceChecker | None = None
    press: PressDispatcher | None = None
    cook_correction: CookCorrector | None = None
    press_exempt: frozenset[str] = frozenset()
    result_sink: Callable[[CurdResult], None] | None = None
    checkpoint_sink: Callable[[], None] | None = None
    max_rounds: int = 8


@attrs.frozen
class FanExecutionOutcome:
    """The aggregate result of one fan run.

    ``results`` is one CurdResult per in-scope curd. ``scope_states`` maps each
    full scope identity to its final remediation state. ``next_step`` is
    the top-level Cook handoff verdict: ``done`` only when every curd and the
    post-merge review are clean, ``mold`` when coverage or remediation is
    incomplete. Press runs inside each per-curd Cook dispatch, never after the merge.
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


def _scope_key(scope: RemediationScopeKey) -> str:
    """Return a collision-free key for one run, kind, and scope identifier."""
    return canonical_bytes((
        scope.run_id, scope.scope_kind.value, scope.scope_id
    )).decode().rstrip("\n")


def _persist_ref(
    context: FanContext, name: str, role: str, contract: object
) -> ArtifactRef:
    """Persist an agent artifact and build a host-owned reference to it."""
    raw = canonical_bytes(contract)
    root = Path(context.artifact_directory).resolve()
    path = contained_path(
        root,
        root / "remediation" / path_component(context.run_id)
        / path_component(role) / f"{path_component(name)}.json",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, raw)
    return build_artifact_ref(path, raw, artifact_id=name, role=role)

def _persist_acceptance_stop(
    context: FanContext,
    scope: RemediationScopeKey,
    *,
    gate_round: int,
    baseline_id: str | None,
    classification: AcceptanceStopClassification,
    failure_reason: str,
    evidence: tuple[EvidenceRef, ...] = (),
) -> ArtifactRef:
    record = AcceptanceStopRecord(
        scope=scope,
        gate_round=gate_round,
        baseline_id=baseline_id,
        classification=classification,
        failure_reason=failure_reason[:_MAX_REASON],
        evidence=evidence,
    )
    return _persist_ref(
        context, f"{scope.scope_id}-acceptance-stop-{gate_round}", ACCEPTANCE_STOP_ROLE, record
    )


def _persist_fault(
    context: FanContext,
    scope: RemediationScopeKey,
    round_number: int,
    source: str,
    error: Exception,
) -> ArtifactRef:
    """Persist the exception type and a bounded traceback of a callback fault."""
    record = {
        "scope_id": scope.scope_id,
        "round_number": round_number,
        "source": source,
        "error_type": type(error).__name__,
        "reason": _failure_reason(f"{source} failed", error),
    }
    name = f"{scope.scope_id}-{source}-fault-{round_number}"
    return _persist_ref(context, name, CALLBACK_FAULT_ROLE, record)


def _artifact_name(
    scope: RemediationScopeKey, kind: str, round_number: int, request_digest: str
) -> str:
    """Name a round artifact so a retried request never overwrites it."""
    suffix = request_digest.rsplit(":", 1)[-1][:_DIGEST_SUFFIX_LENGTH]
    return f"{scope.scope_id}-{kind}-{round_number}-{suffix}"


def _unique_evidence(*groups: Sequence[EvidenceRef]) -> tuple[EvidenceRef, ...]:
    """Merge evidence groups by ``evidence_id`` in first-seen order."""
    unique: dict[str, EvidenceRef] = {}
    for group in groups:
        for item in group:
            _ = unique.setdefault(item.evidence_id, item)
    return tuple(unique.values())


def _gate_cure_observation(
    context: FanContext,
    acceptance_check: AcceptanceChecker,
    scope: RemediationScopeKey,
    round_number: int,
    observation: RemediationCureObservation,
    initial_evidence: tuple[EvidenceRef, ...],
) -> RemediationCureObservation:
    """Fold the post-cure acceptance check into the worker's Cure observation.

    An acceptance-check fault adds one failure name. It never rewrites the applied keys or
    the touched paths the worker reported.
    """
    try:
        gate = _require_acceptance_baseline(acceptance_check(scope, round_number))
    except _HOST_BUGS:
        raise
    except Exception as error:
        _ = _persist_fault(context, scope, round_number, "acceptance-callback", error)
        fault = f"acceptance-callback-failed:{type(error).__name__}"
        return attrs.evolve(
            observation,
            new_gate_failures=normalize_gate_failures(
                (*observation.new_gate_failures, fault)
            ),
        )
    gate_failures = () if gate.passed else ("acceptance-check-failed",)
    return attrs.evolve(
        observation,
        gate_evidence=_unique_evidence(
            initial_evidence, observation.gate_evidence, gate.evidence
        ),
        new_gate_failures=normalize_gate_failures(
            (*observation.new_gate_failures, *gate.new_failures, *gate_failures)
        ),
    )


def _fallback_request_digest(state: RemediationState, event: str) -> str:
    """Digest the host failure envelope when downstream dispatch cannot start."""
    return canonical_digest(
        {
            "event": event,
            "scope": state.scope,
            "state_id": state.state_id,
            "cursor": state.cursor,
            "round_number": len(state.receipts) + 1,
        }
    )


def _cure_intent_path(
    context: FanContext, scope: RemediationScopeKey, intent_digest: str
) -> Path:
    root = Path(context.artifact_directory).resolve()
    name = (
        f"{path_component(scope.scope_kind.value)}-{path_component(scope.scope_id)}-"
        f"{path_component(intent_digest)}.json"
    )
    return contained_path(
        root,
        root / "remediation" / path_component(context.run_id) / CURE_INTENT_ROLE / name,
    )


def _cure_intent(state: RemediationState, round_number: int) -> tuple[str, bytes]:
    """Return the host digest and prepared record for one Cure request."""
    intent_digest = canonical_digest(
        {
            "event": "cure-dispatch",
            "scope": state.scope,
            "state_id": state.state_id,
            "round_number": round_number,
            "locked_selection": list(state.locked_selection),
        }
    )
    record = {
        "scope": state.scope,
        "state_id": state.state_id,
        "round_number": round_number,
        "locked_selection": list(state.locked_selection),
        "intent_digest": intent_digest,
        "status": "prepared",
    }
    return intent_digest, canonical_bytes(record)


def _completed_cure_intent(
    state: RemediationState,
    round_number: int,
    intent_digest: str,
    outcome: tuple[RemediationCureObservation, str],
) -> bytes:
    observation, request_digest = outcome
    return canonical_bytes(
        {
            "scope": state.scope,
            "state_id": state.state_id,
            "round_number": round_number,
            "locked_selection": list(state.locked_selection),
            "intent_digest": intent_digest,
            "request_digest": request_digest,
            "status": "completed",
            "observation": observation,
        }
    )


def _read_completed_cure_intent(
    raw: bytes,
    state: RemediationState,
    round_number: int,
    intent_digest: str,
) -> tuple[str, RemediationCureObservation] | None:
    try:
        record_value = cast(object, json.loads(raw))
        if not isinstance(record_value, dict):
            raise ValueError("Cure intent must be a JSON object")
        record = cast(dict[str, object], record_value)
        expected = {
            "scope": json.loads(canonical_bytes(state.scope)),
            "state_id": state.state_id,
            "round_number": round_number,
            "locked_selection": list(state.locked_selection),
            "intent_digest": intent_digest,
        }
        if any(record.get(key) != value for key, value in expected.items()):
            raise ValueError("Cure intent does not match the current scope and round")
        status = record.get("status")
        if status == "prepared":
            return None
        if status != "completed":
            raise ValueError("Cure intent has an unknown status")
        request_digest = record.get("request_digest")
        observation_raw = record.get("observation")
        if not isinstance(request_digest, str) or not isinstance(observation_raw, dict):
            raise ValueError("completed Cure intent is missing its outcome")
        observation_raw = cast(dict[str, object], observation_raw)
        result = validate_contract(
            canonical_bytes(observation_raw),
            RemediationCureObservation,
            supported_version_for(RemediationCureObservation),
        )
        observation = cast(RemediationCureObservation, result.value)
        if (
            observation.event_identity is None
            or observation.event_identity.expected_request != request_digest
        ):
            raise ValueError("completed Cure intent has a mismatched request identity")
        return request_digest, observation
    except (ContractValidationError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise StateStoreError(f"invalid Cure intent: {error}") from error


def _outcome_unknown_observation(
    state: RemediationState, request_digest: str
) -> RemediationCureObservation:
    """Record that a prepared Cure may have run without claiming its result."""
    version = supported_version_for(RemediationCureObservation)
    assert isinstance(version, ContractVersion)
    return RemediationCureObservation(
        contract_version=version,
        applied_finding_keys=(),
        deferred_finding_keys=state.locked_selection,
        touched_paths=(),
        gate_evidence=(),
        new_gate_failures=("cure-outcome-unknown",),
        event_identity=bind_event_identity(state, request_digest, event="cure"),
    )


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


@attrs.frozen
class _ScopeRun:
    """One scope's drive context: host context, scope key, and state path."""

    context: FanContext
    scope: RemediationScopeKey
    path: Path
    gate_evidence: tuple[EvidenceRef, ...] = ()

    def publish(self, state: RemediationState) -> RemediationState:
        return publish_state(self.context.artifact_directory, self.path, state)


def _block_postmerge(
    run: _ScopeRun,
    state: RemediationState,
    *,
    baseline_id: str | None,
    classification: AcceptanceStopClassification,
    failure_reason: str,
    evidence: tuple[EvidenceRef, ...] = (),
) -> RemediationState:
    """Persist the acceptance stop, then publish the blocked terminal state."""
    _ = _persist_acceptance_stop(
        run.context,
        run.scope,
        gate_round=1,
        baseline_id=baseline_id,
        classification=classification,
        failure_reason=failure_reason,
        evidence=evidence,
    )
    blocked = attrs.evolve(
        state,
        cursor=RemediationCursor.TERMINAL,
        disposition=RemediationDisposition.BLOCKED,
    )
    return run.publish(blocked)


def _bootstrap_postmerge_gate(
    run: _ScopeRun, state: RemediationState
) -> tuple[RemediationState | None, tuple[EvidenceRef, ...]]:
    """Run the initial acceptance check. Return a blocked state or the gate evidence."""
    acceptance_check = run.context.acceptance_check
    if acceptance_check is None:
        blocked = _block_postmerge(
            run,
            state,
            baseline_id=None,
            classification=AcceptanceStopClassification.ABSENT,
            failure_reason="initial acceptance check is absent",
        )
        return blocked, ()
    try:
        gate = _require_acceptance_baseline(acceptance_check(run.scope, 1))
    except _HOST_BUGS:
        raise
    except Exception as error:
        blocked = _block_postmerge(
            run,
            state,
            baseline_id=None,
            classification=AcceptanceStopClassification.ERROR,
            failure_reason=_failure_reason("project gate callback failed", error),
        )
        return blocked, ()
    if gate.passed and not gate.new_failures:
        return None, gate.evidence
    blocked = _block_postmerge(
        run,
        state,
        baseline_id=gate.baseline_id,
        classification=AcceptanceStopClassification.FAILED,
        failure_reason="; ".join(gate.new_failures) or "initial acceptance check failed",
        evidence=gate.evidence,
    )
    return blocked, gate.evidence


def _run_review_round(run: _ScopeRun, state: RemediationState) -> RemediationState:
    """Dispatch one Age review and publish its transition."""
    review_round = len(state.receipts) + 1
    try:
        review, request_digest = _dispatch_review(run.context, state, review_round)
    except _HOST_BUGS:
        raise
    except Exception as error:
        request_digest = _fallback_request_digest(state, "review")
        review = attrs.evolve(
            _blocked_review(run.scope, review_round, error),
            event_identity=bind_event_identity(state, request_digest, event="review"),
        )
    name = _artifact_name(run.scope, "review", review_round, request_digest)
    next_state, _verdict = apply_event(
        state,
        event="review",
        artifact_ref=_persist_ref(run.context, name, "review", review),
        request_digest=request_digest,
        review=review,
        publish=run.publish,
        max_rounds=run.context.max_rounds,
    )
    return next_state


def _cure_once(
    run: _ScopeRun, state: RemediationState, cure_round: int, intent_path: Path
) -> tuple[RemediationCureObservation, str, bool]:
    """Dispatch Cure once, persisting its observation before state publication."""
    intent_digest, intent_raw = _cure_intent(state, cure_round)
    if intent_path.exists():
        try:
            raw = intent_path.read_bytes()
        except OSError as error:
            raise StateStoreError(f"cannot read Cure intent {intent_path}: {error}") from error
        completed = _read_completed_cure_intent(raw, state, cure_round, intent_digest)
        if completed is None:
            return _outcome_unknown_observation(state, intent_digest), intent_digest, True
        request_digest, observation = completed
        return observation, request_digest, False

    try:
        intent_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(intent_path, intent_raw)
    except (OSError, PublicationError) as error:
        raise StateStoreError(f"cannot persist Cure intent {intent_path}: {error}") from error

    try:
        observation, request_digest = _dispatch_cure(run.context, state, cure_round)
    except _HOST_BUGS:
        raise
    except Exception as error:
        _ = _persist_fault(run.context, run.scope, cure_round, "cure-callback", error)
        request_digest = _fallback_request_digest(state, "cure")
        observation = attrs.evolve(
            _blocked_cure_observation(
                state.locked_selection, error, source="cure-callback"
            ),
            event_identity=bind_event_identity(state, request_digest, event="cure"),
        )

    try:
        atomic_write(
            intent_path,
            _completed_cure_intent(
                state, cure_round, intent_digest, (observation, request_digest)
            ),
        )
    except (OSError, PublicationError) as error:
        raise StateStoreError(
            f"cannot persist completed Cure intent {intent_path}: {error}"
        ) from error
    return observation, request_digest, False


def _run_cure_round(run: _ScopeRun, state: RemediationState) -> RemediationState:
    """Run one Cure, publish its transition, then remove the dispatch intent."""
    cure_round = len(state.receipts)
    intent_digest, _intent_raw = _cure_intent(state, cure_round)
    intent_path = _cure_intent_path(run.context, run.scope, intent_digest)
    observation, request_digest, outcome_unknown = _cure_once(
        run, state, cure_round, intent_path
    )
    acceptance_check = run.context.acceptance_check
    if acceptance_check is not None and run.scope.scope_kind is RemediationScopeKind.POSTMERGE:
        # The check round stays review-based: round 1 is the initial check.
        observation = _gate_cure_observation(
            run.context, acceptance_check, run.scope, cure_round + 1, observation, run.gate_evidence
        )
    name = _artifact_name(run.scope, "cure", cure_round, request_digest)
    next_state, _verdict = apply_event(
        state,
        event="cure",
        artifact_ref=_persist_ref(run.context, name, "cure-result", observation),
        request_digest=request_digest,
        observation=observation,
    )
    if outcome_unknown:
        latest = attrs.evolve(
            next_state.receipts[-1],
            progress=False,
            stop_reason="cure outcome unknown: prepared dispatch has no completed worker observation",
        )
        next_state = attrs.evolve(
            next_state,
            cursor=RemediationCursor.TERMINAL,
            disposition=RemediationDisposition.BLOCKED,
            pending_cure_result_ref=None,
            receipts=(*next_state.receipts[:-1], latest),
        )
    next_state = run.publish(next_state)
    try:
        intent_path.unlink(missing_ok=True)
    except OSError:
        pass
    return next_state


def _load_resumed(run: _ScopeRun) -> RemediationState:
    """Reload a published state; a changed plan scope stops before dispatch (AC-14)."""
    state = load_state(run.context.artifact_directory, run.path)
    if state.scope != run.scope:
        raise StateStoreError(
            f"resumed scope {state.scope} does not match current plan scope {run.scope}"
        )
    return state


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
    run = _ScopeRun(context, scope, scope_state_path(context.artifact_directory, scope))
    if run.path.exists():
        state = _load_resumed(run)
    else:
        state = initial_state(scope, state_id=state_id)
        if postmerge:
            blocked, evidence = _bootstrap_postmerge_gate(run, state)
            if blocked is not None:
                return blocked
            run = attrs.evolve(run, gate_evidence=evidence)
        state = run.publish(state)
    while state.cursor is not RemediationCursor.TERMINAL:
        if state.cursor is RemediationCursor.AWAITING_REVIEW:
            state = _run_review_round(run, state)
        else:
            state = _run_cure_round(run, state)
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


@attrs.define
class _FanRun:
    """Mutable bookkeeping for one locked fan run."""

    plan: CurdPlan
    context: FanContext
    selected: Sequence[str] | None
    recorded: dict[str, CurdResult]
    scope_states: dict[str, RemediationState] = attrs.field(factory=lambda: cast(dict[str, RemediationState], {}))
    remediation_scopes: list[str] = attrs.field(factory=lambda: cast(list[str], []))

    def record(self, curd_id: str, result: CurdResult) -> None:
        """Record one curd result and checkpoint it exactly once.

        A host ``result_sink`` writes its own checkpoint. ``checkpoint_sink``
        runs only when no ``result_sink`` exists.
        """
        self.recorded[curd_id] = result
        if self.context.result_sink is not None:
            self.context.result_sink(result)
        elif self.context.checkpoint_sink is not None:
            self.context.checkpoint_sink()

    def note_scope_state(self, state: RemediationState) -> None:
        self.scope_states[_scope_key(state.scope)] = state
        if state.disposition is RemediationDisposition.STALLED:
            self.remediation_scopes.append(_scope_key(state.scope))

    def ordered_results(self) -> tuple[CurdResult, ...]:
        return tuple(
            self.recorded[curd.curd_id]
            for curd in self.plan.curds
            if curd.curd_id in self.recorded
        )


def _remediate_curd(
    fan: _FanRun, curd: SemanticCurd, cook_result: CurdResult
) -> CurdResult:
    """Drive one PASSED curd to a terminal state and map it onto its result.

    Fresh and resumed curds share this path. A terminal persisted state returns
    without dispatch.
    """
    scope = _curd_scope(fan.context.run_id, fan.plan, curd.curd_id)
    final = _drive_scope(scope, f"{curd.curd_id}-state", fan.context)
    fan.note_scope_state(final)
    return _result_after_remediation(fan.plan, curd, cook_result, final)


def _seed_resumed_scopes(fan: _FanRun) -> None:
    """Give every recorded PASSED curd a terminal state before scheduling."""
    known = {curd.curd_id for curd in fan.plan.curds}
    unknown = sorted(set(fan.recorded) - known)
    if unknown:
        raise ValueError("results contains unknown curd ids: " + ", ".join(unknown))
    root = fan.context.artifact_directory
    for curd in fan.plan.curds:
        result = fan.recorded.get(curd.curd_id)
        if result is None:
            continue
        if result.disposition is CurdDisposition.PASSED:
            progress = _replay_press_rounds(fan.context, curd)
            if curd.curd_id not in fan.context.press_exempt and not progress.settled:
                _finish_curd(fan, curd, result, progress)
                continue
            final = _remediate_curd(fan, curd, result)
            if final is not result:
                fan.record(curd.curd_id, final)
            continue
        path = scope_state_path(root, _curd_scope(fan.context.run_id, fan.plan, curd.curd_id))
        if path.exists():
            fan.note_scope_state(load_state(root, path))


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
    The run lock covers the whole execution. A second process cannot drive the
    same run id at the same time.
    """
    with run_lock(context.artifact_directory, context.run_id):
        return _run_fan_locked(plan, context, selected=selected, results=results)


def run_fan_locked(
    plan: CurdPlan,
    context: FanContext,
    *,
    selected: Sequence[str] | None = None,
    results: Mapping[str, CurdResult] | None = None,
) -> FanExecutionOutcome:
    """Run the fan state machine while the caller holds ``context.run_id``'s lock."""
    return _run_fan_locked(plan, context, selected=selected, results=results)


def _press_halt(
    fan: _FanRun,
    curd: SemanticCurd,
    *,
    request: PressRequest,
    result: PressRoundResult,
    halt: str,
) -> CurdResult:
    _ = _persist_press_round(fan.context, curd, request, result, halt=halt)
    reason = f"halt: {halt}"
    return _blocked_result(fan.plan, curd, reason=reason, unresolved=(reason,))


def _persist_press_round(
    context: FanContext,
    curd: SemanticCurd,
    request: PressRequest,
    result: PressRoundResult,
    *,
    halt: str | None = None,
    checkpoint: bool = True,
) -> ArtifactRef:
    record = PressRoundRecord(
        curd_id=curd.curd_id,
        round_number=request.round_number,
        outcome=result.outcome,
        attack_id=result.attack_id,
        summary=result.summary[:_MAX_REASON],
        halt=halt,
        evidence=result.evidence,
    )
    ref = _persist_ref(
        context, f"{curd.curd_id}-press-{request.round_number}", PRESS_ROUND_ROLE, record
    )
    if checkpoint and context.checkpoint_sink is not None:
        context.checkpoint_sink()
    return ref


@attrs.define
class _PressProgress:
    """Replayable Press round counters for one curd."""

    round_number: int = 0
    attack_id: str | None = None
    findings: dict[str | None, int] = attrs.field(factory=dict)
    coverage_gaps: int = 0
    settled: bool = False
    halted: str | None = None


def _press_round_files(
    context: FanContext, curd: SemanticCurd
) -> list[tuple[Path, dict[str, object]]]:
    """Return a curd's persisted press-round files with their records, by round."""
    role_dir = (
        Path(context.artifact_directory).resolve() / "remediation"
        / path_component(context.run_id) / path_component(PRESS_ROUND_ROLE)
    )
    found: list[tuple[Path, dict[str, object]]] = []
    for path in sorted(role_dir.glob("*.json")):
        record = cast("dict[str, object]", json.loads(path.read_bytes()))
        if record.get("curd_id") == curd.curd_id:
            found.append((path, record))
    found.sort(key=lambda item: cast(int, item[1]["round_number"]))
    return found


def _replay_press_rounds(context: FanContext, curd: SemanticCurd) -> _PressProgress:
    """Restore a curd's Press counters from its persisted press-round records."""
    progress = _PressProgress()
    for _path, record in _press_round_files(context, curd):
        progress.round_number = cast(int, record["round_number"])
        halt = cast("str | None", record.get("halt"))
        if halt is not None:
            progress.halted = halt
        outcome = record["outcome"]
        if outcome in (PressOutcome.GREEN.value, PressOutcome.EXEMPT.value):
            progress.settled = halt is None
        elif outcome == PressOutcome.FINDING.value:
            attack = cast("str | None", record.get("attack_id"))
            progress.attack_id = attack
            progress.findings[attack] = progress.findings.get(attack, 0) + 1
        elif outcome == PressOutcome.COVERAGE_GAP.value:
            progress.coverage_gaps += 1
    return progress


def _clear_press_rounds(context: FanContext, curd: SemanticCurd) -> None:
    """Delete a curd's prior press-round files so a fresh Cook restarts at round 1."""
    for path, _record in _press_round_files(context, curd):
        path.unlink()


def _press_fault(
    fan: _FanRun, curd: SemanticCurd, source: str, round_number: int, error: Exception
) -> CurdResult:
    scope = _curd_scope(fan.context.run_id, fan.plan, curd.curd_id)
    _ = _persist_fault(fan.context, scope, round_number, source, error)
    reason = f"{source} failed: {type(error).__name__}"
    return _blocked_result(fan.plan, curd, reason=reason, unresolved=(reason,))


def _press_curd(
    fan: _FanRun, curd: SemanticCurd, cook_result: CurdResult, progress: _PressProgress
) -> CurdResult:
    """Run the orchestrator-owned Press loop for one passed behavior curd.

    Cook is the single round counter. Press has no memory across dispatches, so
    each request carries the round number and the attack identity to replay.
    Persisted press-round records restore the counters on resume. Findings are
    capped per attack and the loop has a total round bound.
    Returns the (possibly corrected) Cook result, or a blocked result that
    names the halt.
    """
    context = fan.context
    if curd.curd_id in context.press_exempt:
        exempt = PressRoundResult(
            outcome=PressOutcome.EXEMPT, summary="non-behavior curd exempt from Press"
        )
        _ = _persist_press_round(
            context, curd, PressRequest(round_number=1), exempt, checkpoint=False
        )
        return cook_result
    if context.press is None:
        raise RuntimeError(
            f"behavior curd {curd.curd_id} requires a Press dispatcher; mark it in press_exempt only for non-behavior work"
        )
    if progress.halted is not None:
        reason = f"halt: {progress.halted}"
        return _blocked_result(fan.plan, curd, reason=reason, unresolved=(reason,))
    if progress.settled:
        return cook_result
    while True:
        request = PressRequest(
            round_number=progress.round_number + 1, attack_id=progress.attack_id
        )
        try:
            result = context.press(curd, request)
        except _HOST_BUGS:
            raise
        except Exception as error:
            return _press_fault(fan, curd, "press-callback", request.round_number, error)
        progress.round_number = request.round_number
        halt: str | None = None
        if result.outcome is PressOutcome.GREEN:
            _ = _persist_press_round(context, curd, request, result)
            return cook_result
        if result.outcome in (PressOutcome.INVALID_EVIDENCE, PressOutcome.EXEMPT):
            halt = "invalid-evidence"
        elif result.outcome is PressOutcome.PRODUCTION_CHANGED:
            halt = "production-changed"
        elif result.outcome is PressOutcome.FINDING:
            progress.attack_id = result.attack_id
            count = progress.findings.get(result.attack_id, 0) + 1
            progress.findings[result.attack_id] = count
            if count > MAX_PRESS_CORRECTIONS:
                halt = "correction-cap"
        else:
            progress.coverage_gaps += 1
            if progress.coverage_gaps > MAX_COVERAGE_RETRIES:
                halt = "coverage-gap"
        if halt is None and progress.round_number >= MAX_PRESS_ROUNDS:
            halt = "press-round-limit"
        if halt is not None:
            return _press_halt(fan, curd, request=request, result=result, halt=halt)
        _ = _persist_press_round(context, curd, request, result)
        if context.cook_correction is None:
            raise RuntimeError(
                f"curd {curd.curd_id} needs a Cook correction but no corrector is configured"
            )
        try:
            cook_result = context.cook_correction(curd, result)
        except _HOST_BUGS:
            raise
        except Exception as error:
            return _press_fault(fan, curd, "cook-correction", request.round_number, error)
        if cook_result.disposition is not CurdDisposition.PASSED:
            return cook_result


def _finish_curd(
    fan: _FanRun,
    curd: SemanticCurd,
    cook_result: CurdResult,
    progress: _PressProgress | None = None,
) -> None:
    """Press a passed curd, then remediate it or publish its blocked state.

    A resumed curd passes its replayed `progress`; a fresh Cook starts at zero.
    """
    context = fan.context
    if cook_result.disposition is CurdDisposition.PASSED:
        cook_result = _press_curd(fan, curd, cook_result, progress or _PressProgress())
    if cook_result.disposition is CurdDisposition.PASSED:
        fan.record(curd.curd_id, _remediate_curd(fan, curd, cook_result))
        return
    scope = _curd_scope(context.run_id, fan.plan, curd.curd_id)
    blocked_state = attrs.evolve(
        initial_state(scope, state_id=f"{curd.curd_id}-state"),
        cursor=RemediationCursor.TERMINAL,
        disposition=RemediationDisposition.BLOCKED,
    )
    fan.scope_states[_scope_key(scope)] = publish_state(
        context.artifact_directory,
        scope_state_path(context.artifact_directory, scope),
        blocked_state,
    )
    fan.record(curd.curd_id, cook_result)


def _cook_and_remediate(fan: _FanRun, curd: SemanticCurd) -> None:
    """Cook one ready curd, press it, then remediate it or publish its blocked state."""
    _clear_press_rounds(fan.context, curd)
    _finish_curd(fan, curd, fan.context.cook(curd))


def _run_waves(fan: _FanRun) -> None:
    """Schedule dependency waves until every in-scope curd has a result."""
    curds = {curd.curd_id: curd for curd in fan.plan.curds}
    while True:
        decision = schedule_wave(fan.plan, fan.recorded, selected=fan.selected)
        if decision.complete:
            return
        for blocked in decision.blocked:
            reason = "dependency did not pass: " + ", ".join(blocked.blocked_by)
            result = _blocked_result(
                fan.plan, curds[blocked.curd_id], reason=reason, unresolved=blocked.blocked_by
            )
            fan.record(blocked.curd_id, result)
        if not decision.ready and not decision.blocked:
            raise RuntimeError(
                "no schedulable curd; unresolved dependencies remain for: "
                + ", ".join(decision.remaining)
            )
        # A wave with only blocked curds loops again to propagate them.
        for curd_id in decision.ready:
            _cook_and_remediate(fan, curds[curd_id])


def _run_postmerge(fan: _FanRun) -> RemediationState:
    """Drive the post-merge scope and note a stall for Mold."""
    state = _drive_scope(
        _postmerge_scope(fan.context.run_id, fan.plan),
        "postmerge-state",
        fan.context,
        postmerge=True,
    )
    fan.scope_states[_scope_key(state.scope)] = state
    if state.disposition is RemediationDisposition.STALLED:
        fan.remediation_scopes.append(_scope_key(state.scope))
    return state


def _build_remediation_request(
    fan: _FanRun,
    results: Sequence[CurdResult],
    stop_evidence_refs: Sequence[ArtifactRef],
) -> ArtifactRef | None:
    """Persist the Mold REMEDIATE request over every stop, state, and result."""
    context = fan.context
    refs = [
        *stop_evidence_refs,
        *(_scope_state_ref(context, state) for state in fan.scope_states.values()),
        *(
            _persist_ref(
                context, f"result-{result.source_curd_ref.curd_id}", "curd-result", result
            )
            for result in results
        ),
    ]
    if not refs:
        return None
    evidence = tuple(
        EvidenceRef(
            evidence_id=f"planner-evidence-{index}",
            kind=EvidenceKind.RUNTIME,
            artifact=ref,
            summary=f"fan remediation evidence: {ref.role}",
        )
        for index, ref in enumerate(refs, start=1)
    )
    request_version = supported_version_for(PlannerRequest)
    if request_version is None:
        raise RuntimeError("planner request has no supported version")
    request = PlannerRequest(
        contract_version=request_version,
        request_id=f"{context.run_id}-remediate",
        kind=PlannerRequestKind.REMEDIATE,
        objective=f"Remediate stalled fan execution for plan {fan.plan.plan_id}",
        evidence=evidence,
        source_plan_ref=_plan_ref(fan.plan),
    )
    ref = _persist_ref(context, "planner-remediation-request", "planner-request", request)
    if context.checkpoint_sink is not None:
        context.checkpoint_sink()
    return ref


def _run_fan_locked(
    plan: CurdPlan,
    context: FanContext,
    *,
    selected: Sequence[str] | None,
    results: Mapping[str, CurdResult] | None,
) -> FanExecutionOutcome:
    """Run the fan stages while the caller holds the run lock."""
    _reject_legacy_press_roles(context)
    fan = _FanRun(plan, context, selected, dict(results or {}))
    _require_press_dispatcher(fan)
    _seed_resumed_scopes(fan)
    _run_waves(fan)
    ordered_results = fan.ordered_results()
    all_passed = bool(ordered_results) and all(
        result.disposition is CurdDisposition.PASSED for result in ordered_results
    )
    full_coverage = selected is None or set(selected) == {c.curd_id for c in plan.curds}
    postmerge_state = _run_postmerge(fan) if all_passed and full_coverage else None
    next_step = _next_step(all_passed, postmerge_state, fan.remediation_scopes)
    stop_evidence_refs = _load_stop_evidence_refs(context)
    remediation_request_ref = None
    if next_step == "mold":
        remediation_request_ref = _build_remediation_request(
            fan, ordered_results, stop_evidence_refs
        )
    return FanExecutionOutcome(
        results=ordered_results,
        scope_states=fan.scope_states,
        postmerge_state=postmerge_state,
        next_step=next_step,
        remediation_scopes=tuple(fan.remediation_scopes),
        stop_evidence_refs=stop_evidence_refs,
        remediation_request_ref=remediation_request_ref,
        scope_summaries={
            scope_key: _scope_summary(state)
            for scope_key, state in fan.scope_states.items()
        },
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
    return build_artifact_ref(
        path,
        raw,
        artifact_id=(
            f"{state.scope.run_id}/{state.scope.scope_kind.value}/"
            f"{state.scope.scope_id}/state"
        ),
        role=REMEDIATION_STATE_ROLE,
    )


def _reject_legacy_press_roles(context: FanContext) -> None:
    """Refuse a run whose persisted artifacts predate the acceptance-check change."""
    run_root = Path(context.artifact_directory).resolve() / "remediation" / path_component(context.run_id)
    for legacy in LEGACY_PRESS_ROLES:
        if any((run_root / path_component(legacy)).glob("*.json")):
            raise ValueError(
                f"persisted role {legacy!r} predates the acceptance-check change; this run cannot resume, so start a fresh run"
            )


def _require_press_dispatcher(fan: _FanRun) -> None:
    """Fail before any dispatch when a behavior curd has no Press dispatcher."""
    context = fan.context
    if context.press is not None:
        return
    scoped = set(fan.selected) if fan.selected is not None else None
    for curd in fan.plan.curds:
        if scoped is not None and curd.curd_id not in scoped:
            continue
        if curd.curd_id in context.press_exempt:
            continue
        if curd.curd_id in fan.recorded and _replay_press_rounds(context, curd).settled:
            continue
        raise RuntimeError(
            f"behavior curd {curd.curd_id} requires a Press dispatcher; mark it in press_exempt only for non-behavior work"
        )


def _load_stop_evidence_refs(context: FanContext) -> tuple[ArtifactRef, ...]:
    """Load every persisted acceptance stop, callback fault, and press halt."""
    run_root = Path(context.artifact_directory).resolve() / "remediation" / path_component(context.run_id)
    refs: list[ArtifactRef] = []
    for role in (ACCEPTANCE_STOP_ROLE, CALLBACK_FAULT_ROLE, PRESS_ROUND_ROLE):
        for path in sorted((run_root / path_component(role)).glob("*.json")):
            raw = path.read_bytes()
            if role == PRESS_ROUND_ROLE:
                record = cast("dict[str, object]", json.loads(raw))
                if record.get("halt") is None:
                    continue
            refs.append(build_artifact_ref(path, raw, artifact_id=path.stem, role=role))
    return tuple(refs)


def _failure_reason(prefix: str, error: Exception) -> str:
    """Name a failure with its exception type and a bounded traceback."""
    head = f"{prefix}: {type(error).__name__}: {error}"[:512]
    frames = "".join(
        traceback.format_exception(
            type(error), error, error.__traceback__, limit=-_TRACEBACK_FRAMES
        )
    )
    return f"{head}\n{frames[-(_MAX_REASON - len(head) - 1):]}"


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
    locked_selection: tuple[str, ...], error: Exception, *, source: str
) -> RemediationCureObservation:
    """Build a zero-progress observation that names the failed `source`."""
    version = supported_version_for(RemediationCureObservation)
    assert isinstance(version, ContractVersion)
    return RemediationCureObservation(
        contract_version=version,
        applied_finding_keys=(),
        deferred_finding_keys=locked_selection,
        touched_paths=(),
        gate_evidence=(),
        new_gate_failures=normalize_gate_failures(
            (f"{source}-failed:{type(error).__name__}",)
        ),
    )


def _next_step(
    all_passed: bool,
    postmerge_state: RemediationState | None,
    remediation_scopes: Sequence[str],
) -> NextStep:
    clean = (
        not remediation_scopes
        and all_passed
        and postmerge_state is not None
        and postmerge_state.disposition is RemediationDisposition.CLEAN
    )
    # Incomplete work, partial coverage, and a non-clean post-merge review all
    # route to Mold; only the clean conjunction publishes (AC-10, AC-12).
    return "done" if clean else "mold"
