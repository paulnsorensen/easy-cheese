"""Cross-boundary Mold producer and Cook consumer regressions."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import attrs
import pytest

from easy_cheese.shared.mold_cook_handoff import validate_bound_execution
from easy_cheese.shared.wheypoint.canonical import digest_bytes
from easy_cheese_schemas import ArtifactRef, MoldCookCoverage
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    _typed_host as structure_contract_value,  # pyright: ignore[reportPrivateUsage]
)
from easy_cheese_schemas.contracts import (
    PlannerDisposition,
    PlannerUncertainty,
    UncertaintyScope,
)
from tests.python.mold_cook_transcript_checker import (
    TranscriptCheckError,
    check_transcript,
    load_transcript,
)
from tests.python.test_mold_cook_producer import (
    finalize_fixture,
    make_planner_result,
    make_spec,
)

TRACE_ROOT = Path(__file__).parent.parent / "fixtures" / "mold_cook_traces"


def _bound_inputs(
    outcome: object,
) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef, MoldCookCoverage]:
    payload = cast(Mapping[str, object], getattr(outcome, "payload"))
    refs = tuple(
        structure_contract_value(payload[name], ArtifactRef, name)
        for name in ("spec_ref", "planner_result_ref", "plan_ref")
    )
    coverage = structure_contract_value(payload["coverage"], MoldCookCoverage, "coverage")
    return refs[0], refs[1], refs[2], coverage


def test_producer_outputs_consumer_valid_bound_inputs(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)
    assert outcome.status == "ready"
    spec_ref, planner_ref, plan_ref, coverage = _bound_inputs(outcome)

    plan = validate_bound_execution(
        spec_ref=spec_ref,
        planner_result_ref=planner_ref,
        plan_ref=plan_ref,
        coverage=coverage,
        artifact_root=tmp_path / "artifacts",
    )

    assert tuple(curd.curd_id for curd in plan.curds) == coverage.curd_ids
    assert not (tmp_path / "artifacts" / "pointers").exists()


def test_partial_finalization_keeps_exact_remainder_in_bound_inputs(
    tmp_path: Path,
) -> None:
    remainder = (
        PlannerUncertainty(
            description="unselected parent work remains",
            scope=UncertaintyScope.OMITTED_WORK,
        ),
    )
    planner = attrs.evolve(
        make_planner_result(),
        disposition=PlannerDisposition.PARTIAL,
        unresolved_work=remainder,
    )
    outcome = finalize_fixture(tmp_path, planner=planner)
    assert outcome.status == "ready"
    spec_ref, planner_ref, plan_ref, coverage = _bound_inputs(outcome)
    assert coverage.unresolved_work == remainder
    assert validate_bound_execution(
        spec_ref=spec_ref, planner_result_ref=planner_ref, plan_ref=plan_ref,
        coverage=coverage, artifact_root=tmp_path / "artifacts",
    ) == planner.plan


def test_consumer_rejects_tampered_producer_plan(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)
    spec_ref, planner_ref, plan_ref, coverage = _bound_inputs(outcome)
    plan_path = Path(urlsplit(plan_ref.uri).path)
    _ = plan_path.write_bytes(plan_path.read_bytes().replace(b"plan-1", b"plan-X", 1))

    with pytest.raises(ContractValidationError, match="stale or corrupt"):
        _ = validate_bound_execution(
            spec_ref=spec_ref,
            planner_result_ref=planner_ref,
            plan_ref=plan_ref,
            coverage=coverage,
            artifact_root=tmp_path / "artifacts",
        )


def test_runner_authority_without_setup_evidence_cannot_execute(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)
    spec_ref, planner_ref, plan_ref, coverage = _bound_inputs(outcome)

    with pytest.raises(
        ContractValidationError, match="requires passing setup evidence"
    ):
        _ = validate_bound_execution(
            spec_ref=spec_ref,
            planner_result_ref=planner_ref,
            plan_ref=plan_ref,
            coverage=coverage,
            artifact_root=tmp_path / "artifacts",
            runner_authorization_ref=attrs.evolve(
                spec_ref, role="runner_authorization"
            ),
            runner_response_ref=attrs.evolve(spec_ref, role="dialogue"),
        )


def test_explicit_spec_hold_prevents_cook_inputs(tmp_path: Path) -> None:
    spec = make_spec(
        tmp_path,
        execution_holds='execution_holds: ["operator review required"]\n',
    )
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    holds = cast(list[dict[str, object]], outcome.payload["holds"])
    assert any(
        item["reason"] == "unresolved execution hold: operator review required"
        for item in holds
    )
    assert "plan_ref" not in outcome.payload
    assert not (tmp_path / "artifacts" / "pointers").exists()


@pytest.mark.parametrize(
    ("filename", "scenario"),
    [
        ("full-ready.json", "full-ready"),
        ("light-ready.json", "runner-setup-ready"),
        ("partial-preserved.json", "partial-preserved"),
    ],
)
def test_frozen_agent_traces_prove_ordered_authority(filename: str, scenario: str) -> None:
    report = check_transcript(load_transcript(TRACE_ROOT / filename))
    assert report.scenario == scenario
    assert report.artifact_refs
    assert "bound_inputs" in report.event_types

def test_frozen_agent_traces_reject_unsafe_actions() -> None:
    cases = cast(
        list[Mapping[str, object]],
        json.loads((TRACE_ROOT / "negative-cases.json").read_text(encoding="utf-8")),
    )
    assert len(cases) == 10
    for case in cases:
        trace = cast(Mapping[str, object], case["trace"])
        expect = cast(str, case["expect"])
        with pytest.raises(TranscriptCheckError, match=re.escape(expect)):
            _ = check_transcript(trace)


def test_transcript_checker_ignores_prose_but_bounds_actions() -> None:
    trace = load_transcript(TRACE_ROOT / "light-ready.json")
    trace["commentary"] = "model prose is not authority"
    assert check_transcript(trace).scenario == "runner-setup-ready"
    oversized = dict(trace)
    events = cast(list[object], trace["events"])
    oversized["events"] = events * 11
    with pytest.raises(TranscriptCheckError, match="64"):
        _ = check_transcript(oversized)


def _validate(
    root: Path,
    spec_ref: ArtifactRef,
    planner_ref: ArtifactRef,
    plan_ref: ArtifactRef,
    coverage: MoldCookCoverage,
    **extra: object,
) -> object:
    return validate_bound_execution(
        spec_ref=spec_ref,
        planner_result_ref=planner_ref,
        plan_ref=plan_ref,
        coverage=coverage,
        artifact_root=root,
        **extra,  # pyright: ignore[reportArgumentType]
    )


def _rewrite_spec(spec_ref: ArtifactRef, content: bytes) -> ArtifactRef:
    """Replace the retained spec bytes and re-pin the reference to them."""
    _ = Path(urlsplit(spec_ref.uri).path).write_bytes(content)
    return attrs.evolve(
        spec_ref, digest=digest_bytes(content), size_bytes=len(content)
    )


def test_consumer_refuses_spec_with_execution_holds(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)
    spec_ref, planner_ref, plan_ref, coverage = _bound_inputs(outcome)
    (tmp_path / "held").mkdir()
    held_text = make_spec(
        tmp_path / "held",
        execution_holds='execution_holds: ["operator review required"]\n',
    ).read_bytes()
    held = _rewrite_spec(spec_ref, held_text)

    with pytest.raises(ContractValidationError, match="execution holds"):
        _ = _validate(tmp_path / "artifacts", held, planner_ref, plan_ref, coverage)


def test_consumer_refuses_spec_changed_after_finalize(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)
    spec_ref, planner_ref, plan_ref, coverage = _bound_inputs(outcome)
    spec_path = Path(urlsplit(spec_ref.uri).path)
    _ = spec_path.write_bytes(
        spec_path.read_bytes().replace(b"mold-handshake", b"mold-handshakf", 1)
    )

    with pytest.raises(ContractValidationError, match="stale or corrupt"):
        _ = _validate(tmp_path / "artifacts", spec_ref, planner_ref, plan_ref, coverage)


def test_runner_response_without_authorization_is_refused(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)
    spec_ref, planner_ref, plan_ref, coverage = _bound_inputs(outcome)

    with pytest.raises(ContractValidationError, match="authorization and response"):
        _ = _validate(
            tmp_path / "artifacts", spec_ref, planner_ref, plan_ref, coverage,
            runner_response_ref=attrs.evolve(spec_ref, role="dialogue"),
        )


def test_setup_evidence_without_runner_authority_is_refused(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)
    spec_ref, planner_ref, plan_ref, coverage = _bound_inputs(outcome)

    with pytest.raises(ContractValidationError, match="requires runner authority"):
        _ = _validate(
            tmp_path / "artifacts", spec_ref, planner_ref, plan_ref, coverage,
            setup_evidence_refs=(attrs.evolve(spec_ref, role="setup_evidence"),),
        )
