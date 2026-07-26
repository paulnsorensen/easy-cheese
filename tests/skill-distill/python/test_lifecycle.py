from __future__ import annotations

import hashlib

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


TOKENIZER_DIGEST = "a" * 64


def _token_profile(
    path: str, content: str, tokens: int, identity: str = TOKENIZER_DIGEST
) -> dict[str, object]:
    return {
        "tokenizer_identity_digest": identity,
        "load_events": [{
            "role": "skill",
            "canonical_path": path,
            "content_digest": hashlib.sha256(content.encode()).hexdigest(),
            "tokenizer_identity_digest": identity,
            "token_count": tokens,
            "schema_version": "load-event-v1",
        }],
        "schema_version": "token-metric-profile-v1",
    }


def _proposal_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, dict[str, object]]:
    context = tmp_path / ".context"
    annotations_path = context / "annotations.yaml"
    scores_path = context / "scores.json"
    drafts_path = context / "drafts.json"
    proposals = context / "proposals"
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "result.txt").write_text("original", encoding="utf-8")
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
    draft: dict[str, object] = {
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
        "original_token_profile": _token_profile("result.txt", "original", 20),
        "variants": {
            "physical-reference": {
                "token_metric_profile": _token_profile("result.txt", "physical", 15),
                "behavior_passed": True,
                "changes": {"result.txt": "physical"},
            },
            "compact-inline": {
                "token_metric_profile": _token_profile("result.txt", "compact", 10),
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
    }
    return annotations_path, scores_path, drafts_path, proposals, repository, draft


def _build_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    annotations, scores, drafts, proposals, repository, draft = _proposal_fixture(tmp_path)
    _write(drafts, [draft])
    proposal, = build_proposals(annotations, scores, drafts, proposals)
    return proposal, repository, draft


def test_propose_derives_token_savings_and_applies_only_after_post_write_gate(tmp_path: Path) -> None:
    proposal_path, repository, _draft = _build_fixture(tmp_path)

    applied = apply_proposal(proposal_path, repository, lambda _root: True)

    proposal = load_document(proposal_path)
    assert proposal["loaded_token_delta"] == 10
    assert proposal["original_token_profile"]["load_events"][0]["token_count"] == 20
    assert applied == (repository / "result.txt",)
    assert (repository / "result.txt").read_text() == "compact"


@pytest.mark.parametrize("profile_name", ["original", "physical-reference", "compact-inline"])
def test_propose_rejects_empty_token_telemetry(tmp_path: Path, profile_name: str) -> None:
    annotations, scores, drafts, proposals, _repository, draft = _proposal_fixture(tmp_path)
    if profile_name == "original":
        profile = draft["original_token_profile"]
    else:
        profile = draft["variants"][profile_name]["token_metric_profile"]  # type: ignore[index]
    profile["load_events"] = []  # type: ignore[index]
    _write(drafts, [draft])

    with pytest.raises(LifecycleError, match="nonempty load events"):
        build_proposals(annotations, scores, drafts, proposals)


@pytest.mark.parametrize("location", ["original", "physical-reference"])
def test_propose_rejects_free_token_totals(tmp_path: Path, location: str) -> None:
    annotations, scores, drafts, proposals, _repository, draft = _proposal_fixture(tmp_path)
    if location == "original":
        draft["original_loaded_tokens"] = 1
    else:
        draft["variants"][location]["loaded_tokens"] = 1  # type: ignore[index]
    _write(drafts, [draft])

    with pytest.raises(LifecycleError, match="free token totals"):
        build_proposals(annotations, scores, drafts, proposals)


@pytest.mark.parametrize(("field", "value", "message"), [
    ("canonical_path", "../escape.md", "not canonical"),
    ("content_digest", "incomplete", "SHA-256"),
    ("tokenizer_identity_digest", "c" * 64, "identity drift"),
])
def test_propose_rejects_incomplete_path_and_digest_evidence(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    annotations, scores, drafts, proposals, _repository, draft = _proposal_fixture(tmp_path)
    profile = draft["variants"]["physical-reference"]["token_metric_profile"]  # type: ignore[index]
    profile["load_events"][0][field] = value  # type: ignore[index]
    _write(drafts, [draft])

    with pytest.raises(LifecycleError, match=message):
        build_proposals(annotations, scores, drafts, proposals)


def test_apply_rejects_self_approval_embedded_in_proposal(tmp_path: Path) -> None:
    proposal_path, repository, _draft = _build_fixture(tmp_path)
    proposal = load_document(proposal_path)
    proposal["behavioral_evidence"]["llm_disposition"] = "concern"
    proposal["behavioral_evidence"]["human_disposition"] = "approved"
    _write(proposal_path, proposal)

    with pytest.raises(LifecycleError, match="separate human disposition"):
        apply_proposal(proposal_path, repository, lambda _root: True)

    assert (repository / "result.txt").read_text(encoding="utf-8") == "original"


def test_apply_accepts_digest_bound_human_disposition(tmp_path: Path) -> None:
    proposal_path, repository, _draft = _build_fixture(tmp_path)
    proposal = load_document(proposal_path)
    proposal["behavioral_evidence"]["llm_disposition"] = "abstain"
    _write(proposal_path, proposal)
    disposition = proposal_path.parent / "disposition.json"
    _write(disposition, {
        "proposal_digest": hashlib.sha256(proposal_path.read_bytes()).hexdigest(),
        "decision": "approve",
        "reviewer_identity": "human@example.com",
        "reviewed_at": "2026-07-26T20:00:00Z",
        "commitment": "I reviewed and approve these exact proposal bytes.",
        "schema_version": "human-disposition-v1",
    })

    apply_proposal(proposal_path, repository, lambda _root: True, disposition)

    assert (repository / "result.txt").read_text(encoding="utf-8") == "compact"


def test_apply_rejects_disposition_for_different_proposal(tmp_path: Path) -> None:
    proposal_path, repository, _draft = _build_fixture(tmp_path)
    proposal = load_document(proposal_path)
    proposal["behavioral_evidence"]["llm_disposition"] = "concern"
    _write(proposal_path, proposal)
    disposition = proposal_path.parent / "disposition.json"
    _write(disposition, {
        "proposal_digest": "0" * 64,
        "decision": "approve",
        "reviewer_identity": "human@example.com",
        "reviewed_at": "2026-07-26T20:00:00Z",
        "commitment": "I reviewed another proposal.",
        "schema_version": "human-disposition-v1",
    })

    with pytest.raises(LifecycleError, match="does not match proposal bytes"):
        apply_proposal(proposal_path, repository, lambda _root: True, disposition)

    assert (repository / "result.txt").read_text(encoding="utf-8") == "original"


def test_failed_gate_cannot_mutate_real_unrelated_files(tmp_path: Path) -> None:
    proposal_path, repository, _draft = _build_fixture(tmp_path)
    result = repository / "result.txt"
    unrelated = repository / "unrelated.txt"
    unrelated.write_text("untouched", encoding="utf-8")

    def reject_applied_tree(mirror: Path) -> bool:
        assert (mirror / "result.txt").read_text(encoding="utf-8") == "compact"
        (mirror / "unrelated.txt").write_text("modified", encoding="utf-8")
        (mirror / "gate-created.txt").write_text("created", encoding="utf-8")
        return False

    with pytest.raises(RuntimeError, match="family gate failed"):
        apply_proposal(proposal_path, repository, reject_applied_tree)

    assert result.read_text(encoding="utf-8") == "original"
    assert unrelated.read_text(encoding="utf-8") == "untouched"
    assert not (repository / "gate-created.txt").exists()


def test_propose_rejects_variant_telemetry_not_bound_to_change_bytes(tmp_path: Path) -> None:
    annotations, scores, drafts, proposals, _repository, draft = _proposal_fixture(tmp_path)
    event = draft["variants"]["compact-inline"]["token_metric_profile"]["load_events"][0]  # type: ignore[index]
    event["content_digest"] = hashlib.sha256(b"fabricated").hexdigest()  # type: ignore[index]
    _write(drafts, [draft])

    with pytest.raises(LifecycleError, match="does not match exact bytes"):
        build_proposals(annotations, scores, drafts, proposals)


def test_propose_rejects_telemetry_path_not_in_changes(tmp_path: Path) -> None:
    annotations, scores, drafts, proposals, _repository, draft = _proposal_fixture(tmp_path)
    event = draft["variants"]["compact-inline"]["token_metric_profile"]["load_events"][0]  # type: ignore[index]
    event["canonical_path"] = "other.txt"  # type: ignore[index]
    _write(drafts, [draft])

    with pytest.raises(LifecycleError, match="paths do not match proposal changes"):
        build_proposals(annotations, scores, drafts, proposals)


def test_apply_rejects_stale_original_telemetry_before_gate(tmp_path: Path) -> None:
    proposal_path, repository, _draft = _build_fixture(tmp_path)
    (repository / "result.txt").write_text("changed after measurement", encoding="utf-8")
    gate_called = False

    def gate(_mirror: Path) -> bool:
        nonlocal gate_called
        gate_called = True
        return True

    with pytest.raises(LifecycleError, match="original token profile content digest"):
        apply_proposal(proposal_path, repository, gate)

    assert not gate_called
    assert (repository / "result.txt").read_text(encoding="utf-8") == "changed after measurement"

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
