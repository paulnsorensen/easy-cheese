"""CLI contract tests for the `remediation-decision` bundle command.

Exercises both events end-to-end through the built cook.pyz bundle: a review
event, the review -> cure chain, the zero-applied remediate stop, and the
fail-closed error paths (mini-spec Sec13, AC-1..AC-5, AC-21).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from easy_cheese.shared.fanout.remediation_store import load_state
from easy_cheese_schemas import (
    ArtifactRef,
    ContractVersion,
    CoverageDisposition,
    EvidenceKind,
    EvidenceRef,
    FixCostNow,
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
    SourceLocation,
    SourcePlanRef,
    canonical_bytes,
)

BUNDLE = Path(__file__).resolve().parents[3] / "skills/cook/scripts/cook.pyz"
DIGEST = f"sha256:{'a' * 64}"
CURE_SCHEMA = "https://schemas.easy-cheese.dev/remediation-cure-observation"
REVIEW_SCHEMA = "https://schemas.easy-cheese.dev/review-result"
STATE_SCHEMA = "https://schemas.easy-cheese.dev/remediation-state"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "remediation_decision", *args],
        capture_output=True,
        text=True,
    )


def _write(path: Path, contract: object) -> Path:
    _ = path.write_bytes(canonical_bytes(contract))
    return path


def _artifact() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="artifact-1",
        role="source",
        uri="repo://artifacts/artifact-1",
        digest=DIGEST,
        size_bytes=12,
        media_type="text/plain",
    )


def _finding(
    severity: ReviewSeverity = ReviewSeverity.MEDIUM,
    summary: str = "The parser drops the final item",
) -> ReviewFinding:
    return ReviewFinding(
        finding_id="f1",
        dimension=ReviewDimension.CORRECTNESS,
        severity=severity,
        summary=summary,
        evidence=[
            EvidenceRef(
                evidence_id="evidence-1",
                kind=EvidenceKind.SOURCE,
                artifact=_artifact(),
                summary="Grounded source evidence",
            )
        ],
        fix_cost_now=FixCostNow.SPRAWLING,
        location=SourceLocation(
            artifact_id="artifact-1", path="src/parser.py", start_line=1, end_line=2
        ),
    )


def _review(
    state: RemediationState,
    findings: list[ReviewFinding] | None,
    disposition: ReviewDisposition,
) -> ReviewResult:
    from easy_cheese.shared.fanout.remediation import bind_event_identity

    return ReviewResult(
        contract_version=ContractVersion(schema_uri=REVIEW_SCHEMA, major="1", minor="0"),
        review_id="review-1",
        disposition=disposition,
        findings=[] if findings is None else findings,
        coverage=[
            ReviewCoverage(
                target="src/parser.py", disposition=CoverageDisposition.COVERED
            )
        ],
        reason=None,
        event_identity=bind_event_identity(state, DIGEST, event="review"),
    )




def _state(
    *,
    cursor: RemediationCursor = RemediationCursor.AWAITING_REVIEW,
    locked_selection: tuple[str, ...] = (),
) -> RemediationState:
    return RemediationState(
        contract_version=ContractVersion(schema_uri=STATE_SCHEMA, major="1", minor="0"),
        state_id="state-1",
        scope=RemediationScopeKey(
            run_id="run-1",
            source_plan_ref=SourcePlanRef(plan_id="plan-1", revision=1, digest=DIGEST),
            scope_kind=RemediationScopeKind.CURD,
            scope_id="curd-1",
        ),
        cursor=cursor,
        disposition=RemediationDisposition.ACTIVE,
        locked_selection=locked_selection,
    )


def _cure_observation(
    state: RemediationState,
    applied: tuple[str, ...],
    deferred: tuple[str, ...],
) -> RemediationCureObservation:
    from easy_cheese.shared.fanout.remediation import bind_event_identity

    return RemediationCureObservation(
        contract_version=ContractVersion(schema_uri=CURE_SCHEMA, major="1", minor="0"),
        applied_finding_keys=applied,
        deferred_finding_keys=deferred,
        touched_paths=("src/parser.py",),
        gate_evidence=(),
        new_gate_failures=(),
        event_identity=bind_event_identity(state, DIGEST, event="cure"),
    )


class TestReviewEvent:
    def test_findings_review_routes_to_cure_and_publishes(self, tmp_path: Path) -> None:
        state_value = _state()
        state = _write(tmp_path / "state.json", state_value)
        review = _write(
            tmp_path / "review.json",
            _review(state_value, [_finding()], ReviewDisposition.FINDINGS),
        )
        result = _run_cli("--state", str(state), "--event", "review", "--review", str(review))
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload["action"] == "cure"
        assert payload["next_phase"] == "cure"
        assert payload["cursor"] == "awaiting_cure"
        assert payload["state_ref"] == str(state)
        # State is republished to the same path with one locked key.
        republished = cast("dict[str, object]", json.loads(state.read_bytes()))
        assert len(cast("list[str]", republished["locked_selection"])) == 1

    def test_clean_review_completes_without_cure(self, tmp_path: Path) -> None:
        state_value = _state()
        state = _write(tmp_path / "state.json", state_value)
        review = _write(
            tmp_path / "review.json", _review(state_value, None, ReviewDisposition.CLEAN)
        )
        result = _run_cli("--state", str(state), "--event", "review", "--review", str(review))
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload["action"] == "complete"
        assert payload["next_phase"] is None
        assert payload["cursor"] == "terminal"


class TestCureEvent:
    def _review_then_state(self, tmp_path: Path) -> tuple[Path, list[str]]:
        state_value = _state()
        state = _write(tmp_path / "state.json", state_value)
        review = _write(
            tmp_path / "review.json",
            _review(state_value, [_finding()], ReviewDisposition.FINDINGS),
        )
        result = _run_cli("--state", str(state), "--event", "review", "--review", str(review))
        assert result.returncode == 0, result.stderr
        published = cast("dict[str, object]", json.loads(state.read_bytes()))
        return state, cast("list[str]", published["locked_selection"])

    def test_cure_applies_selection_and_returns_to_age(self, tmp_path: Path) -> None:
        state, selection = self._review_then_state(tmp_path)
        cure_state = load_state(state)
        cure = _write(
            tmp_path / "cure.json", _cure_observation(cure_state, tuple(selection), ())
        )
        result = _run_cli(
            "--state", str(state), "--event", "cure", "--cure-result", str(cure)
        )
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload["action"] == "age"
        assert payload["next_phase"] == "age"
        assert payload["cursor"] == "awaiting_review"

    def test_zero_applied_cure_remediates(self, tmp_path: Path) -> None:
        state, selection = self._review_then_state(tmp_path)
        cure_state = load_state(state)
        cure = _write(
            tmp_path / "cure.json", _cure_observation(cure_state, (), tuple(selection))
        )
        result = _run_cli(
            "--state", str(state), "--event", "cure", "--cure-result", str(cure)
        )
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload["action"] == "remediate"
        assert payload["next_phase"] == "mold"
        assert payload["cursor"] == "terminal"


class TestFailClosed:
    def test_review_event_without_review_flag_exits_2(self, tmp_path: Path) -> None:
        state = _write(tmp_path / "state.json", _state())
        result = _run_cli("--state", str(state), "--event", "review")
        assert result.returncode == 2
        assert "--review" in result.stderr

    def test_cure_event_without_cure_result_exits_2(self, tmp_path: Path) -> None:
        state = _write(tmp_path / "state.json", _state())
        result = _run_cli("--state", str(state), "--event", "cure")
        assert result.returncode == 2

    def test_missing_state_file_exits_2(self, tmp_path: Path) -> None:
        review = _write(
            tmp_path / "review.json",
            _review(_state(), [_finding()], ReviewDisposition.FINDINGS),
        )
        result = _run_cli(
            "--state", str(tmp_path / "absent.json"), "--event", "review",
            "--review", str(review),
        )
        assert result.returncode == 2
        assert "cannot read" in result.stderr

    def test_invalid_state_contract_exits_3(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        _ = state.write_bytes(b'{"not": "a remediation state"}')
        review = _write(
            tmp_path / "review.json",
            _review(_state(), [_finding()], ReviewDisposition.FINDINGS),
        )
        result = _run_cli(
            "--state", str(state), "--event", "review", "--review", str(review)
        )
        assert result.returncode == 3

    def test_help_lists_flags(self) -> None:
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "--state" in result.stdout
        assert "--event" in result.stdout
        assert "--cure-result" in result.stdout
