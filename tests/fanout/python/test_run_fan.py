"""Integration tests for the fan remediation orchestrator (Sec6/7/9/11/12).

Drives `run_fan` and `_drive_scope` with scripted fake Cook/Age/Cure workers to
cover AC-9..14 and AC-19..21.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
    ReviewCoverage,
    ReviewDimension,
    ReviewDisposition,
    ReviewFinding,
    ReviewResult,
    ReviewSeverity,
    SemanticCurd,
    SourceCurdRef,
    SourcePlanRef,
)

from easy_cheese.shared.fanout import remediation
from easy_cheese.shared.fanout.remediation_store import (
    StateStoreError,
    initial_state,
    load_state,
    publish_state,
    scope_state_path,
)
from easy_cheese.shared.fanout.run_fan import FanContext, run_fan
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


def _context(
    tmp_path: Path,
    age: AgeScript,
    *,
    cure: object = _apply_all,
    cook: object = _passed_cook,
) -> FanContext:
    return FanContext(
        run_id="run-1",
        artifact_directory=tmp_path,
        cook=cook,  # pyright: ignore[reportArgumentType]
        age=age,
        cure=cure,  # pyright: ignore[reportArgumentType]
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


class TestStall:
    def test_two_non_improving_reviews_stall_to_mold(self, tmp_path: Path) -> None:
        # AC-4 + AC-11: same debt three reviews -> stall -> remediate -> mold.
        plan = _plan(_curd("a"))

        def age(scope: RemediationScopeKey, _review_round: int) -> ReviewResult:
            if scope.scope_id == "postmerge":
                return _clean_review()
            return _findings_review("same defect")

        outcome = run_fan(plan, _context(tmp_path, age))
        assert outcome.scope_states["a"].disposition is RemediationDisposition.STALLED
        assert outcome.remediation_scopes == ("curd:a",)
        assert outcome.next_step == "mold"
        assert outcome.results[0].disposition is CurdDisposition.BLOCKED


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

    def test_dirty_postmerge_refuses_done(self, tmp_path: Path) -> None:
        # AC-10: a non-clean terminal post-merge review refuses publication.
        plan = _plan(_curd("a"))

        def age(scope: RemediationScopeKey, _review_round: int) -> ReviewResult:
            if scope.scope_id == "postmerge":
                return _findings_review("merge defect")
            return _clean_review()

        outcome = run_fan(plan, _context(tmp_path, age))
        assert outcome.next_step != "done"
        assert outcome.postmerge_state is not None
        assert (
            outcome.postmerge_state.disposition is not RemediationDisposition.CLEAN
        )


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
        _ = publish_state(path, state)
        assert load_state(path).cursor is RemediationCursor.AWAITING_REVIEW

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

    def test_publish_failure_dispatches_no_next_phase(self, tmp_path: Path) -> None:
        # AC-21: when state cannot be published, run_fan raises and dispatches
        # nothing -- there is no outcome to route forward on.
        plan = _plan(_curd("a"))
        blocker = tmp_path / "blocker"
        _ = blocker.write_text("not a directory")
        context = _context(blocker / "under-a-file", lambda s, r: _clean_review())
        with pytest.raises(StateStoreError):
            _ = run_fan(plan, context)

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
        _ = publish_state(path, initial_state(stale_scope, state_id="a-state"))
        with pytest.raises(StateStoreError):
            _ = _drive_scope(
                current_scope,
                "a-state",
                _context(tmp_path, lambda s, r: _clean_review()),
            )
