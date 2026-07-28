"""Deterministic BGE-M3 fusion split, folds, and selection."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable

from .contracts import FusionProfile
from .retrieval import BgeM3Evidence

_WEIGHT_STEP = 20
_RECALL_FLOOR = 0.98


@dataclass(frozen=True)
class RetrievalCandidate:
    pair_id: str
    evidence: BgeM3Evidence
    relevant: bool


@dataclass(frozen=True)
class FusionExample:
    pair_id: str
    relation: str
    graph_class: str
    candidates: tuple[RetrievalCandidate, ...]


@dataclass(frozen=True)
class FoldedExample:
    example: FusionExample
    stratum: str
    fold: int | None
    held_out: bool


def validate_fusion_profile(profile: FusionProfile) -> None:
    validate_weights(profile.weights)
    if profile.candidate_cutoff < 1:
        raise ValueError("candidate_cutoff must be positive")


def fusion_profile_digest(profile: FusionProfile) -> str:
    validate_fusion_profile(profile)
    return _digest(
        {
            "split_seed": profile.split_seed,
            "fold_seed": profile.fold_seed,
            "weights": profile.weights,
            "candidate_cutoff": profile.candidate_cutoff,
            "training_digest": profile.training_digest,
            "held_out_identity": profile.held_out_identity,
        }
    )


def _stable_hash(seed: str, pair_id: str) -> str:
    return sha256(f"{seed}||{pair_id}".encode()).hexdigest()


def _strata(examples: Iterable[FusionExample]) -> dict[str, list[FusionExample]]:
    initial: dict[tuple[str, str], list[FusionExample]] = {}
    for example in examples:
        initial.setdefault((example.relation, example.graph_class), []).append(example)
    final: dict[str, list[FusionExample]] = {}
    merged_by_relation: dict[str, list[FusionExample]] = {}
    for key in sorted(initial):
        group = initial[key]
        if len(group) >= 10:
            final[f"{key[0]}|{key[1]}"] = group
        else:
            merged_by_relation.setdefault(key[0], []).extend(group)
    sparse: list[FusionExample] = []
    for relation in sorted(merged_by_relation):
        group = merged_by_relation[relation]
        if len(group) >= 10:
            final[f"{relation}|*"] = group
        else:
            sparse.extend(group)
    if sparse:
        if len(sparse) >= 10:
            final["sparse"] = sparse
        elif final:
            final[sorted(final)[0]].extend(sparse)
        else:
            final["sparse"] = sparse
    return final


def split_and_fold(
    examples: Iterable[FusionExample], split_seed: str, fold_seed: str
) -> tuple[FoldedExample, ...]:
    """Use exact strata merging, every-fifth held-out selection, and five folds."""
    assignments: list[FoldedExample] = []
    for stratum, members in sorted(_strata(examples).items()):
        ordered = sorted(members, key=lambda item: (_stable_hash(split_seed, item.pair_id), item.pair_id))
        development: list[FusionExample] = []
        for index, example in enumerate(ordered, start=1):
            if index % 5 == 0:
                assignments.append(FoldedExample(example, stratum, None, True))
            else:
                development.append(example)
        for fold, example in enumerate(
            sorted(development, key=lambda item: (_stable_hash(fold_seed, item.pair_id), item.pair_id))
        ):
            assignments.append(FoldedExample(example, stratum, fold % 5, False))
    return tuple(sorted(assignments, key=lambda item: item.example.pair_id))


def weight_grid() -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (dense / _WEIGHT_STEP, sparse / _WEIGHT_STEP, (_WEIGHT_STEP - dense - sparse) / _WEIGHT_STEP)
        for dense in range(_WEIGHT_STEP + 1)
        for sparse in range(_WEIGHT_STEP - dense + 1)
    )


def validate_weights(weights: tuple[float, float, float]) -> None:
    scaled = tuple(round(weight * _WEIGHT_STEP) for weight in weights)
    if any(weight < 0 for weight in weights) or any(
        abs(weight - value / _WEIGHT_STEP) > 1e-12 for weight, value in zip(weights, scaled)
    ) or sum(scaled) != _WEIGHT_STEP:
        raise ValueError("weights must be non-negative 0.05 increments summing to one")


def fuse(evidence: BgeM3Evidence, weights: tuple[float, float, float]) -> float:
    return sum(score * weight for score, weight in zip((evidence.dense, evidence.sparse, evidence.colbert), weights))


def _rank(example: FusionExample, weights: tuple[float, float, float]) -> tuple[RetrievalCandidate, ...]:
    return tuple(
        sorted(
            example.candidates,
            key=lambda candidate: (-fuse(candidate.evidence, weights), candidate.pair_id),
        )
    )


def _ranked_examples(
    examples: Iterable[FusionExample], weights: tuple[float, float, float]
) -> tuple[tuple[tuple[RetrievalCandidate, ...], int], ...]:
    ranked = []
    for example in examples:
        relevant = sum(candidate.relevant for candidate in example.candidates)
        if not relevant:
            raise ValueError(f"{example.pair_id} has no relevant candidate")
        ranked.append((_rank(example, weights), relevant))
    return tuple(ranked)


def _metrics(
    ranked_examples: tuple[tuple[tuple[RetrievalCandidate, ...], int], ...], cutoff: int
) -> tuple[float, float]:
    recall_total = 0.0
    mrr_total = 0.0
    count = 0
    for ranked, relevant in ranked_examples:
        sliced = ranked[:cutoff]
        recall_total += sum(candidate.relevant for candidate in sliced) / relevant
        mrr_total += next((1 / index for index, candidate in enumerate(sliced, start=1) if candidate.relevant), 0.0)
        count += 1
    if not count:
        raise ValueError("development split is empty")
    return recall_total / count, mrr_total / count


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def select_fusion(
    examples: Iterable[FusionExample], split_seed: str, fold_seed: str
) -> tuple[FusionProfile, tuple[FoldedExample, ...]]:
    """Select fusion from development folds only; held-out labels are never read here."""
    assignments = split_and_fold(examples, split_seed, fold_seed)
    development = tuple(item for item in assignments if not item.held_out)
    if not development:
        raise ValueError("development split is empty")
    available = min(len(item.example.candidates) for item in development)
    if available < 1:
        raise ValueError("development candidates are empty")

    development_examples = tuple(item.example for item in development)
    eligible: list[tuple[float, float, tuple[float, float, float], int]] = []
    for weights in weight_grid():
        validate_weights(weights)
        ranked_examples = _ranked_examples(development_examples, weights)
        for cutoff in range(1, min(50, available) + 1):
            recall, mrr = _metrics(ranked_examples, cutoff)
            if recall >= _RECALL_FLOOR:
                eligible.append((recall, mrr, weights, cutoff))
                break
    if not eligible:
        raise ValueError("no fusion weights reach 98% recall")
    recall, mrr, weights, cutoff = min(
        eligible,
        key=lambda value: (-value[0], -value[1], value[2]),
    )
    del recall, mrr
    training = [
        {"pair_id": item.example.pair_id, "stratum": item.stratum, "fold": item.fold}
        for item in development
    ]
    held_out = [item.example.pair_id for item in assignments if item.held_out]
    return (
        FusionProfile(
            split_seed=split_seed,
            fold_seed=fold_seed,
            weights=weights,
            candidate_cutoff=cutoff,
            training_digest=_digest(training),
            held_out_identity=_digest(held_out),
        ),
        assignments,
    )
