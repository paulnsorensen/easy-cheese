"""Filesystem orchestration for the evidence-gated distillation lifecycle."""

from __future__ import annotations

import importlib.util
import json
import math
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Mapping, Sequence

import yaml

from .adjudication import (
    export_llm_pairs,
    freeze_human_labels,
    reconcile,
    record_llm_labels,
)
from .canonical import validate_family
from .contracts import (
    CanonicalCenter,
    DependencyInventoryV1,
    DistillationFamily,
    DistillationRun,
    FusionProfile,
    ModelLock,
    ProposalV1,
    RelationKind,
    RunState,
)
from .interaction import InteractionResult, gate_interactions
from .representations import RepresentationCandidate, choose_representation
from .retrieval import LocalScoringRunner, ScoringPair
from .transaction import apply_family


class LifecycleError(ValueError):
    """A lifecycle artifact or command violates the locked protocol."""


def require_context_path(path: Path) -> Path:
    """Return a normalized evidence path only when it lives under `.context`."""
    resolved = path.expanduser().resolve()
    if ".context" not in resolved.parts:
        raise LifecycleError(f"generated evidence must be written under .context: {path}")
    return resolved


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    return value


def load_document(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    value = yaml.safe_load(text) if path.suffix in {".yaml", ".yml"} else json.loads(text)
    if value is None:
        raise LifecycleError(f"empty lifecycle document: {path}")
    return value


def _encoded(path: Path, value: Any) -> bytes:
    plain = _plain(value)
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_dump(plain, sort_keys=True, allow_unicode=True).encode()
    return (json.dumps(plain, sort_keys=True, indent=2) + "\n").encode()


def write_evidence(path: Path, value: Any) -> Path:
    target = require_context_path(path)
    apply_family("lifecycle-evidence", {target: _encoded(target, value)}, lambda: True)
    return target


def _run(value: Mapping[str, Any]) -> DistillationRun:
    return DistillationRun(
        run_id=str(value["run_id"]),
        state=RunState(value["state"]),
        human_labels_digest=value.get("human_labels_digest"),
        llm_labels_digest=value.get("llm_labels_digest"),
        human_labels_frozen_at=value.get("human_labels_frozen_at"),
    )


def initialize_run(path: Path, run_id: str) -> DistillationRun:
    run = DistillationRun(run_id, RunState.PREPARED)
    write_evidence(path, run)
    return run


def freeze_labels(run_path: Path, labels_path: Path, frozen_at: str) -> DistillationRun:
    run_path = require_context_path(run_path)
    run = freeze_human_labels(_run(load_document(run_path)), load_document(labels_path), frozen_at=frozen_at)
    write_evidence(run_path, run)
    return run


def _source_pair(value: Mapping[str, Any]) -> SimpleNamespace:
    def side(item: Mapping[str, Any]) -> dict[str, Any]:
        span = item.get("source_span", item.get("span"))
        if not isinstance(span, Mapping):
            raise LifecycleError("dataset pair side is missing a source span")
        return {"source_span": {"path": item["path"], "start": span["start"], "end": span["end"]}}

    return SimpleNamespace(pair_id=value["pair_id"], left=side(value["left"]), right=side(value["right"]))


def export_pairs(run_path: Path, dataset_path: Path, output_path: Path) -> tuple[Any, ...]:
    dataset_path = require_context_path(dataset_path)
    run = _run(load_document(require_context_path(run_path)))
    dataset = load_document(dataset_path)
    pairs = export_llm_pairs(run, tuple(_source_pair(pair) for pair in dataset["pairs"]))
    write_evidence(output_path, pairs)
    return pairs


def record_labels(run_path: Path, labels_path: Path) -> DistillationRun:
    labels_path = require_context_path(labels_path)
    run_path = require_context_path(run_path)
    run = record_llm_labels(_run(load_document(run_path)), load_document(labels_path))
    write_evidence(run_path, run)
    return run


def reconcile_labels(
    run_path: Path,
    human_path: Path,
    llm_path: Path,
    adjudications_path: Path,
    output_path: Path,
) -> tuple[Any, ...]:
    run_path = require_context_path(run_path)
    llm_path = require_context_path(llm_path)
    result = reconcile(
        _run(load_document(run_path)),
        load_document(human_path),
        load_document(llm_path),
        load_document(adjudications_path),
    )
    output_path = require_context_path(output_path)
    apply_family(
        f"reconcile-{result.run.run_id}",
        {run_path: _encoded(run_path, result.run), output_path: _encoded(output_path, result.annotations)},
        lambda: True,
    )
    return result.annotations


def validate_annotations(values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not values:
        raise LifecycleError("annotations cannot be empty")
    pair_ids = [str(value["pair_id"]) for value in values]
    if len(pair_ids) != len(set(pair_ids)):
        raise LifecycleError("annotations must contain unique pair IDs")
    eligible = []
    for value in values:
        reconciliation = value.get("reconciliation", {})
        relation = RelationKind(reconciliation.get("resolved_relation", value["human_relation"]))
        complete = value.get("status") == "reconciled" and reconciliation.get("complete") is True
        rewrite_eligible = reconciliation.get("rewrite_eligible") is True
        expected = complete and relation in {RelationKind.EQUIVALENT, RelationKind.SHARED_SHELL}
        if rewrite_eligible != expected:
            raise LifecycleError(f"annotation eligibility is inconsistent: {value['pair_id']}")
        if expected:
            eligible.append(value["pair_id"])
    return {"annotation_count": len(values), "eligible_pair_ids": sorted(eligible), "valid": True}


_SCORE_FIELDS = (
    "arctic_s",
    "dense",
    "sparse",
    "colbert",
    "fused",
    "left_entails_right",
    "right_entails_left",
    "left_contradicts_right",
    "right_contradicts_left",
)


def validate_score_coverage(
    annotations: Sequence[Mapping[str, Any]], scores: Sequence[Mapping[str, Any]]
) -> None:
    annotation_ids = {value["pair_id"] for value in annotations}
    score_ids = [value["pair_id"] for value in scores]
    if len(score_ids) != len(set(score_ids)) or set(score_ids) != annotation_ids:
        raise LifecycleError("scores must cover every annotated pair exactly once")
    profiles = {
        (value["model_profile_digest"], value["fusion_profile_digest"])
        for value in scores
    }
    if len(profiles) != 1:
        raise LifecycleError("scores must share one model and fusion profile")
    for value in scores:
        if any(
            isinstance(value.get(name), bool)
            or not isinstance(value.get(name), int | float)
            or not math.isfinite(value[name])
            for name in _SCORE_FIELDS
        ):
            raise LifecycleError(f"score evidence is incomplete: {value['pair_id']}")


def _contract(model: type, value: Mapping[str, Any]):
    names = model.__dataclass_fields__  # type: ignore[attr-defined]
    return model(**{name: value[name] for name in names if name in value and name != "schema_version"})


def _load_adapter_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("skill_distill_local_adapters", path)
    if spec is None or spec.loader is None:
        raise LifecycleError(f"cannot load local adapter module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not all(hasattr(module, name) for name in ("arctic", "bge", "nli")):
        raise LifecycleError("adapter module must expose arctic, bge, and nli adapters")
    return module


def score_dataset(
    dataset_path: Path,
    output_path: Path,
    adapter_module: Path,
    locks_path: Path,
    snapshots: Mapping[str, Path],
    fusion_path: Path,
    inventory_path: Path,
) -> tuple[Any, ...]:
    output_path = require_context_path(output_path)
    dataset_path = require_context_path(dataset_path)
    dataset = load_document(dataset_path)
    pairs = tuple(
        ScoringPair(pair["pair_id"], pair["left"]["original_excerpt"], pair["right"]["original_excerpt"])
        for pair in dataset["pairs"]
    )
    locks = load_document(locks_path)
    by_id = {value["model_id"]: _contract(ModelLock, value) for value in locks}
    from .retrieval import ARCTIC_S_MODEL, BGE_M3_MODEL, NLI_MODEL

    module = _load_adapter_module(adapter_module)
    scores = LocalScoringRunner(module.arctic, module.bge, module.nli).score(
        pairs,
        by_id[ARCTIC_S_MODEL], snapshots["arctic"],
        by_id[BGE_M3_MODEL], snapshots["bge"],
        by_id[NLI_MODEL], snapshots["nli"],
        _contract(FusionProfile, load_document(fusion_path)),
        _contract(DependencyInventoryV1, load_document(inventory_path)),
    )
    if len(scores) != len(pairs):
        raise LifecycleError("score output does not cover the complete dataset")
    write_evidence(output_path, scores)
    return scores


def build_proposals(
    annotations_path: Path,
    scores_path: Path,
    drafts_path: Path,
    output_dir: Path,
) -> tuple[Path, ...]:
    annotations_path = require_context_path(annotations_path)
    scores_path = require_context_path(scores_path)
    drafts_path = require_context_path(drafts_path)
    annotations = load_document(annotations_path)
    validate_score_coverage(annotations, load_document(scores_path))
    eligible = set(validate_annotations(annotations)["eligible_pair_ids"])
    drafts = load_document(drafts_path)
    output_dir = require_context_path(output_dir)
    written = []
    for draft in drafts:
        pair_ids = set(draft["pair_ids"])
        if not pair_ids or not pair_ids <= eligible:
            raise LifecycleError("proposal includes an incomplete or rewrite-ineligible pair")
        center_value = draft["canonical_center"]
        center = CanonicalCenter(
            center_value["family_id"], tuple(center_value["clauses"]), center_value["member_residuals"]
        )
        family = DistillationFamily(
            draft["family_id"], RelationKind(draft["relation"]), tuple(draft["members"]), center
        )
        validate_family(family, draft["original_obligations"])
        candidates = tuple(
            RepresentationCandidate(name, value["loaded_tokens"], value["behavior_passed"])
            for name, value in draft["variants"].items()
        )
        choice = choose_representation(draft["original_loaded_tokens"], candidates)
        proposal = ProposalV1(
            family.family_id,
            center,
            center.member_residuals,
            draft["variants"]["physical-reference"],
            draft["variants"]["compact-inline"],
            choice.loaded_token_savings,
            {**draft["behavioral_evidence"], "selected_representation": choice.name},
            draft["reversal_patch"],
        )
        path = output_dir / f"{proposal.family_id}.json"
        write_evidence(path, proposal)
        written.append(path)
    return tuple(written)


def apply_proposal(proposal_path: Path, repository: Path) -> tuple[Path, ...]:
    value = load_document(require_context_path(proposal_path))
    evidence = value["behavioral_evidence"]
    disposition = evidence.get("llm_disposition")
    deterministic = all(evidence.get(name) is True for name in ("deterministic_passed", "behavior_passed", "overlap_passed"))
    diagnostic = disposition == "pass" or (
        disposition in {"concern", "abstain"} and bool(evidence.get("human_disposition"))
    )
    if not deterministic or not diagnostic:
        raise LifecycleError("proposal has not passed every deterministic and diagnostic gate")
    variant = value[evidence["selected_representation"].replace("-", "_") + "_variant"]
    changes = {
        (repository / relative).resolve(): content.encode()
        for relative, content in variant["changes"].items()
    }
    root = repository.resolve()
    if any(root not in path.parents for path in changes):
        raise LifecycleError("proposal change escapes the repository")
    return apply_family(value["family_id"], changes, lambda: True).applied_paths


def verify_run(run_path: Path, evidence_path: Path) -> InteractionResult:
    evidence_path = require_context_path(evidence_path)
    run = _run(load_document(require_context_path(run_path)))
    if run.state is not RunState.RECONCILED:
        raise LifecycleError("verify requires a reconciled run")
    evidence = load_document(evidence_path)
    retained = tuple(evidence.get("retained_families", ()))
    if len(retained) != len(set(retained)):
        raise LifecycleError("interaction evidence repeats a family")
    failing_subsets = {
        tuple(sorted(subset)) for subset in evidence.get("failing_subsets", ())
    }
    if any(set(subset) - set(retained) for subset in failing_subsets):
        raise LifecycleError("interaction evidence names invalid families")
    result = gate_interactions(
        retained,
        lambda subset: tuple(sorted(subset)) not in failing_subsets,
    )
    if not result.passed:
        raise LifecycleError(f"final interaction gate failed: {', '.join(result.failing_families)}")
    return result
