"""Mold's producer-side artifact store, planner structuring, and coverage.

These tests pin the seams a consumer depends on: Mold retains through the one
shared content-addressed store, structures host mappings through the one shared
contract path, bounds every JSON input it reads, and proposes the coverage the
approval is bound against.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import canonical_bytes

from easy_cheese.shared.artifacts import resolve_artifact
from easy_cheese.shared.mold_cook_handoff import accept_mold_cook_handoff
from easy_cheese.skills.mold import producer
from easy_cheese.skills.mold.producer import (
    FinalizationError,
    FinalizationOutcome,
    finalize_mold,
    normalize_planner_result,
)
from easy_cheese_schemas.contracts import (
    MAX_ARTIFACT_BYTES,
    BoundedScope,
    CriterionWriterView,
    CurdPlan,
    CurdPlanWriterView,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResultWriterView,
    SemanticCurdWriterView,
)
from easy_cheese_schemas.mold_cook import (
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookMode,
)
from easy_cheese_schemas.schema_runtime import (
    FORK_TASTE_VERDICT_SCHEMA_URI,
    TASTE_LEDGER_SCHEMA_URI,
    supported_version_for,
)

from tests.python.test_mold_cook_producer import (
    finalize_fixture,
    make_approval,
    make_planner_result,
    make_spec,
    taste_fixture,
)


def _requirement_ids(outcome: FinalizationOutcome) -> set[str]:
    requirements = cast(Sequence[Mapping[str, object]], outcome.payload["requirements"])
    return {str(item["requirement_id"]) for item in requirements}


def _handoff_coverage(outcome: FinalizationOutcome) -> Mapping[str, object]:
    handoff = cast(Mapping[str, object], outcome.payload["handoff"])
    return cast(Mapping[str, object], handoff["coverage"])


def test_retained_artifact_resolves_from_the_shared_store(tmp_path: Path) -> None:
    """Finding 28: one retention layout, readable by the consumer's resolver."""
    root = tmp_path / "artifacts"
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    accepted = accept_mold_cook_handoff(
        root / "pointers" / "operation-1.json", artifact_root=root
    )
    reference = cast(MoldCookHandoff, accepted.canonical.value).spec_ref
    digest = reference.digest.removeprefix("sha256:")

    retained = root / f"sha256-{digest}"
    assert retained.is_file()
    assert not (tmp_path / "mold-artifacts").exists()
    assert not (root / "mold-artifacts").exists()

    resolved = resolve_artifact(reference, artifact_directory=root)
    assert Path(resolved.path) == retained
    assert resolved.content == retained.read_bytes()


def test_taste_ledger_retains_through_the_verifying_path_with_its_label(
    tmp_path: Path,
) -> None:
    """A ledger is a bare JSON list, and its label survives retention."""
    root = tmp_path / "artifacts"
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    accepted = accept_mold_cook_handoff(
        root / "pointers" / "operation-1.json", artifact_root=root
    )
    ledger_ref = cast(MoldCookHandoff, accepted.canonical.value).taste_ledger_ref
    assert ledger_ref is not None
    assert ledger_ref.schema_uri == TASTE_LEDGER_SCHEMA_URI

    resolved = resolve_artifact(ledger_ref, artifact_directory=root)
    # The retained bytes are a JSON list, so retention verified the label
    # instead of skipping the check.
    assert resolved.content == canonical_bytes([])


def test_failed_retention_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 28: the store's failure path is Mold's failure path."""

    def failing_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("replace refused")

    monkeypatch.setattr("easy_cheese.shared.artifacts.os.replace", failing_replace)
    root = tmp_path / "artifacts"

    with pytest.raises(FinalizationError, match="could not retain spec artifact"):
        _ = producer._persist(  # pyright: ignore[reportPrivateUsage]
            root,
            value=b"{}",
            role="spec",
            media_type="text/markdown",
        )

    assert list(root.iterdir()) == []


def test_malformed_planner_mapping_names_the_failing_path() -> None:
    """Finding 62: structuring failures are qualified by the host key path."""
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
                            check="pytest tests/python/test_mold_producer_store.py",
                        )
                    ],
                )
            ],
        ),
    )

    with pytest.raises(FinalizationError, match=r"invalid artifacts\.spec"):
        _ = normalize_planner_result(
            request,
            writer,
            plan_id="plan-1",
            curd_ids={"core": "curd-1"},
            artifacts={"spec": {"artifact_id": "spec-1"}},
        )


def test_host_coverage_is_derived_and_published(tmp_path: Path) -> None:
    """Finding 32: the handoff carries the coverage Mold proposed."""
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    coverage = _handoff_coverage(outcome)
    assert list(cast(Sequence[str], coverage["curd_ids"])) == ["curd-1"]


def test_widened_approval_coverage_is_refused(tmp_path: Path) -> None:
    """Finding 32: an approval cannot widen the scope the host proposed."""
    spec = make_spec(tmp_path)
    planner = make_planner_result()
    widened = cast(Callable[..., MoldCookCoverage], MoldCookCoverage)(
        curd_ids=["curd-1", "curd-2"],
    )
    approval = make_approval(tmp_path, spec, plan=planner, coverage=widened)

    outcome = finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.FULL,
        approval=approval,
        planner_result=planner,
        plan=cast(CurdPlan, planner.plan),
        taste_result=taste_fixture(spec),
        decision_ledger=(),
    )

    assert outcome.status == "saved-not-ready"
    assert "coverage-binding" in _requirement_ids(outcome)
    assert not (tmp_path / "artifacts" / "pointers" / "operation-1.json").exists()


def test_explicit_proposed_coverage_mapping_is_structured(tmp_path: Path) -> None:
    """Finding 32: an explicit host coverage overrides the derived value."""
    spec = make_spec(tmp_path)
    planner = make_planner_result()
    approval = make_approval(tmp_path, spec, plan=planner)

    outcome = finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.FULL,
        approval=approval,
        planner_result=planner,
        plan=cast(CurdPlan, planner.plan),
        proposed_coverage={"curd_ids": ["curd-1"]},
        taste_result=taste_fixture(spec),
        decision_ledger=(),
    )

    assert outcome.status == "ready"
    coverage = _handoff_coverage(outcome)
    assert list(cast(Sequence[str], coverage["curd_ids"])) == ["curd-1"]


def test_malformed_proposed_coverage_blocks_instead_of_raising(tmp_path: Path) -> None:
    """Host coverage is evidence, so a malformed value blocks rather than raises."""
    spec = make_spec(tmp_path)
    planner = make_planner_result()
    approval = make_approval(tmp_path, spec, plan=planner)

    outcome = finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.FULL,
        approval=approval,
        planner_result=planner,
        plan=cast(CurdPlan, planner.plan),
        proposed_coverage={"curd_ids": [7]},
        taste_result=taste_fixture(spec),
        decision_ledger=(),
    )

    assert outcome.status == "saved-not-ready"
    assert "host-coverage" in _requirement_ids(outcome)


def test_contract_paths_outside_the_artifact_root_are_read(tmp_path: Path) -> None:
    """A Mold command input is an operator path, not a retained artifact."""
    spec = make_spec(tmp_path)
    planner = make_planner_result()
    approval_path = tmp_path / "approval.json"
    planner_path = tmp_path / "planner.json"
    plan_path = tmp_path / "plan.json"
    _ = approval_path.write_bytes(
        canonical_bytes(make_approval(tmp_path, spec, plan=planner))
    )
    _ = planner_path.write_bytes(canonical_bytes(planner))
    _ = plan_path.write_bytes(canonical_bytes(cast(CurdPlan, planner.plan)))

    outcome = finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.FULL,
        approval=approval_path,
        planner_result=planner_path,
        plan=plan_path,
        taste_result=taste_fixture(spec),
        decision_ledger=(),
    )

    assert outcome.status == "ready"


def test_oversized_json_input_is_rejected_by_the_bounded_reader(tmp_path: Path) -> None:
    """Finding 60: every JSON input Mold reads is size bounded."""
    spec = make_spec(tmp_path)
    planner = make_planner_result()
    oversized = tmp_path / "coverage.json"
    filler = b"0," * ((MAX_ARTIFACT_BYTES // 2) + 1)
    _ = oversized.write_bytes(b"[" + filler + b"0]")
    assert oversized.stat().st_size > MAX_ARTIFACT_BYTES

    outcome = finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="operation-1",
        request_id="request-1",
        mode=MoldCookMode.FULL,
        approval=make_approval(tmp_path, spec, plan=planner),
        planner_result=planner,
        plan=cast(CurdPlan, planner.plan),
        proposed_coverage=oversized,
        taste_result=taste_fixture(spec),
        decision_ledger=(),
    )

    assert outcome.status == "saved-not-ready"
    requirements = cast(Sequence[Mapping[str, object]], outcome.payload["requirements"])
    reported = next(
        str(item["description"])
        for item in requirements
        if item["requirement_id"] == "host-coverage"
    )
    assert f"exceeds {MAX_ARTIFACT_BYTES} bytes" in reported


def test_written_documents_are_size_bounded(tmp_path: Path) -> None:
    """An over-limit payload is refused before any bytes reach the tree."""
    target = tmp_path / "oversized.json"

    with pytest.raises(FinalizationError, match=f"exceeds {MAX_ARTIFACT_BYTES} bytes"):
        producer._write_bounded(  # pyright: ignore[reportPrivateUsage]
            target, b"0" * (MAX_ARTIFACT_BYTES + 1)
        )

    assert not target.exists()


def test_taste_verdict_artifact_retains_with_its_schema_label(tmp_path: Path) -> None:
    """The retained taste verdict keeps the schema label the handoff requires."""
    root = tmp_path / "artifacts"
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    accepted = accept_mold_cook_handoff(
        root / "pointers" / "operation-1.json", artifact_root=root
    )
    handoff = cast(MoldCookHandoff, accepted.canonical.value)
    reference = handoff.taste_verdict_ref
    assert reference is not None
    assert reference.schema_uri == FORK_TASTE_VERDICT_SCHEMA_URI

    resolved = resolve_artifact(reference, artifact_directory=root)
    assert resolved.content == Path(resolved.path).read_bytes()
