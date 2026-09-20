"""Pure decision core for progress-aware fan remediation (mini-spec Sec4/Sec5).

No argparse, no I/O, no clock. `decide_review` and `decide_cure` take the
persisted `RemediationState` plus one event's normalized inputs and return
the next immutable state plus a router verdict. The CLI wrapper
(`remediation_decision.py`) owns argument parsing, artifact loading, and
atomic state publication; it never re-derives the decisions made here.

Design decisions locked by `.context/remediation-decisions.md`:

- D1: the selection floor is critical/high/medium, plus low findings whose
  `fix_cost_now` is `contained`. Non-contained low findings never enter
  `locked_selection`; they are recorded as deferred evidence instead.
- D2: `finding_key` digests normalized dimension, canonical source path (or
  the empty string when the finding carries no location), and the
  casefolded, whitespace-collapsed finding summary. Severity and line
  offsets never enter the key.
- D3: `fix_cost_now` is consulted only for low-severity findings; it is
  inert for critical/high/medium.

AC-17 (agent-authored round/score/clean fields are ignored) holds by
construction: every value this module reads comes from `ReviewResult`/
`ReviewFinding`, which carry no round, score, or clean field for an agent to
author. Nothing here ever accepts such a field from a caller.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, TypedDict

import attrs

from easy_cheese_schemas import (
    ArtifactRef,
    EvidenceRef,
    FixCostNow,
    ProgressReceipt,
    RemediationCursor,
    RemediationDisposition,
    RemediationState,
    ReviewDebt,
    ReviewDisposition,
    ReviewFinding,
    RemediationEventIdentity,
    ReviewResult,
    ReviewSeverity,
    RemediationScopeKey,
    canonical_digest,
)

Action = Literal["age", "cure", "complete", "remediate", "blocked"]


@attrs.frozen
class PressGateResult:
    """Host-validated result from one post-merge Press gate."""

    passed: bool
    baseline_id: str
    new_failures: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    scope: RemediationScopeKey | None = None
    gate_round: int | None = None


class PressStopClassification(str, Enum):
    """Reason an initial Press gate stopped post-merge execution."""

    ABSENT = "absent"
    FAILED = "failed"
    ERROR = "error"


@attrs.frozen
class PressStopRecord:
    """Typed host record for an absent or failed initial Press gate."""

    scope: RemediationScopeKey
    gate_round: int
    baseline_id: str | None
    classification: PressStopClassification
    failure_reason: str
    evidence: tuple[EvidenceRef, ...] = ()

_BLOCKING_DISPOSITIONS = (
    ReviewDisposition.BLOCKED,
    ReviewDisposition.INVALID,
    ReviewDisposition.EXECUTOR_FAILURE,
)

_NEXT_PHASE_BY_ACTION: dict[Action, str | None] = {
    "age": "age",
    "cure": "cure",
    "complete": None,
    "remediate": "mold",
    "blocked": None,
}


class Verdict(TypedDict):
    action: Action
    next_phase: str | None
    scope: dict[str, str]
    cursor: str
    state_ref: str
    progress: bool
    reason: str | None


def finding_key(finding: ReviewFinding) -> str:
    """Derive D2's host reconciliation key for one finding.

    Digests normalized dimension + canonical source path (empty when the
    finding has no location) + normalized claim text, newline-joined.
    Severity and line offsets are excluded on purpose: they can shift
    between rounds without the underlying claim changing.
    """
    dimension = finding.dimension.value
    path = finding.location.path if finding.location is not None else ""
    if path:
        parts = path.replace("\\", "/").split("/")
        if path.startswith("/") or any(part == ".." for part in parts):
            raise ValueError(f"unsafe finding location path: {path!r}")
        path = "/".join(part for part in parts if part not in {"", "."})
    claim = " ".join(finding.summary.casefold().split())
    return canonical_digest(f"{dimension}\n{path}\n{claim}")


def compute_debt(findings: tuple[ReviewFinding, ...]) -> ReviewDebt:
    """Score `findings` at 16/8/4/1 weights (critical/high/medium/contained-low).

    Always built via `ReviewDebt.compute` so the score can never drift from
    the counts that produced it.
    """
    critical = sum(1 for f in findings if f.severity is ReviewSeverity.CRITICAL)
    high = sum(1 for f in findings if f.severity is ReviewSeverity.HIGH)
    medium = sum(1 for f in findings if f.severity is ReviewSeverity.MEDIUM)
    contained_low = sum(
        1
        for f in findings
        if f.severity is ReviewSeverity.LOW and f.fix_cost_now is FixCostNow.CONTAINED
    )
    return ReviewDebt.compute(
        critical=critical, high=high, medium=medium, contained_low=contained_low
    )


def locked_selection_and_deferred(
    findings: tuple[ReviewFinding, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split `findings` into D1's selection floor and its deferred low keys.

    Selected: every critical/high/medium finding, plus low findings marked
    `contained`. Deferred: low findings marked `sprawling` -- excluded from
    automatic remediation debt but recorded as evidence.
    """
    selected: list[str] = []
    deferred: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        key = finding_key(finding)
        if key in seen:
            # Duplicate normalized findings remain unresolved new debt.
            deferred.append(key)
            continue
        seen.add(key)
        if finding.severity is ReviewSeverity.LOW:
            if finding.fix_cost_now is FixCostNow.CONTAINED:
                selected.append(key)
            else:
                deferred.append(key)
        else:
            selected.append(key)
    return tuple(selected), tuple(deferred)


def duplicate_finding_keys(findings: tuple[ReviewFinding, ...]) -> tuple[str, ...]:
    """Return normalized finding keys whose collision makes reconciliation ambiguous."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for finding in findings:
        key = finding_key(finding)
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return tuple(sorted(duplicates))


def is_automation_clean(findings: tuple[ReviewFinding, ...]) -> bool:
    """AC-18: true when `findings` has no critical/high/medium/contained-low.

    Non-contained low findings alone do not block automation-clean.
    """
    selected, _deferred = locked_selection_and_deferred(findings)
    return not selected


def _scope_dict(state: RemediationState) -> dict[str, str]:
    return {"kind": state.scope.scope_kind.value, "id": state.scope.scope_id}


def _verdict(
    state: RemediationState, action: Action, progress: bool, reason: str | None
) -> Verdict:
    return {
        "action": action,
        "next_phase": _NEXT_PHASE_BY_ACTION[action],
        "scope": _scope_dict(state),
        "cursor": state.cursor.value,
        "state_ref": state.state_id,
        "progress": progress,
        "reason": reason,
    }


def bind_event_identity(
    state: RemediationState,
    request_digest: str,
    *,
    event: Literal["review", "cure"],
) -> RemediationEventIdentity:
    """Bind an event to active state and the exact host request digest."""
    expected_cursor = (
        RemediationCursor.AWAITING_REVIEW
        if event == "review"
        else RemediationCursor.AWAITING_CURE
    )
    if state.cursor is not expected_cursor:
        raise ValueError(
            f"{event} event rejected: cursor is {state.cursor.value}, not {expected_cursor.value}"
        )
    return RemediationEventIdentity(
        run_id=state.scope.run_id,
        plan_id=state.scope.source_plan_ref.plan_id,
        plan_revision=state.scope.source_plan_ref.revision,
        plan_digest=state.scope.source_plan_ref.digest,
        scope_kind=state.scope.scope_kind,
        scope_id=state.scope.scope_id,
        state_id=state.state_id,
        cursor=state.cursor,
        expected_request=request_digest,
        round_number=len(state.receipts) + 1,
    )


def validate_event_identity(
    state: RemediationState,
    identity: RemediationEventIdentity,
    *,
    event: Literal["review", "cure"],
    request_digest: str | None = None,
) -> None:
    """Reject an event unless its host-owned identity matches active state."""
    expected_cursor = (
        RemediationCursor.AWAITING_REVIEW
        if event == "review"
        else RemediationCursor.AWAITING_CURE
    )
    expected = {
        "run_id": state.scope.run_id,
        "plan_id": state.scope.source_plan_ref.plan_id,
        "plan_revision": state.scope.source_plan_ref.revision,
        "plan_digest": state.scope.source_plan_ref.digest,
        "scope_kind": state.scope.scope_kind,
        "scope_id": state.scope.scope_id,
        "state_id": state.state_id,
        "cursor": expected_cursor,
        "round_number": len(state.receipts) + 1,
    }
    for name, value in expected.items():
        if getattr(identity, name) != value:
            raise ValueError(f"{event} event identity mismatch: {name}")
    if request_digest is not None and identity.expected_request != request_digest:
        raise ValueError(f"{event} event identity mismatch: expected_request")


def decide_review(
    state: RemediationState, review: ReviewResult, review_ref: ArtifactRef
) -> tuple[RemediationState, Verdict]:
    """Apply mini-spec Sec4's Review event to `state`.

    Raises `ValueError` when `state.cursor` is not `awaiting_review` -- the
    router rejects events that do not match the persisted cursor.
    """
    if state.cursor is not RemediationCursor.AWAITING_REVIEW:
        raise ValueError(
            f"review event rejected: cursor is {state.cursor.value}, not awaiting_review"
        )

    preceding_cure_ref = state.pending_cure_result_ref

    if review.disposition in _BLOCKING_DISPOSITIONS:
        selected: tuple[str, ...] = ()
        deferred: tuple[str, ...] = ()
        debt = ReviewDebt.compute(critical=0, high=0, medium=0, contained_low=0)
        disposition = RemediationDisposition.BLOCKED
        cursor = RemediationCursor.TERMINAL
        action: Action = "blocked"
        best_debt = state.best_debt
        stagnation_count = state.stagnation_count
        progress = False
        reason = review.reason or f"review disposition {review.disposition.value}"
    else:
        selected, deferred = locked_selection_and_deferred(review.findings)
        debt = compute_debt(review.findings)
        collisions = duplicate_finding_keys(review.findings)
        if collisions:
            disposition = RemediationDisposition.STALLED
            cursor = RemediationCursor.TERMINAL
            action = "remediate"
            best_debt = state.best_debt
            stagnation_count = state.stagnation_count
            progress = False
            reason = "ambiguous duplicate finding keys: " + ", ".join(collisions)
        elif not selected:
            disposition = RemediationDisposition.CLEAN
            cursor = RemediationCursor.TERMINAL
            action = "complete"
            best_debt = state.best_debt
            stagnation_count = state.stagnation_count
            progress = True
            reason = None
        elif state.best_debt is None or debt.score < state.best_debt.score:
            disposition = RemediationDisposition.ACTIVE
            cursor = RemediationCursor.AWAITING_CURE
            action = "cure"
            best_debt = debt
            stagnation_count = 0
            progress = True
            reason = None
        else:
            stagnation_count = state.stagnation_count + 1
            best_debt = state.best_debt
            if stagnation_count >= 2:
                disposition = RemediationDisposition.STALLED
                cursor = RemediationCursor.TERMINAL
                action = "remediate"
                progress = False
                reason = "stalled after two reviews without a new best debt score"
            else:
                disposition = RemediationDisposition.ACTIVE
                cursor = RemediationCursor.AWAITING_CURE
                action = "cure"
                progress = False
                reason = None

    round_number = len(state.receipts) + 1
    receipt = ProgressReceipt(
        round_number=round_number,
        review_ref=review_ref,
        preceding_cure_result_ref=preceding_cure_ref,
        selected_finding_keys=selected,
        applied_finding_keys=(),
        deferred_finding_keys=deferred,
        debt=debt,
        gate_evidence=(),
        touched_paths=(),
        progress=progress,
        stop_reason=reason,
    )

    next_state = attrs.evolve(
        state,
        cursor=cursor,
        disposition=disposition,
        locked_selection=selected,
        pending_cure_result_ref=None,
        best_debt=best_debt,
        stagnation_count=stagnation_count,
        receipts=(*state.receipts, receipt),
    )
    return next_state, _verdict(next_state, action, progress, reason)


def decide_cure(
    state: RemediationState,
    cure_ref: ArtifactRef,
    applied_finding_keys: tuple[str, ...],
    deferred_finding_keys: tuple[str, ...],
    gate_evidence: tuple[EvidenceRef, ...],
    touched_paths: tuple[str, ...],
    *,
    new_gate_failures: bool,
    reverted_finding_keys: tuple[str, ...] = (),
) -> tuple[RemediationState, Verdict]:
    """Apply mini-spec Sec4's Cure event to `state`.

    Enforces Sec3's partition invariant: `applied_finding_keys` and
    `deferred_finding_keys` must together equal `state.locked_selection`
    exactly, with no overlap. Raises `ValueError` on a cursor mismatch, a
    missing prior review receipt, or a partition violation -- all caller
    contract bugs, not review-content stops.
    """
    if state.cursor is not RemediationCursor.AWAITING_CURE:
        raise ValueError(
            f"cure event rejected: cursor is {state.cursor.value}, not awaiting_cure"
        )
    if not state.receipts:
        raise ValueError("cure event rejected: no review receipt to attach this cure to")

    applied = tuple(applied_finding_keys)
    deferred = tuple(deferred_finding_keys)
    reverted = set(reverted_finding_keys)
    locked = set(state.locked_selection)
    if not reverted <= locked:
        raise ValueError("reverted finding keys must be a subset of locked_selection")
    if set(applied) & set(deferred):
        raise ValueError("applied and deferred finding keys must not overlap")
    if set(applied) | set(deferred) != set(state.locked_selection):
        raise ValueError(
            "applied and deferred finding keys must exactly partition locked_selection"
        )

    final_applied = tuple(key for key in applied if key not in reverted)
    final_deferred = tuple(dict.fromkeys((*deferred, *reverted)))
    latest_receipt = state.receipts[-1]
    updated_receipt = attrs.evolve(
        latest_receipt,
        applied_finding_keys=final_applied,
        deferred_finding_keys=final_deferred,
        gate_evidence=tuple(gate_evidence),
        touched_paths=tuple(touched_paths),
        cure_result_ref=cure_ref,
    )

    if reverted == locked:
        disposition = RemediationDisposition.STALLED
        cursor = RemediationCursor.TERMINAL
        action: Action = "remediate"
        progress = False
        reason = "all selected findings were reverted"
        pending_cure_result_ref = None
    elif not final_applied:
        disposition = RemediationDisposition.STALLED
        cursor = RemediationCursor.TERMINAL
        action = "remediate"
        progress = False
        reason = "cure applied zero selected findings"
        pending_cure_result_ref = None
    elif new_gate_failures:
        disposition = RemediationDisposition.BLOCKED
        cursor = RemediationCursor.TERMINAL
        action = "blocked"
        progress = False
        reason = "new or changed project gate failure after cure"
        pending_cure_result_ref = None
    else:
        disposition = state.disposition
        cursor = RemediationCursor.AWAITING_REVIEW
        action = "age"
        progress = True
        reason = None
        pending_cure_result_ref = cure_ref

    updated_receipt = attrs.evolve(updated_receipt, progress=progress, stop_reason=reason)
    receipts = (*state.receipts[:-1], updated_receipt)

    next_state = attrs.evolve(
        state,
        cursor=cursor,
        disposition=disposition,
        pending_cure_result_ref=pending_cure_result_ref,
        receipts=receipts,
    )
    return next_state, _verdict(next_state, action, progress, reason)
