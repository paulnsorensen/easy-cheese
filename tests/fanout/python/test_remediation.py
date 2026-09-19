"""Unit tests for the pure remediation decision core (mini-spec Sec4/Sec5)."""
from __future__ import annotations

from easy_cheese_schemas import (
    ArtifactRef,
    ContractVersion,
    EvidenceKind,
    EvidenceRef,
    FixCostNow,
    ProgressReceipt,
    RemediationCursor,
    RemediationDisposition,
    RemediationScopeKey,
    RemediationScopeKind,
    RemediationState,
    ReviewDebt,
    ReviewDimension,
    ReviewDisposition,
    ReviewFinding,
    ReviewResult,
    ReviewSeverity,
    SourceLocation,
    SourcePlanRef,
)

from easy_cheese.shared.fanout import remediation

DIGEST = f"sha256:{'a' * 64}"
REVIEW_SCHEMA = "https://schemas.easy-cheese.dev/review-result"


def _artifact(artifact_id: str = "artifact-1") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        role="source",
        uri=f"repo://artifacts/{artifact_id}",
        digest=DIGEST,
        size_bytes=12,
        media_type="text/plain",
    )


def _evidence(evidence_id: str = "evidence-1") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        kind=EvidenceKind.SOURCE,
        artifact=_artifact(),
        summary="Grounded source evidence",
    )


def _finding(
    finding_id: str = "f1",
    severity: ReviewSeverity = ReviewSeverity.HIGH,
    fix_cost_now: FixCostNow = FixCostNow.SPRAWLING,
    summary: str = "The parser drops the final item",
    path: str | None = "src/parser.py",
) -> ReviewFinding:
    location = (
        SourceLocation(artifact_id="artifact-1", path=path, start_line=1, end_line=2)
        if path is not None
        else None
    )
    return ReviewFinding(
        finding_id=finding_id,
        dimension=ReviewDimension.CORRECTNESS,
        severity=severity,
        summary=summary,
        evidence=[_evidence()],
        fix_cost_now=fix_cost_now,
        location=location,
    )


def _review(
    findings: list[ReviewFinding] | None = None,
    disposition: ReviewDisposition = ReviewDisposition.FINDINGS,
    review_id: str = "review-1",
    reason: str | None = None,
) -> ReviewResult:
    findings = [] if findings is None else findings
    coverage = []
    if disposition in (ReviewDisposition.CLEAN, ReviewDisposition.FINDINGS):
        from easy_cheese_schemas import CoverageDisposition, ReviewCoverage

        coverage = [
            ReviewCoverage(target="src/parser.py", disposition=CoverageDisposition.COVERED)
        ]
    return ReviewResult(
        contract_version=ContractVersion(schema_uri=REVIEW_SCHEMA, major="1", minor="0"),
        review_id=review_id,
        disposition=disposition,
        findings=findings,
        coverage=coverage,
        reason=reason,
    )


def _state(
    *,
    cursor: RemediationCursor = RemediationCursor.AWAITING_REVIEW,
    disposition: RemediationDisposition = RemediationDisposition.ACTIVE,
    locked_selection: tuple[str, ...] = (),
    best_debt: ReviewDebt | None = None,
    stagnation_count: int = 0,
    receipts: tuple[ProgressReceipt, ...] = (),
    pending_cure_result_ref: ArtifactRef | None = None,
) -> RemediationState:
    return RemediationState(
        contract_version=ContractVersion(
            schema_uri="https://schemas.easy-cheese.dev/remediation-state", major="1", minor="0"
        ),
        state_id="state-1",
        scope=RemediationScopeKey(
            run_id="run-1",
            source_plan_ref=SourcePlanRef(plan_id="plan-1", revision=1, digest=DIGEST),
            scope_kind=RemediationScopeKind.CURD,
            scope_id="curd-1",
        ),
        cursor=cursor,
        disposition=disposition,
        locked_selection=locked_selection,
        pending_cure_result_ref=pending_cure_result_ref,
        best_debt=best_debt,
        stagnation_count=stagnation_count,
        receipts=receipts,
    )


class TestFindingKey:
    def test_deterministic_for_identical_normalized_content(self) -> None:
        a = _finding(summary="  The Parser Drops   the final item ")
        b = _finding(summary="the parser drops the final item")
        assert remediation.finding_key(a) == remediation.finding_key(b)

    def test_no_location_uses_empty_path_segment(self) -> None:
        with_loc = _finding(path="src/parser.py")
        without_loc = _finding(path=None)
        assert remediation.finding_key(with_loc) != remediation.finding_key(without_loc)

    def test_severity_excluded_from_key(self) -> None:
        low = _finding(severity=ReviewSeverity.LOW, fix_cost_now=FixCostNow.CONTAINED)
        high = _finding(severity=ReviewSeverity.HIGH)
        assert remediation.finding_key(low) == remediation.finding_key(high)


class TestComputeDebt:
    def test_weights_16_8_4_1(self) -> None:
        findings = [
            _finding("f1", ReviewSeverity.CRITICAL),
            _finding("f2", ReviewSeverity.HIGH),
            _finding("f3", ReviewSeverity.MEDIUM),
            _finding("f4", ReviewSeverity.LOW, FixCostNow.CONTAINED),
        ]
        debt = remediation.compute_debt(tuple(findings))
        assert debt.score == 16 + 8 + 4 + 1

    def test_non_contained_low_excluded(self) -> None:
        findings = [_finding("f1", ReviewSeverity.LOW, FixCostNow.SPRAWLING)]
        debt = remediation.compute_debt(tuple(findings))
        assert debt.score == 0
        assert debt.contained_low == 0


class TestLockedSelectionAndDeferred:
    def test_medium_plus_floor_and_contained_low_carve_out(self) -> None:
        findings = [
            _finding("f1", ReviewSeverity.MEDIUM),
            _finding("f2", ReviewSeverity.LOW, FixCostNow.CONTAINED),
            _finding("f3", ReviewSeverity.LOW, FixCostNow.SPRAWLING),
        ]
        selected, deferred = remediation.locked_selection_and_deferred(tuple(findings))
        assert len(selected) == 2
        assert len(deferred) == 1
        assert remediation.finding_key(findings[2]) in deferred


class TestIsAutomationClean:
    def test_only_non_contained_low_is_clean(self) -> None:
        findings = [_finding("f1", ReviewSeverity.LOW, FixCostNow.SPRAWLING)]
        assert remediation.is_automation_clean(tuple(findings)) is True

    def test_contained_low_blocks_clean(self) -> None:
        findings = [_finding("f1", ReviewSeverity.LOW, FixCostNow.CONTAINED)]
        assert remediation.is_automation_clean(tuple(findings)) is False

    def test_no_findings_is_clean(self) -> None:
        assert remediation.is_automation_clean(()) is True


class TestDecideReviewCleanAndBlocked:
    def test_clean_before_cure_completes(self) -> None:
        # AC-1
        state = _state()
        review = _review([], disposition=ReviewDisposition.CLEAN)
        next_state, verdict = remediation.decide_review(state, review, _artifact())
        assert verdict["action"] == "complete"
        assert next_state.disposition is RemediationDisposition.CLEAN
        assert next_state.cursor is RemediationCursor.TERMINAL

    def test_only_non_contained_low_completes_without_cure(self) -> None:
        # AC-18
        state = _state()
        review = _review([_finding("f1", ReviewSeverity.LOW, FixCostNow.SPRAWLING)])
        _next_state, verdict = remediation.decide_review(state, review, _artifact())
        assert verdict["action"] == "complete"

    def test_blocked_disposition_stops_immediately(self) -> None:
        state = _state()
        review = _review([], disposition=ReviewDisposition.BLOCKED, reason="executor died")
        next_state, verdict = remediation.decide_review(state, review, _artifact())
        assert verdict["action"] == "blocked"
        assert next_state.disposition is RemediationDisposition.BLOCKED


class TestDecideReviewStagnation:
    def test_initial_review_sets_best_debt_no_stagnation(self) -> None:
        # AC-8/scenario 8: fresh state, best_debt is None
        state = _state()
        review = _review([_finding("f1", ReviewSeverity.HIGH)])
        next_state, verdict = remediation.decide_review(state, review, _artifact())
        assert verdict["action"] == "cure"
        assert next_state.stagnation_count == 0
        assert next_state.best_debt is not None and next_state.best_debt.score == 8

    def test_new_best_after_cure_continues(self) -> None:
        # AC-2
        debt = remediation.compute_debt((_finding("f0", ReviewSeverity.HIGH),))
        state = _state(cursor=RemediationCursor.AWAITING_REVIEW, best_debt=debt, stagnation_count=0)
        review = _review([_finding("f1", ReviewSeverity.MEDIUM)])
        _next_state, verdict = remediation.decide_review(state, review, _artifact())
        assert verdict["action"] == "cure"
        assert verdict["progress"] is True

    def test_one_discovery_grace_before_stall(self) -> None:
        # AC-3
        debt = remediation.compute_debt((_finding("f0", ReviewSeverity.MEDIUM),))
        state = _state(best_debt=debt, stagnation_count=0)
        review = _review([_finding("f1", ReviewSeverity.MEDIUM)])
        next_state, verdict = remediation.decide_review(state, review, _artifact())
        assert verdict["action"] == "cure"
        assert next_state.stagnation_count == 1

    def test_two_strikes_stalls(self) -> None:
        # AC-4
        debt = remediation.compute_debt((_finding("f0", ReviewSeverity.MEDIUM),))
        state = _state(best_debt=debt, stagnation_count=1)
        review = _review([_finding("f1", ReviewSeverity.MEDIUM)])
        next_state, verdict = remediation.decide_review(state, review, _artifact())
        assert verdict["action"] == "remediate"
        assert next_state.disposition is RemediationDisposition.STALLED
        assert next_state.cursor is RemediationCursor.TERMINAL


class TestDecideReviewHostDerivation:
    def test_review_result_carries_no_round_or_score_field(self) -> None:
        # AC-17: ReviewResult/ReviewFinding expose no round/score/clean field
        # for an agent to author; decide_review only ever reads disposition
        # and findings.
        review = _review([_finding("f1", ReviewSeverity.HIGH)])
        import attrs

        field_names = set(attrs.fields_dict(type(review)))
        assert field_names == {
            "contract_version",
            "review_id",
            "disposition",
            "findings",
            "coverage",
            "reason",
        }


class TestDecideCure:
    def _reviewed_state(self, selection: tuple[str, ...]) -> RemediationState:
        from easy_cheese_schemas import ProgressReceipt, ReviewDebt

        receipt = ProgressReceipt(
            round_number=1,
            review_ref=_artifact(),
            preceding_cure_result_ref=None,
            selected_finding_keys=selection,
            applied_finding_keys=(),
            deferred_finding_keys=(),
            debt=ReviewDebt.compute(critical=0, high=1, medium=0, contained_low=0),
            gate_evidence=[],
            touched_paths=[],
            progress=True,
            stop_reason=None,
        )
        return _state(
            cursor=RemediationCursor.AWAITING_CURE,
            locked_selection=selection,
            receipts=(receipt,),
        )

    def test_zero_applied_stops_immediately(self) -> None:
        # AC-5 / regression scenario 3
        state = self._reviewed_state((DIGEST,))
        next_state, verdict = remediation.decide_cure(
            state, _artifact("cure-1"), (), (DIGEST,), (), (), new_gate_failures=False
        )
        assert verdict["action"] == "remediate"
        assert next_state.disposition is RemediationDisposition.STALLED

    def test_new_gate_failure_blocks(self) -> None:
        state = self._reviewed_state((DIGEST,))
        _next_state, verdict = remediation.decide_cure(
            state, _artifact("cure-1"), (DIGEST,), (), (), (), new_gate_failures=True
        )
        assert verdict["action"] == "blocked"

    def test_successful_cure_advances_to_age(self) -> None:
        state = self._reviewed_state((DIGEST,))
        next_state, verdict = remediation.decide_cure(
            state, _artifact("cure-1"), (DIGEST,), (), (), ("src/x.py",), new_gate_failures=False
        )
        assert verdict["action"] == "age"
        assert next_state.cursor is RemediationCursor.AWAITING_REVIEW
        assert next_state.pending_cure_result_ref is not None
        assert next_state.pending_cure_result_ref.artifact_id == "cure-1"

    def test_partition_violation_raises(self) -> None:
        state = self._reviewed_state((DIGEST,))
        try:
            _ = remediation.decide_cure(
                state, _artifact("cure-1"), (), (), (), (), new_gate_failures=False
            )
        except ValueError as exc:
            assert "partition" in str(exc)
        else:
            raise AssertionError("expected ValueError")
