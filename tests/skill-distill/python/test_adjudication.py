from dataclasses import dataclass, fields
from typing import Any, Mapping

import pytest

from skill_distill.adjudication import (
    AnnotationLifecycleError,
    HumanRelationLabel,
    LlmRelationLabel,
    export_llm_pairs,
    freeze_human_labels,
    record_llm_labels,
    reconcile,
)
from skill_distill.contracts import (
    AnnotationV1,
    DistillationRun,
    RelationAdjudication,
    RelationKind,
    RunState,
)
from skill_distill.obligations import (
    ObligationAtomV1,
    ObligationCategory,
    Polarity,
    SourceSpan,
)

FROZEN_AT = "2026-07-26T12:00:00Z"


@dataclass(frozen=True)
class SourcePair:
    pair_id: str
    left: Mapping[str, Any]
    right: Mapping[str, Any]


@dataclass(frozen=True)
class UncommittedFrozenRun:
    run_id: str = "run-1"
    state: RunState = RunState.HUMAN_FROZEN
    human_labels_digest: str | None = None
    human_labels_frozen_at: str | None = None


def source_pair():
    return SourcePair(
        "pair-1",
        {"source_span": {"path": "left.md", "start": 1, "end": 2}},
        {"source_span": {"path": "right.md", "start": 7, "end": 9}},
    )


def atom():
    return ObligationAtomV1(
        ObligationCategory.ROUTING,
        Polarity.REQUIRED,
        "route",
        "task",
        "always",
        0,
        SourceSpan("left.md", 1, 2),
    )


def labels(relation: RelationKind = RelationKind.EQUIVALENT):
    atom_label = atom()
    human = (HumanRelationLabel("pair-1", relation, "first-human", (atom_label,)),)
    llm = (LlmRelationLabel("pair-1", relation, (atom_label,)),)
    return human, llm


def freeze(run: DistillationRun, human):
    return freeze_human_labels(run, human, frozen_at=FROZEN_AT)


def test_lifecycle_freezes_before_source_only_export_and_reconciles():
    prepared = DistillationRun("run-1", RunState.PREPARED)
    human, llm = labels()

    frozen = freeze(prepared, human)
    payload = export_llm_pairs(frozen, (source_pair(),))

    assert frozen.state is RunState.HUMAN_FROZEN
    assert frozen.human_labels_frozen_at == FROZEN_AT
    assert {field.name for field in fields(payload[0])} == {
        "pair_id", "left_source_span", "right_source_span"
    }
    assert payload[0].left_source_span == SourceSpan("left.md", 1, 2)

    recorded = record_llm_labels(frozen, llm)
    decision = RelationAdjudication(
        "pair-1", "second-human", RelationKind.EQUIVALENT, {}, "confirmed"
    )
    result = reconcile(recorded, human, llm, (decision,))

    assert result.run.state is RunState.RECONCILED
    assert isinstance(result.annotations[0], AnnotationV1)
    assert result.annotations[0].reconciliation["rewrite_eligible"]


def test_export_rejects_human_freeze_without_a_commitment():
    with pytest.raises(ValueError, match="digest and timestamp"):
        export_llm_pairs(UncommittedFrozenRun(), (source_pair(),))


@pytest.mark.parametrize(
    "operation",
    [
        lambda run: export_llm_pairs(run, (source_pair(),)),
        lambda run: record_llm_labels(run, labels()[1]),
        lambda run: reconcile(run, *labels(), ()),
    ],
)
def test_invalid_transitions_fail_without_mutating_the_run(operation):
    prepared = DistillationRun("run-1", RunState.PREPARED)

    with pytest.raises(AnnotationLifecycleError):
        operation(prepared)

    assert prepared.state is RunState.PREPARED
    assert prepared.human_labels_digest is None
    assert prepared.llm_labels_digest is None
    assert prepared.human_labels_frozen_at is None


def test_reconciliation_verifies_both_stored_digests():
    human, llm = labels()
    frozen = freeze(DistillationRun("run-1", RunState.PREPARED), human)
    recorded = record_llm_labels(frozen, llm)
    altered = (HumanRelationLabel("pair-1", RelationKind.CONFLICT, "first-human"),)

    with pytest.raises(ValueError, match="human label digest"):
        reconcile(recorded, altered, llm, ())


def test_second_human_is_required_for_all_compression_positive_pairs():
    human, llm = labels(RelationKind.SHARED_SHELL)
    frozen = freeze(DistillationRun("run-1", RunState.PREPARED), human)
    recorded = record_llm_labels(frozen, llm)

    with pytest.raises(ValueError, match="requires second-human adjudication"):
        reconcile(recorded, human, llm, ())

    same_human = RelationAdjudication(
        "pair-1", "first-human", RelationKind.SHARED_SHELL, {}, "confirmed"
    )
    with pytest.raises(ValueError, match="must be a second human"):
        reconcile(recorded, human, llm, (same_human,))


def test_reconciliation_rejects_adjudication_for_an_unknown_pair_id():
    human, llm = labels()
    frozen = freeze(DistillationRun("run-1", RunState.PREPARED), human)
    recorded = record_llm_labels(frozen, llm)
    stray = RelationAdjudication(
        "pair-unknown", "second-human", RelationKind.EQUIVALENT, {}, "confirmed"
    )

    with pytest.raises(ValueError, match="outside the label pairs"):
        reconcile(recorded, human, llm, (stray,))


def test_shared_shell_is_eligible_after_second_human_adjudication():
    human, llm = labels(RelationKind.SHARED_SHELL)
    frozen = freeze(DistillationRun("run-1", RunState.PREPARED), human)
    recorded = record_llm_labels(frozen, llm)
    adjudication = RelationAdjudication(
        "pair-1", "second-human", RelationKind.SHARED_SHELL, {}, "confirmed"
    )

    annotation = reconcile(recorded, human, llm, (adjudication,)).annotations[0]

    assert annotation.reconciliation["complete"]
    assert annotation.reconciliation["rewrite_eligible"]


def test_unresolved_atom_relations_are_incomplete_and_ineligible():
    human = (HumanRelationLabel("pair-1", RelationKind.EQUIVALENT, "first-human"),)
    llm = (LlmRelationLabel("pair-1", RelationKind.EQUIVALENT, (atom(),)),)
    frozen = freeze(DistillationRun("run-1", RunState.PREPARED), human)
    recorded = record_llm_labels(frozen, llm)
    adjudication = RelationAdjudication(
        "pair-1", "second-human", RelationKind.EQUIVALENT, {}, "confirmed"
    )

    annotation = reconcile(recorded, human, llm, (adjudication,)).annotations[0]

    assert annotation.status == "incomplete"
    assert not annotation.reconciliation["rewrite_eligible"]


def test_reconciliation_accepts_mappings_and_returns_immutable_contracts():
    human = ({"pair_id": "pair-1", "relation": "conflict", "reviewer": "first"},)
    llm = ({"pair_id": "pair-1", "relation": "conflict", "atoms": ()},)
    frozen = freeze(DistillationRun("run-1", RunState.PREPARED), human)
    recorded = record_llm_labels(frozen, llm)

    annotation = reconcile(recorded, human, llm, ()).annotations[0]

    assert isinstance(annotation, AnnotationV1)
    assert annotation.reconciliation["resolved_relation"] is RelationKind.CONFLICT
    with pytest.raises(TypeError):
        annotation.reconciliation["rewrite_eligible"] = True