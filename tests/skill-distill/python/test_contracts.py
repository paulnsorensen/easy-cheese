"""Contract invariants owned by the distillation pilot's first curd."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from skill_distill.contracts import DatasetV1, PairEvidenceV1, RunState


def test_dataset_evidence_is_deeply_immutable() -> None:
    source = {"path": "skills/age/SKILL.md", "heading_path": ["Age"]}
    pair = PairEvidenceV1(
        pair_id="pair-1",
        left=source,
        right={"path": "skills/cure/SKILL.md"},
        lane="semantic",
        detector="cosine",
        kind="semantic",
        graph={"disconnected": True},
        cosine=0.8,
        duplicate_tokens_estimate=7,
        disposition="advisory",
        selection="review",
        score_decile=8,
        graph_class="disconnected",
        skill_family="skills/age|skills/cure",
    )
    source["path"] = "mutated"

    assert pair.left["path"] == "skills/age/SKILL.md"
    with pytest.raises(TypeError):
        pair.left["path"] = "mutated"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        pair.pair_id = "mutated"  # type: ignore[misc]
    assert DatasetV1("report", "prepare", (pair,)).schema_version == "dataset-v1"


def test_run_state_requires_the_committed_digests() -> None:
    from skill_distill.contracts import DistillationRun

    assert DistillationRun("run-1", RunState.PREPARED).state is RunState.PREPARED
    with pytest.raises(ValueError, match="human_labels_digest=True"):
        DistillationRun("run-2", RunState.HUMAN_FROZEN)
