"""Cross-boundary Mold -> Cook regressions.

The assertions cross producer and consumer seams. Browser and live-agent
checks are separate opt-in tests so this module remains hermetic.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import canonical_bytes
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared.publication import accept_mold_cook_handoff
from easy_cheese.skills.cook.preparation import prepare, resubmit
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    CookPreparationOutcome,
    CookRequirementKind,
    CookSetupAuthorization,
    MoldCookInputKind,
    MoldCookMode,
    MoldCookHandoff,
)

from tests.python.mold_cook_transcript_checker import (
    TranscriptCheckError,
    check_transcript,
    load_transcript,
)
from tests.python.test_cook_contract_accept import published_handoff
from tests.python.test_mold_cook_producer import (
    make_approval,
    finalize_fixture,
    make_planner_result,
    make_spec,
)


TRACE_ROOT = Path(__file__).parent.parent / "fixtures" / "mold_cook_traces"


def test_full_and_light_authority_are_distinct_and_consumable(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    outcome = finalize_fixture(tmp_path, spec_path=spec)
    assert outcome.status == "ready"
    pointer = tmp_path / "artifacts" / "pointers" / "operation-1.json"
    accepted = accept_mold_cook_handoff(pointer, artifact_root=tmp_path / "artifacts")
    full = cast(MoldCookHandoff, accepted.canonical.value)
    assert full.mode is MoldCookMode.FULL
    assert full.planner_result_ref is not None
    assert full.plan_ref is not None

    light_root = tmp_path / "light"
    light_pointer, _, _ = published_handoff(light_root, "light-operation")
    light_accepted = accept_mold_cook_handoff(light_pointer, artifact_root=light_root)
    light = cast(MoldCookHandoff, light_accepted.canonical.value)
    assert light.mode is MoldCookMode.LIGHT
    assert light.coverage.curd_ids == ("curd-1",)
    assert light.planner_result_ref is None
    assert light.plan_ref is None


def test_approval_reuse_succeeds_but_stale_evidence_is_rejected(tmp_path: Path) -> None:
    pointer, _, _ = published_handoff(tmp_path, "repeatable")
    first = accept_mold_cook_handoff(pointer, artifact_root=tmp_path)
    second = accept_mold_cook_handoff(pointer, artifact_root=tmp_path)
    assert first.canonical.canonical_bytes == second.canonical.canonical_bytes

    approval = tmp_path / "approval.json"
    _ = approval.write_bytes(approval.read_bytes().replace(b"Approve", b"Reject!"))
    with pytest.raises(ContractValidationError, match="stale or corrupt"):
        _ = accept_mold_cook_handoff(pointer, artifact_root=tmp_path)


def test_hold_survives_resubmission_until_explicitly_cleared(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    planner = make_planner_result()
    approval = make_approval(tmp_path, spec, plan=planner)
    hold = cast(Callable[..., CookExecutionHold], CookExecutionHold)(
        hold_id="incident-1",
        kind=CookHoldKind.BLOCKED,
        reason="operator review required",
    )
    blocked = prepare(
        spec,
        request_id="request-1",
        repository_root=tmp_path,
        artifact_root=tmp_path,
        mode=MoldCookMode.FULL,
        planner_result=planner,
        plan_approval=approval,
        holds=(hold,),
    )
    assert blocked.outcome is CookPreparationOutcome.BLOCKED
    repeated = resubmit(
        blocked,
        source=spec,
        repository_root=tmp_path,
        artifact_root=tmp_path,
        mode=MoldCookMode.FULL,
        planner_result=planner,
        plan_approval=approval,
        holds=(hold,),
    )
    assert repeated.outcome is CookPreparationOutcome.BLOCKED
    assert repeated.holds == (hold,)


def test_continuity_reuses_published_payload(tmp_path: Path) -> None:
    pointer, _, _ = published_handoff(tmp_path, "continuation")
    accepted = accept_mold_cook_handoff(pointer, artifact_root=tmp_path)
    repeated, _, _ = published_handoff(tmp_path / "repeat", "continuation-2")
    accepted_again = accept_mold_cook_handoff(
        repeated, artifact_root=tmp_path / "repeat"
    )
    handoff = cast(MoldCookHandoff, accepted.canonical.value)
    assert accepted.canonical.value == accepted_again.canonical.value
    assert accepted.canonical.canonical_bytes == canonical_bytes(handoff)
    assert accepted_again.canonical.canonical_bytes == canonical_bytes(handoff)


_BOUNDARY_FIXTURES = Path(__file__).parents[1] / "fixtures" / "mold_cook_boundary"


def _copy_historical_fixture(tmp_path: Path, pointer_name: str) -> Path:
    for name in (
        "historical-plan.json",
        "historical-receipt.json",
        pointer_name,
    ):
        _ = shutil.copy2(_BOUNDARY_FIXTURES / name, tmp_path / name)
    return tmp_path / pointer_name


@pytest.mark.parametrize(
    ("pointer_name", "reference_count"),
    [
        ("historical-pointer.json", 3),
        ("historical-pointer-with-receipt.json", 4),
    ],
)
def test_historical_curd_plan_pointer_requires_one_bound_migration(
    tmp_path: Path, pointer_name: str, reference_count: int
) -> None:
    pointer = _copy_historical_fixture(tmp_path, pointer_name)
    original_pointer = pointer.read_bytes()
    result = prepare(
        pointer,
        request_id="historical-1",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        explicit_kind=MoldCookInputKind.CANONICAL_POINTER,
    )

    assert result.outcome is CookPreparationOutcome.BLOCKED
    assert result.holds == ()
    assert tuple(
        (item.requirement_id, item.kind, item.description, item.evidence)
        for item in result.requirements
    ) == (
        (
            "legacy-spec-binding",
            CookRequirementKind.SCOPE,
            "an intact historical CurdPlan requires a canonical host-bound "
            + "Mold spec before migration",
            (),
        ),
    )
    assert len(result.references) == reference_count
    assert "curd_plan" in {reference.role for reference in result.references}
    assert pointer.read_bytes() == original_pointer


@pytest.mark.parametrize("corruption", ["pointer-digest", "payload-bytes"])
def test_historical_curd_plan_pointer_reports_exact_corruption(
    tmp_path: Path, corruption: str
) -> None:
    pointer = _copy_historical_fixture(tmp_path, "historical-pointer.json")
    if corruption == "pointer-digest":
        document = cast(
            dict[str, object], json.loads(pointer.read_text(encoding="utf-8"))
        )
        payload = cast(dict[str, object], document["payload"])
        payload["digest"] = "sha256:" + "0" * 64
        _ = pointer.write_text(json.dumps(document), encoding="utf-8")
    else:
        plan = tmp_path / "historical-plan.json"
        _ = plan.write_text(plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = prepare(
        pointer,
        request_id="historical-corrupt",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        explicit_kind=MoldCookInputKind.CANONICAL_POINTER,
    )

    assert result.outcome is CookPreparationOutcome.INVALID
    assert tuple((item.code, item.path) for item in result.findings) == (
        ("invalid-pointer", str(pointer)),
    )


def test_setup_authority_is_named_and_does_not_claim_feature_execution(
    tmp_path: Path,
) -> None:
    spec = make_spec(tmp_path)
    auth = cast(Callable[..., CookSetupAuthorization], CookSetupAuthorization)(
        prerequisite_curd_id="curd-setup",
        allowed_paths=("tests/fixtures/setup.py",),
        allowed_commands=("python3 tests/fixtures/setup.py",),
    )
    result = prepare(
        spec,
        request_id="setup-1",
        repository_root=tmp_path,
        artifact_root=tmp_path,
        mode=MoldCookMode.FULL,
        setup_authorization=auth,
    )
    assert result.outcome is CookPreparationOutcome.INVALID
    assert result.handoff_ref is None
    assert result.findings[0].message == (
        "setup authority and evidence must be derived from runner approval"
    )


@pytest.mark.parametrize(
    ("filename", "mode"),
    [
        ("full-ready.json", "full"),
        ("light-ready.json", "light"),
        ("partial-preserved.json", "full"),
    ],
)
def test_frozen_agent_traces_prove_ordered_authority(filename: str, mode: str) -> None:
    report = check_transcript(
        load_transcript(TRACE_ROOT / filename), expected_mode=mode
    )
    assert report.artifact_refs
    assert "consumer_accept" in report.event_types


def test_frozen_agent_traces_reject_unsafe_actions() -> None:
    cases = cast(
        list[Mapping[str, object]],
        json.loads((TRACE_ROOT / "negative-cases.json").read_text(encoding="utf-8")),
    )
    assert len(cases) == 7
    for case in cases:
        trace = cast(Mapping[str, object], case["trace"])
        expect = cast(str, case["expect"])
        with pytest.raises(TranscriptCheckError, match=re.escape(expect)):
            _ = check_transcript(trace)


def test_transcript_checker_ignores_prose_but_bounds_actions() -> None:
    trace = load_transcript(TRACE_ROOT / "light-ready.json")
    trace["commentary"] = "model prose is not authority"
    assert check_transcript(trace).scenario == "light-ready"
    oversized = dict(trace)
    events = cast(list[object], trace["events"])
    oversized["events"] = events * 11
    with pytest.raises(TranscriptCheckError, match="64"):
        _ = check_transcript(oversized)
