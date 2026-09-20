"""Integration tests for the fan remediation orchestrator (Sec6/7/9/11/12).

Drives `run_fan` and `_drive_scope` with scripted fake Cook/Age/Cure workers to
cover AC-9..14 and AC-19..21.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

import attrs

import pytest

from easy_cheese_schemas import (
    ArtifactRef,
    BoundedScope,
    ContractVersion,
    Criterion,
    CriterionDisposition,
    CriterionResult,
    CoverageDisposition,
    CurdDisposition,
    CurdPlan,
    CurdResult,
    EvidenceKind,
    EvidenceRef,
    FixCostNow,
    IdentityAction,
    IdentityLineage,
    RemediationCureObservation,
    RemediationCursor,
    RemediationDisposition,
    RemediationScopeKey,
    RemediationScopeKind,
    RemediationState,
    ReviewCoverage,
    ReviewDimension,
    ReviewDisposition,
    ReviewFinding,
    ReviewResult,
    ReviewSeverity,
    SemanticCurd,
    SourceCurdRef,
    SourcePlanRef,
    PlannerRequest,
    PlannerRequestKind,
    supported_version_for,
    validate_contract,
)

from easy_cheese.shared.fanout import remediation
from easy_cheese.shared.fanout import run_fan as run_fan_module
from easy_cheese.shared.fanout.scheduler import WaveDecision
from easy_cheese.shared.remediation_artifacts import path_component
from easy_cheese.shared.fanout.remediation_store import (
    StateStoreError,
    initial_state,
    load_state,
    publish_state,
    run_lock_path,
    scope_state_path,
)
from easy_cheese.shared.fanout.press_types import (
    PressGateResult,
    normalize_gate_failures,
)
from easy_cheese.shared.fanout.run_fan import (
    CureDispatchOutcome,
    FanContext,
    FanExecutionOutcome,
    RemediationEventContext,
    ReviewDispatchOutcome,
    run_fan,
)
from easy_cheese.shared.fanout.run_fan import (  # private helpers under test
    _curd_scope,  # pyright: ignore[reportPrivateUsage]
    _drive_scope,  # pyright: ignore[reportPrivateUsage]
)

DIGEST = f"sha256:{'a' * 64}"
PLAN_SCHEMA = "https://schemas.easy-cheese.dev/curd-plan"
RESULT_SCHEMA = "https://schemas.easy-cheese.dev/curd-result"
REVIEW_SCHEMA = "https://schemas.easy-cheese.dev/review-result"
CURE_SCHEMA = "https://schemas.easy-cheese.dev/remediation-cure-observation"


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence-1",
        kind=EvidenceKind.SOURCE,
        artifact=ArtifactRef(
            artifact_id="artifact-1",
            role="source",
            uri="repo://artifacts/artifact-1",
            digest=DIGEST,
            size_bytes=12,
            media_type="text/plain",
        ),
        summary="evidence",
    )


def _curd(curd_id: str, deps: tuple[str, ...] = ()) -> SemanticCurd:
    return SemanticCurd(
        curd_id=curd_id,
        outcome=f"Implement {curd_id}",
        scope=BoundedScope(paths=[f"src/{curd_id}.py"]),
        inputs=(),
        outputs=(f"{curd_id}-out",),
        dependencies=deps,
        criteria=(
            Criterion(
                criterion_id=f"{curd_id}-crit",
                description=f"{curd_id} passes",
                check="the focused regression passes",
            ),
        ),
        lineage=IdentityLineage(IdentityAction.NEW),
    )


def _plan(*curds: SemanticCurd) -> CurdPlan:
    return CurdPlan.signed(
        contract_version=ContractVersion(schema_uri=PLAN_SCHEMA, major="1", minor="0"),
        plan_id="plan-1",
        revision=1,
        objective="exercise the fan orchestrator",
        curds=curds,
    )


def _passed_cook(curd: SemanticCurd) -> CurdResult:
    return CurdResult(
        contract_version=ContractVersion(schema_uri=RESULT_SCHEMA, major="1", minor="0"),
        result_id=f"{curd.curd_id}-result",
        source_plan_ref=SourcePlanRef(plan_id="plan-1", revision=1, digest=DIGEST),
        source_curd_ref=SourceCurdRef(curd_id=curd.curd_id, digest=DIGEST),
        disposition=CurdDisposition.PASSED,
        expected_criterion_ids=(f"{curd.curd_id}-crit",),
        criterion_results=(
            CriterionResult(
                criterion_id=f"{curd.curd_id}-crit",
                disposition=CriterionDisposition.PASSED,
                evidence=(_evidence(),),
            ),
        ),
    )


def _finding(summary: str, severity: ReviewSeverity = ReviewSeverity.MEDIUM) -> ReviewFinding:
    return ReviewFinding(
        finding_id="f1",
        dimension=ReviewDimension.CORRECTNESS,
        severity=severity,
        summary=summary,
        evidence=(_evidence(),),
        fix_cost_now=FixCostNow.SPRAWLING,
        location=None,
    )


def _clean_review() -> ReviewResult:
    return ReviewResult(
        contract_version=ContractVersion(schema_uri=REVIEW_SCHEMA, major="1", minor="0"),
        review_id="review-clean",
        disposition=ReviewDisposition.CLEAN,
        findings=(),
        coverage=(
            ReviewCoverage(target="src/x.py", disposition=CoverageDisposition.COVERED),
        ),
    )


def _findings_review(summary: str) -> ReviewResult:
    return ReviewResult(
        contract_version=ContractVersion(schema_uri=REVIEW_SCHEMA, major="1", minor="0"),
        review_id="review-findings",
        disposition=ReviewDisposition.FINDINGS,
        findings=(_finding(summary),),
        coverage=(
            ReviewCoverage(target="src/x.py", disposition=CoverageDisposition.COVERED),
        ),
    )


def _findings_review_with_summaries(*summaries: str) -> ReviewResult:
    return ReviewResult(
        contract_version=ContractVersion(schema_uri=REVIEW_SCHEMA, major="1", minor="0"),
        review_id=f"review-{len(summaries)}-findings",
        disposition=ReviewDisposition.FINDINGS,
        findings=tuple(
            attrs.evolve(_finding(summary), finding_id=f"f{index}")
            for index, summary in enumerate(summaries, start=1)
        ),
        coverage=(
            ReviewCoverage(target="src/x.py", disposition=CoverageDisposition.COVERED),
        ),
    )


def _apply_all(
    _scope: RemediationScopeKey, locked_selection: tuple[str, ...], _cure_round: int
) -> RemediationCureObservation:
    return RemediationCureObservation(
        contract_version=ContractVersion(schema_uri=CURE_SCHEMA, major="1", minor="0"),
        applied_finding_keys=tuple(locked_selection),
        deferred_finding_keys=(),
        touched_paths=("src/x.py",),
        gate_evidence=(),
        new_gate_failures=(),
    )


AgeScript = Callable[[RemediationScopeKey, int], ReviewResult]


PressScript = Callable[[RemediationScopeKey, int], PressGateResult]


def _press(_scope: RemediationScopeKey, _round: int) -> PressGateResult:
    return PressGateResult(True, "baseline-1", evidence=(_evidence(),))


def _context(
    tmp_path: Path,
    age: AgeScript,
    *,
    cure: Callable[[RemediationScopeKey, tuple[str, ...], int], RemediationCureObservation] = _apply_all,
    cook: Callable[[SemanticCurd], CurdResult] = _passed_cook,
    press: PressScript | None = _press,
) -> FanContext:
    def age_adapter(event: RemediationEventContext) -> ReviewDispatchOutcome:
        return ReviewDispatchOutcome(
            result=age(event.scope, event.round_number), request_digest=DIGEST
        )

    def cure_adapter(event: RemediationEventContext) -> CureDispatchOutcome:
        return CureDispatchOutcome(
            observation=cure(event.scope, event.locked_selection, event.round_number),
            request_digest=DIGEST,
        )

    return FanContext(
        run_id="run-1",
        artifact_directory=tmp_path,
        cook=cook,
        age=age_adapter,
        cure=cure_adapter,
        press=press,
    )


def _scope_state(outcome: FanExecutionOutcome, curd_id: str) -> RemediationState:
    return next(
        state for state in outcome.scope_states.values()
        if state.scope.scope_kind is RemediationScopeKind.CURD
        and state.scope.scope_id == curd_id
    )


class TestHappyPath:
    def test_clean_curds_then_clean_postmerge_is_done(self, tmp_path: Path) -> None:
        # AC-9 (harvest before post-merge) + AC-1: clean before cure completes.
        plan = _plan(_curd("a"), _curd("b", ("a",)))
        outcome = run_fan(plan, _context(tmp_path, lambda scope, r: _clean_review()))
        assert [r.disposition for r in outcome.results] == [
            CurdDisposition.PASSED,
            CurdDisposition.PASSED,
        ]
        assert outcome.postmerge_state is not None
        assert outcome.postmerge_state.disposition is RemediationDisposition.CLEAN
        assert outcome.next_step == "done"

    def test_findings_then_cure_then_clean_completes(self, tmp_path: Path) -> None:
        # AC-2: a productive cure round leads to a clean age and completion.
        plan = _plan(_curd("a"))

        def age(_scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            return _findings_review("drops item") if review_round == 1 else _clean_review()

        outcome = run_fan(plan, _context(tmp_path, age))
        assert outcome.next_step == "done"
        assert outcome.results[0].disposition is CurdDisposition.PASSED


    def test_third_productive_cure_round_reaches_clean(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        cure_calls: list[tuple[int, tuple[str, ...]]] = []

        def age(scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            if scope.scope_id == "postmerge":
                return _clean_review()
            reviews = {
                1: _findings_review_with_summaries("first", "second", "third"),
                2: _findings_review_with_summaries("first", "second"),
                3: _findings_review_with_summaries("first"),
            }
            return reviews.get(review_round, _clean_review())

        def cure(
            _scope: RemediationScopeKey, locked: tuple[str, ...], cure_round: int
        ) -> RemediationCureObservation:
            cure_calls.append((cure_round, locked))
            return _apply_all(_scope, locked, cure_round)

        outcome = run_fan(plan, _context(tmp_path, age, cure=cure))
        state = _scope_state(outcome, "a")
        assert len(cure_calls) == 3
        assert [round_number for round_number, _ in cure_calls] == [1, 2, 3]
        assert [receipt.round_number for receipt in state.receipts] == [1, 2, 3, 4]
        assert [receipt.debt.score for receipt in state.receipts] == [12, 8, 4, 0]
        assert all(receipt.progress for receipt in state.receipts)
        assert state.stagnation_count == 0
        assert state.disposition is RemediationDisposition.CLEAN
        assert state.cursor is RemediationCursor.TERMINAL
        assert outcome.next_step == "done"

    def test_independent_curds_different_round_counts(self, tmp_path: Path) -> None:
        plan = _plan(_curd("one"), _curd("two"))
        cure_calls: dict[str, list[int]] = {"one": [], "two": []}

        def age(scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            if scope.scope_id == "postmerge":
                return _clean_review()
            if scope.scope_id == "one":
                return _findings_review("one defect") if review_round == 1 else _clean_review()
            if review_round == 1:
                return _findings_review_with_summaries("two first", "two second")
            if review_round == 2:
                return _findings_review("two first")
            return _clean_review()

        def cure(
            scope: RemediationScopeKey, locked: tuple[str, ...], cure_round: int
        ) -> RemediationCureObservation:
            cure_calls[scope.scope_id].append(cure_round)
            return _apply_all(scope, locked, cure_round)

        outcome = run_fan(plan, _context(tmp_path, age, cure=cure))
        assert cure_calls == {"one": [1], "two": [1, 2]}
        one = _scope_state(outcome, "one")
        two = _scope_state(outcome, "two")
        assert [receipt.round_number for receipt in one.receipts] == [1, 2]
        assert [receipt.round_number for receipt in two.receipts] == [1, 2, 3]
        assert [receipt.debt.score for receipt in one.receipts] == [4, 0]
        assert [receipt.debt.score for receipt in two.receipts] == [8, 4, 0]
        assert one.scope.scope_id == "one"
        assert two.scope.scope_id == "two"
        assert one.stagnation_count == two.stagnation_count == 0
        assert outcome.next_step == "done"

class TestStall:
    def test_two_non_improving_reviews_stall_to_mold(self, tmp_path: Path) -> None:
        # AC-4 + AC-11: same debt three reviews -> stall -> remediate -> mold.
        plan = _plan(_curd("a"))

        def age(scope: RemediationScopeKey, _review_round: int) -> ReviewResult:
            if scope.scope_id == "postmerge":
                return _clean_review()
            return _findings_review("same defect")

        outcome = run_fan(plan, _context(tmp_path, age))
        assert _scope_state(outcome, "a").disposition is RemediationDisposition.STALLED
        assert outcome.remediation_scopes == ("[\"run-1\",\"curd\",\"a\"]",)
        assert outcome.next_step == "mold"
        assert outcome.results[0].disposition is CurdDisposition.BLOCKED
        ref = outcome.remediation_request_ref
        assert ref is not None
        raw = Path(unquote(urlparse(ref.uri).path)).read_bytes()
        request = validate_contract(
            cast(object, json.loads(raw)), PlannerRequest,
            supported_version_for(PlannerRequest)
        ).value
        assert isinstance(request, PlannerRequest)
        assert request.kind is PlannerRequestKind.REMEDIATE
        assert request.source_plan_ref is not None
        assert request.source_plan_ref.plan_id == plan.plan_id

    def test_round_ceiling_stalls_first_dirty_review(self, tmp_path: Path) -> None:
        # T29: FanContext.max_rounds reaches decide_review.
        plan = _plan(_curd("a"))
        context = attrs.evolve(
            _context(tmp_path, lambda _scope, _round: _findings_review("defect")),
            max_rounds=1,
        )
        outcome = run_fan(plan, context)
        state = _scope_state(outcome, "a")
        assert state.disposition is RemediationDisposition.STALLED
        assert state.receipts[-1].stop_reason == "round ceiling reached"


class TestIncomplete:
    def test_cook_failure_never_presses(self, tmp_path: Path) -> None:
        # AC-12: an incomplete run never writes next: press.
        plan = _plan(_curd("a"), _curd("b", ("a",)))

        def failing_cook(curd: SemanticCurd) -> CurdResult:
            if curd.curd_id == "a":
                return CurdResult(
                    contract_version=ContractVersion(
                        schema_uri=RESULT_SCHEMA, major="1", minor="0"
                    ),
                    result_id="a-result",
                    source_plan_ref=SourcePlanRef(
                        plan_id="plan-1", revision=1, digest=DIGEST
                    ),
                    source_curd_ref=SourceCurdRef(curd_id="a", digest=DIGEST),
                    disposition=CurdDisposition.FAILED,
                    expected_criterion_ids=("a-crit",),
                    criterion_results=(
                        CriterionResult(
                            criterion_id="a-crit",
                            disposition=CriterionDisposition.FAILED,
                            evidence=(_evidence(),),
                        ),
                    ),
                    unresolved_work=("a failed",),
                )
            return _passed_cook(curd)

        outcome = run_fan(
            plan,
            _context(tmp_path, lambda scope, r: _clean_review(), cook=failing_cook),
        )
        assert outcome.next_step != "press"
        # b depends on a, which failed: b is blocked without dispatch (AC-8).
        dispositions = {r.source_curd_ref.curd_id: r.disposition for r in outcome.results}
        assert dispositions["a"] is CurdDisposition.FAILED
        assert dispositions["b"] is CurdDisposition.BLOCKED

    def test_recorded_seven_curd_trace(self, tmp_path: Path) -> None:
        # AC-8 and AC-12: the trace contains one root and six dependent curds.
        curds = [_curd("root")]
        curds.extend(_curd(chr(code), ("root",)) for code in range(ord("b"), ord("h")))
        plan = _plan(*curds)
        cook_calls: list[str] = []

        def failing_root(curd: SemanticCurd) -> CurdResult:
            cook_calls.append(curd.curd_id)
            if curd.curd_id != "root":
                return _passed_cook(curd)
            return CurdResult(
                contract_version=ContractVersion(
                    schema_uri=RESULT_SCHEMA, major="1", minor="0"
                ),
                result_id="root-result",
                source_plan_ref=SourcePlanRef(
                    plan_id="plan-1", revision=1, digest=DIGEST
                ),
                source_curd_ref=SourceCurdRef(curd_id="root", digest=DIGEST),
                disposition=CurdDisposition.FAILED,
                expected_criterion_ids=("root-crit",),
                criterion_results=(
                    CriterionResult(
                        criterion_id="root-crit",
                        disposition=CriterionDisposition.FAILED,
                        evidence=(_evidence(),),
                    ),
                ),
                unresolved_work=("root failed",),
            )

        outcome = run_fan(
            plan,
            _context(tmp_path, lambda _scope, _round: _clean_review(), cook=failing_root),
        )
        dispositions = {r.source_curd_ref.curd_id: r.disposition for r in outcome.results}
        assert dispositions["root"] is CurdDisposition.FAILED
        assert all(dispositions[curd_id] is CurdDisposition.BLOCKED for curd_id in "bcdefg")
        assert cook_calls == ["root"]
        assert outcome.next_step == "mold"
        assert outcome.next_step != "press"

    def test_independent_branch_runs_after_failed_root(self, tmp_path: Path) -> None:
        plan = _plan(_curd("root"), _curd("independent"))
        cook_calls: list[str] = []

        def cook(curd: SemanticCurd) -> CurdResult:
            cook_calls.append(curd.curd_id)
            result = _passed_cook(curd)
            if curd.curd_id != "root":
                return result
            return attrs.evolve(
                result,
                disposition=CurdDisposition.FAILED,
                criterion_results=(attrs.evolve(result.criterion_results[0], disposition=CriterionDisposition.FAILED),),
                unresolved_work=("root failed",),
            )

        outcome = run_fan(
            plan,
            _context(tmp_path, lambda _scope, _round: _clean_review(), cook=cook),
        )
        assert cook_calls == ["root", "independent"]
        dispositions = {item.source_curd_ref.curd_id: item.disposition for item in outcome.results}
        assert dispositions["root"] is CurdDisposition.FAILED
        assert dispositions["independent"] is CurdDisposition.PASSED
        assert outcome.next_step == "mold"

    def test_dirty_postmerge_refuses_done(self, tmp_path: Path) -> None:
        # AC-10: a non-clean terminal post-merge review refuses publication.
        plan = _plan(_curd("a"))

        def age(scope: RemediationScopeKey, _review_round: int) -> ReviewResult:
            if scope.scope_id == "postmerge":
                return _findings_review("merge defect")
            return _clean_review()

        outcome = run_fan(plan, _context(tmp_path, age))
        assert outcome.next_step == "mold"
        assert outcome.postmerge_state is not None
        assert outcome.postmerge_state.disposition is RemediationDisposition.STALLED
        assert outcome.remediation_scopes == ("[\"run-1\",\"postmerge\",\"postmerge\"]",)


class TestResume:
    def test_resume_reloads_persisted_cursor(self, tmp_path: Path) -> None:
        # AC-13 + AC-19 + AC-20: after a cure the persisted cursor is
        # awaiting_review, so resume dispatches Age and never repeats the Cure.
        plan = _plan(_curd("a"))
        scope = _curd_scope("run-1", plan, "a")
        # Build a realistic mid-loop state: one findings review, then a cure that
        # applied its selection, leaving cursor awaiting_review.
        state = initial_state(scope, state_id="a-state")
        review = _findings_review("defect")
        review_ref = _evidence().artifact
        state, _ = remediation.decide_review(state, review, review_ref)
        state, _ = remediation.decide_cure(
            state,
            review_ref,
            state.locked_selection,
            (),
            (),
            ("src/x.py",),
            new_gate_failures=False,
        )
        assert state.cursor is RemediationCursor.AWAITING_REVIEW
        path = scope_state_path(tmp_path, scope)
        _ = publish_state(tmp_path, path, state)
        assert load_state(tmp_path, path).cursor is RemediationCursor.AWAITING_REVIEW

        cure_calls: list[int] = []

        def counting_cure(
            s: RemediationScopeKey, locked: tuple[str, ...], cure_round: int
        ) -> RemediationCureObservation:
            cure_calls.append(cure_round)
            return _apply_all(s, locked, cure_round)

        final = _drive_scope(
            scope,
            "a-state",
            _context(tmp_path, lambda s, r: _clean_review(), cure=counting_cure),
        )
        assert final.disposition is RemediationDisposition.CLEAN
        assert cure_calls == []  # the accepted cure is never repeated

    def test_prepared_cure_intent_blocks_without_applied_work(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        scope = _curd_scope("run-1", plan, "a")
        state = initial_state(scope, state_id="a-state")
        review_ref = _evidence().artifact
        state, _ = remediation.decide_review(
            state, _findings_review("defect"), review_ref
        )
        path = scope_state_path(tmp_path, scope)
        _ = publish_state(tmp_path, path, state)
        context = _context(tmp_path, lambda _scope, _round: _clean_review())
        intent_digest, intent_raw = run_fan_module._cure_intent(state, 1)  # pyright: ignore[reportPrivateUsage]
        intent_path = run_fan_module._cure_intent_path(context, scope, intent_digest)  # pyright: ignore[reportPrivateUsage]
        intent_path.parent.mkdir(parents=True, exist_ok=True)
        _ = intent_path.write_bytes(intent_raw)

        final = _drive_scope(scope, "a-state", context)

        receipt = final.receipts[-1]
        assert final.disposition is RemediationDisposition.BLOCKED
        assert not receipt.applied_finding_keys
        assert receipt.stop_reason is not None
        assert "outcome unknown" in receipt.stop_reason

    def test_completed_cure_intent_replays_without_redispatch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        plan = _plan(_curd("a"))
        scope = _curd_scope("run-1", plan, "a")
        state = initial_state(scope, state_id="a-state")
        review_ref = _evidence().artifact
        state, _ = remediation.decide_review(
            state, _findings_review_with_summaries("defect-1", "defect-2"), review_ref
        )
        path = scope_state_path(tmp_path, scope)
        _ = publish_state(tmp_path, path, state)
        cure_calls: list[int] = []

        def cure(event: RemediationEventContext) -> CureDispatchOutcome:
            cure_calls.append(event.round_number)
            observation = attrs.evolve(
                _apply_all(event.scope, event.locked_selection, event.round_number),
                applied_finding_keys=event.locked_selection[:1],
                deferred_finding_keys=event.locked_selection[1:],
            )
            return CureDispatchOutcome(observation=observation, request_digest=DIGEST)

        context = attrs.evolve(
            _context(tmp_path, lambda _scope, _round: _clean_review()), cure=cure
        )
        original_publish = run_fan_module.publish_state  # pyright: ignore[reportPrivateLocalImportUsage]
        failed = False

        def fail_cure_publish(
            root: Path, target: Path, next_state: RemediationState
        ) -> RemediationState:
            nonlocal failed
            if not failed and next_state.cursor is RemediationCursor.AWAITING_REVIEW:
                failed = True
                raise StateStoreError("simulated crash before state publication")
            return original_publish(root, target, next_state)

        monkeypatch.setattr(run_fan_module, "publish_state", fail_cure_publish)
        with pytest.raises(StateStoreError, match="simulated crash"):
            _ = _drive_scope(scope, "a-state", context)
        assert cure_calls == [1]

        monkeypatch.setattr(run_fan_module, "publish_state", original_publish)
        final = _drive_scope(scope, "a-state", context)
        assert final.disposition is RemediationDisposition.CLEAN
        assert len(final.receipts[0].applied_finding_keys) == 1
        assert cure_calls == [1]

    def test_cleanup_failure_does_not_poison_the_next_cure_round(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _plan(_curd("a"))
        cure_calls: list[int] = []
        review_calls: list[int] = []

        def age(_scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            review_calls.append(review_round)
            return _findings_review("defect") if review_round < 3 else _clean_review()

        def cure(
            _scope: RemediationScopeKey, locked: tuple[str, ...], cure_round: int
        ) -> RemediationCureObservation:
            cure_calls.append(cure_round)
            return _apply_all(_scope, locked, cure_round)

        original_unlink = Path.unlink
        failed = False

        def fail_first_intent_unlink(
            self: Path, *, missing_ok: bool = False
        ) -> None:
            nonlocal failed
            if not failed and self.parent.name == run_fan_module.CURE_INTENT_ROLE:
                failed = True
                raise KeyboardInterrupt("simulated crash")
            original_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_first_intent_unlink)
        with pytest.raises(KeyboardInterrupt, match="simulated crash"):
            _ = _drive_scope(_curd_scope("run-1", plan, "a"), "a-state", _context(tmp_path, age, cure=cure))
        monkeypatch.setattr(Path, "unlink", original_unlink)

        final = _drive_scope(
            _curd_scope("run-1", plan, "a"),
            "a-state",
            _context(tmp_path, age, cure=cure),
        )
        assert final.disposition is RemediationDisposition.CLEAN
        assert review_calls == [1, 2, 3]
        assert cure_calls == [1, 2]

    def test_cleanup_permission_failure_is_best_effort(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _plan(_curd("a"))
        cure_calls: list[int] = []

        def age(_scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            return _findings_review("defect") if review_round == 1 else _clean_review()

        def cure(
            _scope: RemediationScopeKey, locked: tuple[str, ...], cure_round: int
        ) -> RemediationCureObservation:
            cure_calls.append(cure_round)
            return _apply_all(_scope, locked, cure_round)

        original_unlink = Path.unlink
        failed = False

        def fail_intent_unlink(
            self: Path, *, missing_ok: bool = False
        ) -> None:
            nonlocal failed
            if not failed and self.parent.name == run_fan_module.CURE_INTENT_ROLE:
                failed = True
                raise OSError("permission denied")
            original_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_intent_unlink)
        final = _drive_scope(
            _curd_scope("run-1", plan, "a"),
            "a-state",
            _context(tmp_path, age, cure=cure),
        )
        assert final.disposition is RemediationDisposition.CLEAN
        assert cure_calls == [1]

    def test_publish_failure_dispatches_no_next_phase(self, tmp_path: Path) -> None:
        # AC-21: when state cannot be published, run_fan raises and dispatches
        # nothing -- there is no outcome to route forward on.
        plan = _plan(_curd("a"))
        blocker = tmp_path / "blocker"
        _ = blocker.write_text("not a directory")
        age_calls: list[int] = []
        cure_calls: list[int] = []

        def age(_scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            age_calls.append(review_round)
            return _clean_review()

        def cure(
            s: RemediationScopeKey, locked: tuple[str, ...], cure_round: int
        ) -> RemediationCureObservation:
            cure_calls.append(cure_round)
            return _apply_all(s, locked, cure_round)

        context = _context(blocker / "under-a-file", age, cure=cure)
        with pytest.raises(StateStoreError):
            _ = run_fan(plan, context)
        assert age_calls == []
        assert cure_calls == []

    def test_age_sees_durable_awaiting_review_cursor(self, tmp_path: Path) -> None:
        # AC-19: the cursor and the preceding cure receipt are durable before Age.
        plan = _plan(_curd("a"))
        path = scope_state_path(tmp_path, _curd_scope("run-1", plan, "a"))
        seen: list[int] = []

        def age(scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            if scope.scope_id == "postmerge":
                return _clean_review()
            durable = load_state(tmp_path, path)
            assert durable.cursor is RemediationCursor.AWAITING_REVIEW
            assert len(durable.receipts) == review_round - 1
            if review_round == 2:
                assert durable.receipts[-1].cure_result_ref is not None
                assert durable.receipts[-1].applied_finding_keys
            seen.append(review_round)
            return _findings_review("defect") if review_round == 1 else _clean_review()

        outcome = run_fan(plan, _context(tmp_path, age))
        assert seen == [1, 2]
        assert outcome.next_step == "done"

    def test_crash_after_cure_never_repeats_the_cure(self, tmp_path: Path) -> None:
        # B25: a crash between the Cure edit and the state publish resumes at
        # review. The Cure is not dispatched again and the scope does not stall.
        plan = _plan(_curd("a"))
        scope = _curd_scope("run-1", plan, "a")
        cure_calls: list[int] = []

        def age(_scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            return _findings_review("defect") if review_round == 1 else _clean_review()

        def crashing_cure(
            _s: RemediationScopeKey, _locked: tuple[str, ...], cure_round: int
        ) -> RemediationCureObservation:
            cure_calls.append(cure_round)
            raise AssertionError("crash after the tree edit")

        with pytest.raises(AssertionError):
            _ = _drive_scope(scope, "a-state", _context(tmp_path, age, cure=crashing_cure))
        path = scope_state_path(tmp_path, scope)
        assert load_state(tmp_path, path).cursor is RemediationCursor.AWAITING_CURE

        def redispatched_cure(
            _s: RemediationScopeKey, _locked: tuple[str, ...], _round: int
        ) -> RemediationCureObservation:
            raise AssertionError("redispatched")

        final = _drive_scope(
            scope, "a-state", _context(tmp_path, age, cure=redispatched_cure)
        )
        assert cure_calls == [1]
        assert final.disposition is RemediationDisposition.BLOCKED
        assert not final.receipts[-1].applied_finding_keys
        assert final.receipts[-1].stop_reason is not None
        assert "outcome unknown" in final.receipts[-1].stop_reason
        assert not list(path.parent.glob("cure-intent/*.json"))

    def test_stale_plan_digest_stops_before_dispatch(self, tmp_path: Path) -> None:
        # AC-14: a resumed state from another plan digest stops before dispatch.
        plan = _plan(_curd("a"))
        current_scope = _curd_scope("run-1", plan, "a")
        stale_scope = RemediationScopeKey(
            run_id="run-1",
            source_plan_ref=SourcePlanRef(
                plan_id="plan-1", revision=1, digest=f"sha256:{'b' * 64}"
            ),
            scope_kind=current_scope.scope_kind,
            scope_id="a",
        )
        path = scope_state_path(tmp_path, current_scope)
        _ = publish_state(tmp_path, path, initial_state(stale_scope, state_id="a-state"))
        with pytest.raises(StateStoreError):
            _ = _drive_scope(
                current_scope,
                "a-state",
                _context(tmp_path, lambda s, r: _clean_review()),
            )


class TestCallbackFailures:
    def test_age_failure_publishes_blocked_scope_and_routes_mold(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))

        def fail_age(_scope: RemediationScopeKey, _round: int) -> ReviewResult:
            raise RuntimeError("review unavailable")

        outcome = run_fan(plan, _context(tmp_path, fail_age))
        state = _scope_state(outcome, "a")
        assert state.disposition is RemediationDisposition.BLOCKED
        assert state.cursor is RemediationCursor.TERMINAL
        assert outcome.next_step == "mold"

    def test_cure_failure_publishes_blocked_scope_and_routes_mold(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))

        def fail_cure(
            _scope: RemediationScopeKey,
            _locked: tuple[str, ...],
            _round: int,
        ) -> RemediationCureObservation:
            raise RuntimeError("diagnosis unavailable")

        outcome = run_fan(
            plan,
            _context(
                tmp_path,
                lambda _scope, _round: _findings_review("needs cure"),
                cure=fail_cure,
            ),
        )
        state = _scope_state(outcome, "a")
        assert state.disposition is RemediationDisposition.STALLED
        assert state.cursor is RemediationCursor.TERMINAL
        assert outcome.next_step == "mold"


class TestPostmergePress:
    def test_press_precedes_postmerge_age_and_skips_curds(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        events: list[str] = []

        def press(scope: RemediationScopeKey, _round: int) -> PressGateResult:
            events.append(f"press:{scope.scope_id}")
            return PressGateResult(True, "baseline-1", evidence=(_evidence(),))

        def age(scope: RemediationScopeKey, _round: int) -> ReviewResult:
            events.append(f"age:{scope.scope_id}")
            return _clean_review()

        outcome = run_fan(plan, _context(tmp_path, age, press=press))
        assert outcome.next_step == "done"
        assert "press:a" not in events
        assert events.index("press:postmerge") < events.index("age:postmerge")

    def test_absent_press_blocks_postmerge(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        outcome = run_fan(
            plan,
            _context(tmp_path, lambda _scope, _round: _clean_review(), press=None),
        )
        assert outcome.next_step == "mold"
        assert outcome.postmerge_state is not None
        assert outcome.postmerge_state.disposition is RemediationDisposition.BLOCKED
        assert len(outcome.stop_evidence_refs) == 1
        assert outcome.stop_evidence_refs[0].role == "press-stop"


    def test_postmerge_cure_receipt_keeps_both_gate_runs(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))

        def press(_scope: RemediationScopeKey, gate_round: int) -> PressGateResult:
            return PressGateResult(True, "baseline-1", evidence=(attrs.evolve(_evidence(), evidence_id=f"gate-{gate_round}"),))

        def age(scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            if scope.scope_id == "postmerge" and review_round == 1:
                return _findings_review("merge defect")
            return _clean_review()

        outcome = run_fan(plan, _context(tmp_path, age, press=press))
        assert outcome.postmerge_state is not None
        gate_ids = {
            item.evidence_id
            for item in outcome.postmerge_state.receipts[-2].gate_evidence
        }
        assert {"gate-1", "gate-2"} <= gate_ids


    def test_fresh_postmerge_debt_gets_own_cure_receipt(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        age_calls: list[str] = []
        cure_calls: list[str] = []

        def age(scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            age_calls.append(scope.scope_id)
            if scope.scope_id == "postmerge" and review_round == 1:
                return _findings_review("fresh merge defect")
            return _clean_review()

        def cure(
            scope: RemediationScopeKey, locked: tuple[str, ...], cure_round: int
        ) -> RemediationCureObservation:
            cure_calls.append(scope.scope_id)
            return _apply_all(scope, locked, cure_round)

        outcome = run_fan(plan, _context(tmp_path, age, cure=cure))
        assert age_calls == ["a", "postmerge", "postmerge"]
        assert cure_calls == ["postmerge"]
        assert outcome.postmerge_state is not None
        postmerge = outcome.postmerge_state
        assert len(postmerge.receipts) == 2
        assert postmerge.receipts[0].cure_result_ref is not None
        assert postmerge.receipts[0].selected_finding_keys
        assert postmerge.receipts[1].selected_finding_keys == ()
        state = _scope_state(outcome, "a")
        assert len(state.receipts) == 1
        assert state.receipts[0].cure_result_ref is None
        assert outcome.next_step == "done"

class TestRecordedResume:
    def test_recorded_passed_curd_resumes_age_without_cook(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        scope = _curd_scope("run-1", plan, "a")
        _ = publish_state(
            tmp_path, scope_state_path(tmp_path, scope), initial_state(scope, state_id="a-state")
        )
        age_calls: list[str] = []

        def age(scope_key: RemediationScopeKey, _round: int) -> ReviewResult:
            age_calls.append(scope_key.scope_id)
            return _clean_review()

        def forbidden_cook(_curd: SemanticCurd) -> CurdResult:
            raise AssertionError("resume must not redispatch Cook")

        outcome = run_fan(
            plan,
            _context(tmp_path, age, cook=forbidden_cook),
            results={"a": _passed_cook(_curd("a"))},
        )
        assert outcome.next_step == "done"
        assert age_calls == ["a", "postmerge"]

    def test_recorded_passed_curd_without_state_runs_age(self, tmp_path: Path) -> None:
        # F1: a recorded PASSED result never skips its remediation review.
        plan = _plan(_curd("a"))
        age_calls: list[str] = []

        def age(scope_key: RemediationScopeKey, _round: int) -> ReviewResult:
            age_calls.append(scope_key.scope_id)
            return _clean_review()

        outcome = run_fan(
            plan, _context(tmp_path, age), results={"a": _passed_cook(_curd("a"))}
        )
        assert age_calls == ["a", "postmerge"]
        assert _scope_state(outcome, "a").cursor is RemediationCursor.TERMINAL
        assert len(_scope_state(outcome, "a").receipts) == 1

    def test_resumed_stall_is_reported_for_remediation(self, tmp_path: Path) -> None:
        # F26: resume and fresh runs report a stalled scope the same way.
        plan = _plan(_curd("a"))
        scope = _curd_scope("run-1", plan, "a")
        _ = publish_state(
            tmp_path, scope_state_path(tmp_path, scope), initial_state(scope, state_id="a-state")
        )
        outcome = run_fan(
            plan,
            _context(tmp_path, lambda _scope, _round: _findings_review("same defect")),
            results={"a": _passed_cook(_curd("a"))},
        )
        assert _scope_state(outcome, "a").disposition is RemediationDisposition.STALLED
        assert outcome.remediation_scopes == ("[\"run-1\",\"curd\",\"a\"]",)
        assert outcome.results[0].disposition is CurdDisposition.BLOCKED

    def test_unknown_recorded_curd_is_rejected(self, tmp_path: Path) -> None:
        # L4: a seeded result outside the plan fails with a clear error.
        plan = _plan(_curd("a"))
        with pytest.raises(ValueError, match="unknown curd ids: ghost"):
            _ = run_fan(
                plan,
                _context(tmp_path, lambda _scope, _round: _clean_review()),
                results={"ghost": _passed_cook(_curd("ghost"))},
            )


def _artifact_payloads(tmp_path: Path, role: str) -> dict[str, dict[str, object]]:
    root = tmp_path / "remediation" / path_component("run-1") / path_component(role)
    return {path.name: json.loads(path.read_text()) for path in sorted(root.glob("*.json"))}


def _postmerge_findings_once(scope: RemediationScopeKey, review_round: int) -> ReviewResult:
    if scope.scope_id == "postmerge" and review_round == 1:
        return _findings_review("merge defect")
    return _clean_review()


class TestPressGateHardening:
    def test_press_callback_failure_keeps_cure_observation(self, tmp_path: Path) -> None:
        # F5: a Press fault blocks the scope and keeps the Cure observation.
        plan = _plan(_curd("a"))

        def press(_scope: RemediationScopeKey, gate_round: int) -> PressGateResult:
            if gate_round > 1:
                raise RuntimeError("gate runner crashed")
            return PressGateResult(True, "baseline-1", evidence=(_evidence(),))

        outcome = run_fan(plan, _context(tmp_path, _postmerge_findings_once, press=press))
        assert outcome.postmerge_state is not None
        receipt = outcome.postmerge_state.receipts[-1]
        assert outcome.postmerge_state.disposition is RemediationDisposition.BLOCKED
        assert receipt.applied_finding_keys == receipt.selected_finding_keys != ()
        assert receipt.touched_paths == ("src/x.py",)
        cures = _artifact_payloads(tmp_path, "cure-result")
        failures = [item["new_gate_failures"] for item in cures.values()]
        assert failures == [["press-callback-failed:RuntimeError"]]
        faults = _artifact_payloads(tmp_path, "callback-fault")
        assert [item["source"] for item in faults.values()] == ["press-callback"]

    def test_free_text_press_failure_blocks_postmerge(self, tmp_path: Path) -> None:
        # F19: free-text gate names block the scope instead of stalling it.
        plan = _plan(_curd("a"))

        def press(_scope: RemediationScopeKey, gate_round: int) -> PressGateResult:
            if gate_round == 1:
                return PressGateResult(True, "baseline-1", evidence=(_evidence(),))
            return PressGateResult(
                False, "baseline-1", new_failures=("pytest: 3 failed", "pytest: 3 failed")
            )

        outcome = run_fan(plan, _context(tmp_path, _postmerge_findings_once, press=press))
        assert outcome.postmerge_state is not None
        assert outcome.postmerge_state.disposition is RemediationDisposition.BLOCKED
        cures = _artifact_payloads(tmp_path, "cure-result")
        failures = [item["new_gate_failures"] for item in cures.values()]
        assert failures == [["pytest:-3-failed", "press-gate-failed"]]

    def test_normalize_gate_failures_slugs_and_deduplicates(self) -> None:
        names = ("pytest: 3 failed", "  !!", "ok-gate", "pytest: 3 failed", "x" * 200)
        assert normalize_gate_failures(names) == (
            "pytest:-3-failed",
            "gate-failure",
            "ok-gate",
            "x" * 128,
        )

    def test_gate_evidence_is_unique_by_id(self, tmp_path: Path) -> None:
        # F37: repeated gate evidence appears once in the Cure receipt.
        plan = _plan(_curd("a"))
        outcome = run_fan(plan, _context(tmp_path, _postmerge_findings_once))
        assert outcome.postmerge_state is not None
        ids = [item.evidence_id for item in outcome.postmerge_state.receipts[-2].gate_evidence]
        assert ids == ["evidence-1"]


class TestCallbackFaults:
    @pytest.mark.parametrize("error_type", [TypeError, AttributeError, NameError, AssertionError, KeyError])
    def test_host_programming_error_propagates(
        self, tmp_path: Path, error_type: type[Exception]
    ) -> None:
        # F30: a host bug never becomes a blocked scope.
        plan = _plan(_curd("a"))

        def buggy_age(_scope: RemediationScopeKey, _round: int) -> ReviewResult:
            raise error_type("host bug")

        with pytest.raises(error_type):
            _ = run_fan(plan, _context(tmp_path, buggy_age))

    def test_blocked_review_records_error_type_and_traceback(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))

        def fail_age(_scope: RemediationScopeKey, _round: int) -> ReviewResult:
            raise RuntimeError("review unavailable")

        _ = run_fan(plan, _context(tmp_path, fail_age))
        (review,) = _artifact_payloads(tmp_path, "review").values()
        reason = str(review["reason"])
        assert "RuntimeError: review unavailable" in reason
        assert "fail_age" in reason
        assert len(reason) <= 2048

    def test_cure_fault_artifact_names_the_cure_callback(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))

        def fail_cure(
            _scope: RemediationScopeKey, _locked: tuple[str, ...], _round: int
        ) -> RemediationCureObservation:
            raise RuntimeError("diagnosis unavailable")

        _ = run_fan(
            plan,
            _context(tmp_path, lambda _scope, _round: _findings_review("needs cure"), cure=fail_cure),
        )
        (fault,) = _artifact_payloads(tmp_path, "callback-fault").values()
        assert fault["source"] == "cure-callback"
        assert fault["error_type"] == "RuntimeError"
        assert "fail_cure" in str(fault["reason"])


class TestRecording:
    def test_result_sink_replaces_checkpoint_sink(self, tmp_path: Path) -> None:
        # F35: the host result sink already writes the checkpoint.
        plan = _plan(_curd("a"), _curd("b", ("a",)))
        recorded: list[str] = []
        checkpoints: list[int] = []
        def record_result(result: CurdResult) -> None:
            recorded.append(result.source_curd_ref.curd_id)

        context = attrs.evolve(
            _context(tmp_path, lambda _scope, _round: _clean_review()),
            result_sink=record_result,
            checkpoint_sink=lambda: checkpoints.append(1),
        )
        _ = run_fan(plan, context)
        assert recorded == ["a", "b"]
        assert checkpoints == []

    def test_checkpoint_sink_runs_without_result_sink(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"), _curd("b", ("a",)))
        checkpoints: list[int] = []
        context = attrs.evolve(
            _context(tmp_path, lambda _scope, _round: _clean_review()),
            checkpoint_sink=lambda: checkpoints.append(1),
        )
        _ = run_fan(plan, context)
        assert checkpoints == [1, 1]

    def test_artifact_names_carry_request_digest(self, tmp_path: Path) -> None:
        # L3: a retried round with a new request never overwrites an artifact.
        plan = _plan(_curd("a"))

        def age(_scope: RemediationScopeKey, review_round: int) -> ReviewResult:
            return _findings_review("defect") if review_round == 1 else _clean_review()

        _ = run_fan(plan, _context(tmp_path, age, press=None))
        suffix = "a" * 12
        assert sorted(_artifact_payloads(tmp_path, "review")) == sorted(
            f"{path_component(name)}.json"
            for name in (f"a-review-1-{suffix}", f"a-review-2-{suffix}")
        )
        assert list(_artifact_payloads(tmp_path, "cure-result")) == [
            f"{path_component(f'a-cure-1-{suffix}')}.json"
        ]

    def test_stuck_schedule_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # L1: a wave with only waiting curds is an error, never a silent stop.
        plan = _plan(_curd("a"))
        stuck = WaveDecision(ready=(), blocked=(), remaining=("a",), complete=False)
        def stuck_schedule(*_args: object, **_kwargs: object) -> WaveDecision:
            return stuck

        monkeypatch.setattr(run_fan_module, "schedule_wave", stuck_schedule)
        with pytest.raises(RuntimeError, match="no schedulable curd.*: a"):
            _ = run_fan(plan, _context(tmp_path, lambda _scope, _round: _clean_review()))


class TestRunLock:
    def test_second_run_fails_while_lock_is_held(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        lock = run_lock_path(tmp_path, "run-1")
        errors: list[str] = []

        def cook(curd: SemanticCurd) -> CurdResult:
            assert lock.exists()
            with pytest.raises(StateStoreError) as caught:
                _ = run_fan(plan, _context(tmp_path, lambda _s, _r: _clean_review()))
            errors.append(str(caught.value))
            return _passed_cook(curd)

        outcome = run_fan(plan, _context(tmp_path, lambda _s, _r: _clean_review(), cook=cook))
        assert outcome.next_step == "done"
        assert len(errors) == 1 and str(lock) in errors[0]

    def test_lock_is_released_after_success(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        _ = run_fan(plan, _context(tmp_path, lambda _s, _r: _clean_review()))
        assert run_lock_path(tmp_path, "run-1").exists()

    def test_lock_is_released_after_exception(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))

        def cook(_curd: SemanticCurd) -> CurdResult:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            _ = run_fan(plan, _context(tmp_path, lambda _s, _r: _clean_review(), cook=cook))
        assert run_lock_path(tmp_path, "run-1").exists()

    def test_preexisting_lock_file_does_not_block_without_os_holder(self, tmp_path: Path) -> None:
        plan = _plan(_curd("a"))
        lock = run_lock_path(tmp_path, "run-1")
        lock.parent.mkdir(parents=True)
        _ = lock.write_text("stale pid text")
        outcome = run_fan(plan, _context(tmp_path, lambda _s, _r: _clean_review()))
        assert outcome.next_step == "done"
        assert lock.exists()
