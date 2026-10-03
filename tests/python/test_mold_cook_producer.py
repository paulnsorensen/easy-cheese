from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared.mold_cook_handoff import accept_mold_cook_handoff
from easy_cheese_schemas import ContractVersion, validate_contract
from easy_cheese.shared.publication import PublicationError
from easy_cheese.shared.taste_test import ForkTasteVerdict
from easy_cheese.skills.mold import producer
from easy_cheese.skills.mold.producer import (
    FinalizationError,
    FinalizationOutcome,
    finalize_mold,
    normalize_planner_result,
)
from easy_cheese_schemas.contracts import (
    BoundedScope,
    CriterionWriterView,
    CurdPlan,
    CurdPlanWriterView,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    PlannerResultWriterView,
    SemanticCurdWriterView,
)
from easy_cheese_schemas.mold_cook import (
    CookPreparationResult,
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import supported_version_for


FIXTURE = Path(__file__).parent / "fixtures" / "spec_format" / "valid_spec.md"


def make_spec(
    tmp_path: Path,
    *,
    landing_id: str | None = None,
    do_not_implement: bool = False,
    gates_overridden: str | None = None,
    execution_holds: str | None = None,
) -> Path:
    text = FIXTURE.read_text(encoding="utf-8")
    if landing_id is not None:
        replacement = (
            'gates_overridden: []\nlanding:\n  shape: stacked_linear\n  layers: [["'
            + landing_id
            + '"]]\n  per_layer_green: required\n  review_fixes: fold\n'
        )
        text = text.replace("gates_overridden: []\n", replacement)
    if do_not_implement:
        text = text.replace(
            "gates_overridden: []\n",
            "gates_overridden: []\nrequest_directive: do-not-implement\n",
            1,
        )
    if gates_overridden is not None:
        text = text.replace("gates_overridden: []\n", gates_overridden, 1)
    if execution_holds is not None:
        text = text.replace(
            "agent_introduced_scope: []\n",
            execution_holds + "agent_introduced_scope: []\n",
            1,
        )
    path = tmp_path / "spec.md"
    _ = path.write_text(text, encoding="utf-8")
    return path


def taste_fixture(spec_path: Path, *, passed: bool = True) -> ForkTasteVerdict:
    return ForkTasteVerdict.from_mapping(
        {
            "draft_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            "verdict": "pass" if passed else "fail",
            "forks": [],
            "contradictions": [],
            "orphaned_decisions": [],
            "unsupported_assumptions": [],
            "acceptance_gaps": [] if passed else ["failed-fork"],
        }
    )


def make_planner_result() -> PlannerResult:
    version = supported_version_for(PlannerRequest)
    request = cast(Callable[..., PlannerRequest], PlannerRequest)(
        contract_version=version,
        request_id="request-1",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Implement the Mold to Cook boundary",
    )
    writer = cast(Callable[..., PlannerResultWriterView], PlannerResultWriterView)(
        disposition=PlannerDisposition.COMPLETE,
        plan=cast(Callable[..., CurdPlanWriterView], CurdPlanWriterView)(
            objective=request.objective,
            curds=[
                cast(Callable[..., SemanticCurdWriterView], SemanticCurdWriterView)(
                    key="core",
                    outcome="Implement the canonical boundary",
                    scope=cast(Callable[..., BoundedScope], BoundedScope)(
                        paths=["src/core.py"]
                    ),
                    outputs=["A consumer-valid handoff"],
                    criteria=[
                        cast(Callable[..., CriterionWriterView], CriterionWriterView)(
                            description="The handoff is consumer-valid",
                            check="pytest tests/python/test_mold_cook_producer.py",
                        )
                    ],
                )
            ],
        ),
    )
    return normalize_planner_result(
        request,
        writer,
        plan_id="plan-1",
        curd_ids={"core": "curd-1"},
    )

def finalize_fixture(
    tmp_path: Path,
    *,
    spec_path: Path | None = None,
    planner: PlannerResult | None = None,
    taste: ForkTasteVerdict | None = None,
    save_approved: bool = False,
) -> FinalizationOutcome:
    spec = spec_path or make_spec(tmp_path)
    selected_plan = planner or make_planner_result()
    return finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.FULL,
        planner_result=selected_plan,
        plan=cast(CurdPlan, selected_plan.plan),
        taste_result=taste or taste_fixture(spec),
        decision_ledger=(),
        save_approved=save_approved,
    )



def test_complete_finalization_publishes_a_pointer_consumers_can_accept(
    tmp_path: Path,
) -> None:
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    assert outcome.ready is True
    pointer_path = tmp_path / "artifacts" / "pointers" / "operation-1.json"
    accepted = accept_mold_cook_handoff(
        pointer_path, artifact_root=tmp_path / "artifacts"
    )
    accepted_handoff = cast(MoldCookHandoff, accepted.canonical.value)
    assert accepted_handoff.request_id == "request-1"
    assert outcome.payload["next"] == "cook"


def test_failed_taste_is_saved_without_execution_authority(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    outcome = finalize_fixture(
        tmp_path, spec_path=spec, taste=taste_fixture(spec, passed=False)
    )

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert outcome.payload["requirements"] == [
        {
            "requirement_id": "taste-verdict",
            "kind": "evidence",
            "description": "taste verdict did not pass: failed-fork",
            "evidence": [],
        }
    ]
    assert "pointer" not in outcome.payload


def test_invalid_landing_id_is_saved_without_execution_authority(
    tmp_path: Path,
) -> None:
    spec = make_spec(tmp_path, landing_id="not-a-plan-curd")
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    requirements = cast(Sequence[Mapping[str, object]], outcome.payload["requirements"])
    assert tuple(
        (item["requirement_id"], item["kind"], item["evidence"])
        for item in requirements
    ) == (("landing-declaration", "integrity", []),)
    assert "pointer" not in outcome.payload


def test_do_not_implement_hold_blocks_ready_publication(tmp_path: Path) -> None:
    spec = make_spec(tmp_path, do_not_implement=True)
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert outcome.payload["holds"] == [
        {
            "hold_id": "user-do-not-implement",
            "kind": "user_intent",
            "reason": "whole-request directive 'do-not-implement' blocks execution",
            "evidence": [],
        }
    ]


def test_full_tier_publishes_without_any_approval_evidence(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    handoff = cast(Mapping[str, object], outcome.payload["handoff"])
    assert "approval_ref" not in handoff


def test_light_tier_publishes_one_curd_without_any_approval_evidence(
    tmp_path: Path,
) -> None:
    spec = make_spec(tmp_path)
    outcome = finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.LIGHT,
        proposed_coverage=MoldCookCoverage(curd_ids=("curd-1",)),
        taste_result=taste_fixture(spec),
        decision_ledger=(),
    )

    assert outcome.status == "ready"
    handoff = cast(Mapping[str, object], outcome.payload["handoff"])
    assert handoff["mode"] == "light"
    assert "approval_ref" not in handoff


def test_light_tier_with_two_curds_is_saved_without_execution_authority(
    tmp_path: Path,
) -> None:
    spec = make_spec(tmp_path)
    outcome = finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.LIGHT,
        proposed_coverage=MoldCookCoverage(curd_ids=("curd-1", "curd-2")),
        taste_result=taste_fixture(spec),
        decision_ledger=(),
    )

    assert outcome.status == "saved-not-ready"
    requirements = cast(Sequence[Mapping[str, object]], outcome.payload["requirements"])
    assert "light-coverage" in {str(item["requirement_id"]) for item in requirements}

def test_save_approved_is_save_only_and_records_a_hold(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path, save_approved=True)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert outcome.payload["holds"] == [
        {
            "hold_id": "save-approved",
            "kind": "preparation",
            "reason": "save approval is save-only and never waives execution readiness",
            "evidence": [],
        }
    ]
    assert "pointer" not in outcome.payload


def test_non_ready_results_are_durable(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    outcome = finalize_fixture(
        tmp_path, spec_path=spec, taste=taste_fixture(spec, passed=False)
    )

    assert outcome.result_path is not None
    assert outcome.result_path.is_file()
    assert outcome.payload["saved"] is True


def _hold_rows(outcome: FinalizationOutcome) -> Sequence[Mapping[str, object]]:
    return cast(Sequence[Mapping[str, object]], outcome.payload["holds"])


def test_block_list_gate_override_is_saved_with_a_gates_overridden_hold(
    tmp_path: Path,
) -> None:
    spec = make_spec(
        tmp_path,
        gates_overridden="gates_overridden:\n  - handshake-coherence\n  - taste-test\n",
    )
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    holds = {str(item["hold_id"]): str(item["reason"]) for item in _hold_rows(outcome)}
    assert "gates-overridden" in holds
    assert holds["gates-overridden"].endswith("handshake-coherence, taste-test")
    assert "pointer" not in outcome.payload


def test_gate_override_and_save_approval_keep_distinct_holds(tmp_path: Path) -> None:
    spec = make_spec(
        tmp_path, gates_overridden="gates_overridden:\n  - taste-test\n"
    )
    outcome = finalize_fixture(tmp_path, spec_path=spec, save_approved=True)

    holds = {str(item["hold_id"]): str(item["reason"]) for item in _hold_rows(outcome)}
    assert holds["gates-overridden"].endswith("taste-test")
    assert (
        holds["save-approved"]
        == "save approval is save-only and never waives execution readiness"
    )


@pytest.mark.parametrize(
    ("declaration", "expected"),
    [
        ('gates_overridden: ["handshake-coherence"]\n', "handshake-coherence"),
        ("gates_overridden: handshake-coherence\n", "handshake-coherence"),
    ],
)
def test_flow_list_and_scalar_gate_overrides_keep_the_hold(
    tmp_path: Path, declaration: str, expected: str
) -> None:
    spec = make_spec(tmp_path, gates_overridden=declaration)
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    holds = {str(item["hold_id"]): str(item["reason"]) for item in _hold_rows(outcome)}
    assert holds["gates-overridden"].endswith(expected)


@pytest.mark.parametrize(
    "declaration",
    [
        "gates_overridden:\n- agent-coherence\n- taste-test\n",
        "gates_overridden:\n  # the handshake keys left unchecked\n  - agent-coherence\n  - taste-test\n",
    ],
)
def test_column_zero_and_commented_block_lists_keep_the_hold(
    tmp_path: Path, declaration: str
) -> None:
    """A block sequence at the key's own indentation is valid YAML."""
    spec = make_spec(tmp_path, gates_overridden=declaration)

    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    holds = {str(item["hold_id"]): str(item["reason"]) for item in _hold_rows(outcome)}
    assert holds["gates-overridden"].endswith("agent-coherence, taste-test")


def test_a_mapping_under_gates_overridden_is_a_caller_error(tmp_path: Path) -> None:
    spec = make_spec(
        tmp_path, gates_overridden="gates_overridden:\n  waived: agent-coherence\n"
    )

    with pytest.raises(FinalizationError, match="gates_overridden"):
        _ = finalize_fixture(tmp_path, spec_path=spec)


def test_unparsable_gate_override_list_is_a_caller_error(tmp_path: Path) -> None:
    spec = make_spec(tmp_path, gates_overridden='gates_overridden: ["unterminated"\n')

    with pytest.raises(FinalizationError, match="gates_overridden"):
        _ = finalize_fixture(tmp_path, spec_path=spec)


def _requirement_ids(outcome: FinalizationOutcome) -> set[str]:
    rows = cast(
        Sequence[Mapping[str, object]], outcome.payload.get("requirements", [])
    )
    return {str(row["requirement_id"]) for row in rows}


@pytest.mark.parametrize(
    "declaration",
    [
        "execution_holds:\n  - scope-audit-row-5-needs-your-verb\n",
        "execution_holds:\n- scope-audit-row-5-needs-your-verb\n",
        'execution_holds: ["scope-audit-row-5-needs-your-verb"]\n',
        "execution_holds: [scope-audit-row-5-needs-your-verb]\n",
    ],
    ids=["indented-block", "flush-block", "quoted-flow", "bare-flow"],
)
def test_a_non_empty_execution_holds_list_blocks_ready(
    tmp_path: Path, declaration: str
) -> None:
    spec = make_spec(tmp_path, execution_holds=declaration)
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert "spec-validation" not in _requirement_ids(outcome)
    holds = {str(item["hold_id"]): str(item["reason"]) for item in _hold_rows(outcome)}
    assert holds["execution-hold-1"].endswith("scope-audit-row-5-needs-your-verb")


def test_an_execution_hold_with_an_apostrophe_is_kept_verbatim(tmp_path: Path) -> None:
    spec = make_spec(
        tmp_path,
        execution_holds='execution_holds: ["row 5 needs the user\'s verb"]\n',
    )
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert "spec-validation" not in _requirement_ids(outcome)
    holds = {str(item["hold_id"]): str(item["reason"]) for item in _hold_rows(outcome)}
    assert holds["execution-hold-1"].endswith("row 5 needs the user's verb")


def test_an_empty_execution_holds_list_does_not_block_ready(tmp_path: Path) -> None:
    spec = make_spec(tmp_path, execution_holds="execution_holds: []\n")
    outcome = finalize_fixture(tmp_path, spec_path=spec)

    assert outcome.status == "ready"
    assert "spec-validation" not in _requirement_ids(outcome)


def test_an_absent_execution_holds_list_does_not_block_ready(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"


def test_publication_failure_saves_a_validated_blocked_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validated: list[object] = []
    real_validate = validate_contract

    def recording_validate(payload: bytes, contract: object, version: object) -> object:
        validated.append(contract)
        return real_validate(
            payload,
            cast(type[object], contract),
            cast("ContractVersion | None", version),
        )

    def failing_publish(*_args: object, **_kwargs: object) -> object:
        raise PublicationError("publication refused")

    monkeypatch.setattr(producer, "validate_contract", recording_validate)
    monkeypatch.setattr(producer, "publish_mold_cook_handoff", failing_publish)
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "saved-not-ready"
    assert CookPreparationResult in validated
    requirements = cast(Sequence[Mapping[str, object]], outcome.payload["requirements"])
    assert "handoff-integrity" in {str(item["requirement_id"]) for item in requirements}
    assert not (tmp_path / "artifacts" / "pointers" / "operation-1.json").exists()


def test_persisted_artifact_ids_derive_from_role_and_digest(tmp_path: Path) -> None:
    assert "artifact_id" not in inspect.signature(producer._persist).parameters  # pyright: ignore[reportPrivateUsage]
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    handoff = cast(Mapping[str, object], outcome.payload["handoff"])
    spec_ref = cast(Mapping[str, object], handoff["spec_ref"])
    digest = str(spec_ref["digest"]).removeprefix("sha256:")
    assert spec_ref["artifact_id"] == f"spec-{digest}"
