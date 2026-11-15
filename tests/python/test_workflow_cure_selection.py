"""A partial cure validates bindings against the selected curds only.

`skills/cure/SKILL.md` step 3 dispatches one confirmed diagnosis per selected
curd. The binding check must therefore expect the dependency-closed selection
when `curd_ids` is supplied, and the whole plan when it is not.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from easy_cheese.shared.workflow import bind_diagnosis, cure, plan
from easy_cheese_schemas.contracts import (
    ArtifactRef,
    BoundedScope,
    CriterionWriterView,
    CurdPlan,
    CurdPlanWriterView,
    DiagnosisCause,
    DiagnosisDisposition,
    DiagnosisResult,
    EvidenceKind,
    EvidenceRef,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResultWriterView,
    Reproduction,
    ReproductionDisposition,
    SemanticCurdWriterView,
    SourceLocation,
)
from easy_cheese_schemas.schema_runtime import supported_version_for


class Dispatched(Exception):
    """Raised by every executor: validation passed and execution started."""


def dispatched(_value: object) -> object:
    raise Dispatched


def source_artifact(root: Path) -> ArtifactRef:
    payload = b"approved workflow contract\n"
    _ = (root / "spec.md").write_bytes(payload)
    return ArtifactRef(
        artifact_id="source-artifact",
        role="source",
        uri="repo://spec.md",
        digest=f"sha256:{hashlib.sha256(payload).hexdigest()}",
        size_bytes=len(payload),
        media_type="text/markdown",
    )


def curd_view(
    key: str,
    path: str,
    *,
    dependencies: tuple[str, ...] = (),
) -> SemanticCurdWriterView:
    return SemanticCurdWriterView(
        key=key,
        outcome=f"Execute the {key} workflow curd",
        scope=BoundedScope(paths=[path]),
        input_keys=["source"],
        outputs=[f"A verified {key} artifact"],
        dependencies=dependencies,
        criteria=[
            CriterionWriterView(
                description=f"The {key} artifact is verified",
                check=f"pytest tests/test_{key}.py",
            )
        ],
    )


def two_curd_plan(root: Path, *, dependency_order: bool = False) -> CurdPlan:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    request = PlannerRequest(
        contract_version=version,
        request_id="cure-selection-request",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Implement two independent workflow curds",
    )
    result = plan(
        request,
        lambda _request: PlannerResultWriterView(
            disposition=PlannerDisposition.COMPLETE,
            plan=CurdPlanWriterView(
                objective="Implement two independent workflow curds",
                curds=(
                    [
                        curd_view("leaf", "src/leaf.py", dependencies=("root",)),
                        curd_view("root", "src/root.py"),
                    ]
                    if dependency_order
                    else [
                        # Neither curd declares a dependency, so either one is a
                        # dependency-closed selection on its own.
                        curd_view("first", "src/first.py"),
                        curd_view("second", "src/second.py"),
                    ]
                ),
            ),
        ),
        artifacts={"source": source_artifact(root)},
    )
    assert result.plan is not None
    return result.plan


def confirmed_diagnosis(source: ArtifactRef, curd_id: str) -> DiagnosisResult:
    version = supported_version_for(DiagnosisResult)
    assert version is not None
    evidence = EvidenceRef(
        evidence_id=f"diagnosis-source-{curd_id}",
        kind=EvidenceKind.SOURCE,
        artifact=source,
        summary="Source-bound diagnosis evidence",
    )
    return DiagnosisResult(
        contract_version=version,
        diagnosis_id=f"diagnosis-{curd_id}",
        disposition=DiagnosisDisposition.CONFIRMED,
        symptom="The workflow criterion failed",
        reproduction=Reproduction(
            status=ReproductionDisposition.REPRODUCED,
            steps=["Run the workflow verification"],
            observed="The workflow criterion failed",
            evidence=[evidence],
        ),
        hypotheses=[],
        confirmed_cause=DiagnosisCause(
            summary="The workflow output did not satisfy its criterion",
            evidence=[evidence],
            location=SourceLocation(
                artifact_id=source.artifact_id,
                path="src/first.py",
                start_line=1,
                end_line=1,
            ),
        ),
        regression_seam=SourceLocation(
            artifact_id=source.artifact_id,
            path="src/first.py",
            start_line=1,
            end_line=1,
        ),
    )


def test_partial_cure_accepts_bindings_for_the_selection_only(tmp_path: Path) -> None:
    curd_plan = two_curd_plan(tmp_path)
    selected = curd_plan.curds[0]
    source = source_artifact(tmp_path)
    binding = bind_diagnosis(
        curd_plan, selected, confirmed_diagnosis(source, selected.curd_id)
    )
    events: list[str] = []

    def record(label: str):
        def dispatch(_value: object) -> object:
            events.append(label)
            raise Dispatched

        return dispatch

    # Reaching an executor proves the binding check accepted one binding for
    # the one selected curd instead of demanding a binding per plan curd.
    _ = cure(
        curd_plan,
        {selected.curd_id: binding},
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_writer=record("writer"),
        dispatch_review=record("review"),
        dispatch_diagnosis=record("diagnosis"),
        curd_ids=[selected.curd_id],
    )

    assert events[0] == "writer"


def test_cure_dispatches_dependencies_before_a_declared_leaf(tmp_path: Path) -> None:
    curd_plan = two_curd_plan(tmp_path, dependency_order=True)
    assert tuple(curd.outcome for curd in curd_plan.curds) == (
        "Execute the leaf workflow curd",
        "Execute the root workflow curd",
    )
    source = source_artifact(tmp_path)
    bindings = {
        curd.curd_id: bind_diagnosis(
            curd_plan,
            curd,
            confirmed_diagnosis(source, curd.curd_id),
        )
        for curd in curd_plan.curds
    }
    dispatches: list[str] = []

    def record_writer(context: Mapping[str, object]) -> object:
        dispatches.append(str(context["outcome"]))
        raise Dispatched

    _ = cure(
        curd_plan,
        bindings,
        repository_root=tmp_path,
        artifact_directory=tmp_path / "artifacts",
        dispatch_writer=record_writer,
        dispatch_review=dispatched,
        dispatch_diagnosis=dispatched,
    )

    assert dispatches == [
        "Execute the root workflow curd",
        "Execute the leaf workflow curd",
    ]


def test_whole_plan_cure_still_demands_a_binding_per_curd(tmp_path: Path) -> None:
    curd_plan = two_curd_plan(tmp_path)
    selected = curd_plan.curds[0]
    source = source_artifact(tmp_path)
    binding = bind_diagnosis(
        curd_plan, selected, confirmed_diagnosis(source, selected.curd_id)
    )

    with pytest.raises(
        ValueError, match="diagnosis bindings must match plan curds exactly"
    ):
        _ = cure(
            curd_plan,
            {selected.curd_id: binding},
            repository_root=tmp_path,
            artifact_directory=tmp_path / "artifacts",
            dispatch_writer=dispatched,
            dispatch_review=dispatched,
            dispatch_diagnosis=dispatched,
        )


def test_partial_cure_rejects_a_binding_outside_the_selection(tmp_path: Path) -> None:
    curd_plan = two_curd_plan(tmp_path)
    selected, other = curd_plan.curds[0], curd_plan.curds[1]
    source = source_artifact(tmp_path)
    binding = bind_diagnosis(
        curd_plan, other, confirmed_diagnosis(source, other.curd_id)
    )

    with pytest.raises(
        ValueError, match="diagnosis bindings must match plan curds exactly"
    ):
        _ = cure(
            curd_plan,
            {other.curd_id: binding},
            repository_root=tmp_path,
            artifact_directory=tmp_path / "artifacts",
            dispatch_writer=dispatched,
            dispatch_review=dispatched,
            dispatch_diagnosis=dispatched,
            curd_ids=[selected.curd_id],
        )
