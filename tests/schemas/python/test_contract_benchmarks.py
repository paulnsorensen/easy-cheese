from __future__ import annotations

import pytest

from easy_cheese_schemas.benchmarks import (
    BenchmarkRecord,
    BenchmarkReport,
    ContractBenchmarkInput,
    benchmark_contracts,
)
from easy_cheese_schemas.contracts import (
    AgentWriterView,
    ArtifactRef,
    BoundedContextWriterView,
    BoundedScope,
    CriterionWriterView,
    EvidenceKind,
    EvidenceRef,
    IdentityAction,
    IdentityLineage,
    CurdPlanWriterView,
    PlannerDisposition,
    PlannerResultWriterView,
    PlannerUncertaintyWriterView,
    SemanticCurdWriterView,
    UncertaintyScope,
    WriterViewKind,
)
from easy_cheese_schemas.schema_runtime import normalize_agent_output

SCHEMA_ROOT = "https://schemas.easy-cheese.dev"
PLANNER_RESULT_SCHEMA = f"{SCHEMA_ROOT}/planner-result"
CURD_PLAN_SCHEMA = f"{SCHEMA_ROOT}/curd-plan"


def _artifact(key: str, index: int) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"artifact-{key}",
        role="source",
        uri=f"repo://inputs/{key}.md",
        digest=f"sha256:{index:064x}",
        size_bytes=1_024 + index,
        media_type="text/markdown",
    )


def _planner_input(
    disposition: PlannerDisposition = PlannerDisposition.COMPLETE,
) -> ContractBenchmarkInput:
    artifact = _artifact("source", 1)
    evidence = EvidenceRef(
        evidence_id="evidence-1",
        kind=EvidenceKind.REVIEW,
        artifact=artifact,
        summary="The planner dispatch boundary is under review.",
    )
    curd = SemanticCurdWriterView(
        key="core",
        outcome="Complete the planner benchmark slice.",
        scope=BoundedScope(paths=["src/planner.py"]),
        input_keys=["source"],
        outputs=["The planner slice is materialized."],
        criteria=[
            CriterionWriterView(
                description="The planner result is canonical.",
                check="The normalized plan has host identity.",
            )
        ],
    )
    writer = AgentWriterView(
        kind=WriterViewKind.PLANNER_RESULT,
        payload=PlannerResultWriterView(
            disposition=disposition,
            plan=CurdPlanWriterView(
                objective="Measure planner-result normalization.",
                curds=[curd],
                context=BoundedContextWriterView(
                    shared_input_keys=["source"],
                    constraints=["Only the approved planner input is in scope."],
                    invariants=["Host identity is never supplied by the writer."],
                ),
            ),
            unresolved_work=(
                [
                    PlannerUncertaintyWriterView(
                        description="A later planner slice remains to be planned.",
                        scope=UncertaintyScope.OMITTED_WORK,
                        evidence_keys=["evidence-1"],
                    )
                ]
                if disposition is PlannerDisposition.PARTIAL
                else []
            ),
        ),
    )
    invocation = {
        "request_id": "planner-request-benchmark",
        "versions": {
            PLANNER_RESULT_SCHEMA: {
                "schema_uri": PLANNER_RESULT_SCHEMA,
                "major": "1",
                "minor": "0",
            }
        },
        "evidence": {"evidence-1": evidence},
        "plan": {
            "plan_id": "planner-benchmark-plan",
            "versions": {
                CURD_PLAN_SCHEMA: {
                    "schema_uri": CURD_PLAN_SCHEMA,
                    "major": "1",
                    "minor": "0",
                }
            },
            "artifacts": {"source": artifact},
            "lineages": {"core": IdentityLineage(IdentityAction.NEW)},
        },
    }
    return ContractBenchmarkInput(
        name=f"planner-result-{disposition.value}",
        writer_view=writer,
        invocation=invocation,
    )


def _review_input(
    writer_view: object,
    *,
    repair_view: object | None = None,
) -> ContractBenchmarkInput:
    schema_uri = f"{SCHEMA_ROOT}/review-result"
    invocation = {
        "review_id": "review-benchmark",
        "versions": {
            schema_uri: {
                "schema_uri": schema_uri,
                "major": "1",
                "minor": "0",
            }
        },
        "coverage": [{"target": "changed-files", "disposition": "covered"}],
    }
    return ContractBenchmarkInput(
        name="review-result",
        writer_view=writer_view,
        invocation=invocation,
        repair_view=repair_view,
    )


def _invalid_review_view() -> dict[str, object]:
    return {
        "kind": "review_result",
        "payload": {
            "disposition": "clean",
            "findings": [],
            "host_only": "must reject",
        },
    }


def _valid_review_view() -> dict[str, object]:
    return {
        "kind": "review_result",
        "payload": {"disposition": "clean", "findings": []},
    }


def test_public_benchmark_shape_accepts_only_input_and_repair_data() -> None:
    assert set(ContractBenchmarkInput.__dataclass_fields__) == {
        "name",
        "writer_view",
        "invocation",
        "repair_view",
    }
    assert set(BenchmarkRecord.__dataclass_fields__) == {
        "name",
        "first_pass_valid",
        "repair_attempted",
        "repair_succeeded",
        "writer_bytes",
        "canonical_bytes",
    }
    assert set(BenchmarkReport.__dataclass_fields__) == {
        "records",
        "first_pass_validity",
        "repair_rate",
    }


@pytest.mark.parametrize(
    "disposition",
    [PlannerDisposition.COMPLETE, PlannerDisposition.PARTIAL],
)
def test_planner_representatives_use_real_normalized_canonical_bytes(
    disposition: PlannerDisposition,
) -> None:
    input_ = _planner_input(disposition)
    expected = normalize_agent_output(input_.writer_view, input_.invocation)

    report = benchmark_contracts((input_,))
    record = report.records[0]

    assert report == benchmark_contracts((input_,))
    assert record.name == f"planner-result-{disposition.value}"
    assert record.first_pass_valid is True
    assert record.repair_attempted is False
    assert record.repair_succeeded is False
    assert record.writer_bytes > 0
    assert record.canonical_bytes == len(expected.canonical_bytes)
    assert report.first_pass_validity == 1.0
    assert report.repair_rate == 0.0


def test_invalid_unrepaired_input_is_reported_without_raising() -> None:
    report = benchmark_contracts((_review_input(_invalid_review_view()),))
    record = report.records[0]

    assert record.first_pass_valid is False
    assert record.repair_attempted is False
    assert record.repair_succeeded is False
    assert record.writer_bytes > 0
    assert record.canonical_bytes is None
    assert report.first_pass_validity == 0.0
    assert report.repair_rate == 0.0


def test_repair_attempt_and_success_are_derived_from_normalization() -> None:
    input_ = _review_input(
        _invalid_review_view(),
        repair_view=_valid_review_view(),
    )
    expected = normalize_agent_output(input_.repair_view, input_.invocation)

    record = benchmark_contracts((input_,)).records[0]

    assert record.first_pass_valid is False
    assert record.repair_attempted is True
    assert record.repair_succeeded is True
    assert record.canonical_bytes == len(expected.canonical_bytes)


def test_invalid_repair_is_recorded_and_repair_rate_aggregates_invalid_cases() -> None:
    repaired = _review_input(
        _invalid_review_view(),
        repair_view=_valid_review_view(),
    )
    unrepaired = _review_input(_invalid_review_view())
    invalid_repair = _review_input(
        _invalid_review_view(),
        repair_view=_invalid_review_view(),
    )

    report = benchmark_contracts((repaired, unrepaired, invalid_repair))

    assert report.first_pass_validity == 0.0
    assert report.repair_rate == pytest.approx(1 / 2)
    assert report.records[2].repair_attempted is True
    assert report.records[2].repair_succeeded is False
    assert report.records[2].canonical_bytes is None


def test_repair_rate_uses_successful_repairs_over_attempts() -> None:
    report = benchmark_contracts(
        (
            _review_input(_invalid_review_view()),
            _review_input(
                _invalid_review_view(),
                repair_view=_valid_review_view(),
            ),
        )
    )

    assert report.first_pass_validity == 0.0
    assert report.repair_rate == 1.0


def test_repair_candidate_is_not_attempted_after_valid_first_pass() -> None:
    input_ = _review_input(
        _valid_review_view(),
        repair_view=_invalid_review_view(),
    )

    record = benchmark_contracts((input_,)).records[0]

    assert record.first_pass_valid is True
    assert record.repair_attempted is False
    assert record.repair_succeeded is False
    assert record.canonical_bytes is not None
