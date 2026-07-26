from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import skill_distill.lifecycle as lifecycle

from skill_distill.contracts import RunState
from skill_distill.lifecycle import (
    LifecycleError,
    apply_proposal,
    build_proposals,
    export_pairs,
    freeze_labels,
    initialize_run,
    load_document,
    record_labels,
    require_context_path,
    score_dataset,
    validate_annotations,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix in {".yaml", ".yml"}:
        path.write_text(yaml.safe_dump(value), encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def test_lifecycle_persists_committed_transitions_and_source_only_export(tmp_path: Path) -> None:
    context = tmp_path / ".context"
    run_path = context / "run.json"
    human_path = tmp_path / "human.yml"
    llm_path = context / "llm.json"
    dataset_path = context / "dataset.json"
    export_path = context / "source-only.json"
    human = [{"pair_id": "p", "relation": "conflict", "reviewer": "human"}]
    llm = [{"pair_id": "p", "relation": "conflict", "atoms": []}]
    _write(human_path, human)
    _write(llm_path, llm)
    _write(dataset_path, {"pairs": [{
        "pair_id": "p",
        "left": {"path": "left.md", "span": {"start": 1, "end": 2}},
        "right": {"path": "right.md", "span": {"start": 3, "end": 4}},
    }]})

    initialize_run(run_path, "run")
    frozen = freeze_labels(run_path, human_path, "2026-07-26T12:00:00Z")
    exported = export_pairs(run_path, dataset_path, export_path)
    recorded = record_labels(run_path, llm_path)

    assert frozen.state is RunState.HUMAN_FROZEN
    assert recorded.state is RunState.LLM_RECORDED
    assert set(load_document(export_path)[0]) == {
        "pair_id", "left_source_span", "right_source_span"
    }
    assert exported[0].left_source_span.path == "left.md"
    assert load_document(run_path)["llm_labels_digest"]


def test_generated_paths_are_restricted_to_context(tmp_path: Path) -> None:
    with pytest.raises(LifecycleError, match="under .context"):
        require_context_path(tmp_path / "scores.json")


def test_annotation_validation_rejects_false_rewrite_authority() -> None:
    with pytest.raises(LifecycleError, match="eligibility"):
        validate_annotations([{
            "pair_id": "p",
            "human_relation": "conflict",
            "status": "reconciled",
            "reconciliation": {
                "resolved_relation": "conflict",
                "complete": True,
                "rewrite_eligible": True,
            },
        }])


def test_propose_validates_authority_tokens_and_center_before_atomic_apply(
    tmp_path: Path,
) -> None:
    context = tmp_path / ".context"
    annotations_path = context / "annotations.yaml"
    scores_path = context / "scores.json"
    drafts_path = context / "drafts.json"
    proposals = context / "proposals"
    repository = tmp_path / "repo"
    repository.mkdir()
    atom = {"action": "verify", "object": "run", "condition": "always", "order": 0}
    _write(annotations_path, [{
        "pair_id": "p",
        "human_relation": "equivalent",
        "status": "reconciled",
        "reconciliation": {
            "resolved_relation": "equivalent",
            "complete": True,
            "rewrite_eligible": True,
        },
    }])
    _write(scores_path, [{
        "pair_id": "p",
        "model_profile_digest": "models",
        "fusion_profile_digest": "fusion",
        "arctic_s": 0.1,
        "dense": 0.2,
        "sparse": 0.3,
        "colbert": 0.4,
        "fused": 0.3,
        "left_entails_right": 0.8,
        "right_entails_left": 0.7,
        "left_contradicts_right": 0.1,
        "right_contradicts_left": 0.2,
    }])
    _write(drafts_path, [{
        "pair_ids": ["p"],
        "family_id": "family",
        "relation": "equivalent",
        "members": ["a", "b"],
        "canonical_center": {
            "family_id": "family",
            "clauses": [atom],
            "member_residuals": {"a": [], "b": []},
        },
        "original_obligations": {"a": [atom], "b": [atom]},
        "original_loaded_tokens": 20,
        "variants": {
            "physical-reference": {
                "loaded_tokens": 15,
                "behavior_passed": True,
                "changes": {"result.txt": "physical"},
            },
            "compact-inline": {
                "loaded_tokens": 10,
                "behavior_passed": True,
                "changes": {"result.txt": "compact"},
            },
        },
        "behavioral_evidence": {
            "deterministic_passed": True,
            "behavior_passed": True,
            "overlap_passed": True,
            "llm_disposition": "pass",
        },
        "reversal_patch": "reverse",
    }])

    proposal_path, = build_proposals(
        annotations_path, scores_path, drafts_path, proposals
    )
    applied = apply_proposal(proposal_path, repository)

    assert load_document(proposal_path)["loaded_token_delta"] == 10
    assert applied == (repository / "result.txt",)
    assert (repository / "result.txt").read_text() == "compact"

def test_score_dataset_preserves_output_when_score_evidence_is_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context = tmp_path / ".context"
    dataset_path = context / "dataset.json"
    output_path = context / "scores.json"
    locks_path = tmp_path / "locks.json"
    fusion_path = tmp_path / "fusion.json"
    inventory_path = tmp_path / "inventory.json"
    _write(dataset_path, {"pairs": [{
        "pair_id": "pair",
        "left": {"original_excerpt": "left"},
        "right": {"original_excerpt": "right"},
    }]})
    _write(locks_path, [{"model_id": model_id} for model_id in (
        "snowflake/snowflake-arctic-embed-s",
        "BAAI/bge-m3",
        "cross-encoder/nli-deberta-v3-base",
    )])
    _write(fusion_path, {})
    _write(inventory_path, {})
    output_path.write_bytes(b"preserved scores\n")
    invalid = {
        "model_profile_digest": "models",
        "fusion_profile_digest": "fusion",
        "pair_id": "pair",
        "arctic_s": math.nan,
        "dense": 0.2,
        "sparse": 0.3,
        "colbert": 0.5,
        "fused": 0.38,
        "left_entails_right": 0.9,
        "right_entails_left": 0.8,
        "left_contradicts_right": 0.1,
        "right_contradicts_left": 0.2,
    }
    monkeypatch.setattr(lifecycle, "_contract", lambda _model, value: value)
    monkeypatch.setattr(
        lifecycle,
        "_load_adapter_module",
        lambda _path: SimpleNamespace(arctic=object(), bge=object(), nli=object()),
    )
    monkeypatch.setattr(
        lifecycle,
        "LocalScoringRunner",
        lambda *_adapters: SimpleNamespace(score=lambda *_args: (invalid,)),
    )

    with pytest.raises(LifecycleError, match="score evidence is incomplete"):
        score_dataset(
            dataset_path,
            output_path,
            tmp_path / "adapters.py",
            locks_path,
            {"arctic": Path(), "bge": Path(), "nli": Path()},
            fusion_path,
            inventory_path,
        )

    assert output_path.read_bytes() == b"preserved scores\n"
