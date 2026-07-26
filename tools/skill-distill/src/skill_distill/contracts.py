"""Versioned immutable records shared by skill-distill curds.

Seed owns these public contract definitions; curds 1–4 wire their consumers,
while curd 5 adds model-free tests to the normal ``just check`` gate.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class RelationKind(StrEnum):
    EQUIVALENT = "equivalent"
    LEFT_SUBSUMES_RIGHT = "left-subsumes-right"
    RIGHT_SUBSUMES_LEFT = "right-subsumes-left"
    SHARED_SHELL = "shared-shell"
    CONFLICT = "conflict"
    UNRELATED = "unrelated"
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"


class RunState(StrEnum):
    PREPARED = "prepared"
    HUMAN_FROZEN = "human-frozen"
    LLM_RECORDED = "llm-recorded"
    RECONCILED = "reconciled"


RUN_STATE_ORDER = (
    RunState.PREPARED,
    RunState.HUMAN_FROZEN,
    RunState.LLM_RECORDED,
    RunState.RECONCILED,
)


def _deep_freeze(value: Any) -> Any:
    """Copy JSON-shaped contract inputs into immutable collections."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    if isinstance(value, bytearray):
        return bytes(value)
    return value


class _ImmutableContract:
    def __post_init__(self) -> None:
        for field in fields(self):
            object.__setattr__(self, field.name, _deep_freeze(getattr(self, field.name)))


@dataclass(frozen=True)
class PairEvidenceV1(_ImmutableContract):
    pair_id: str
    left: Mapping[str, Any]
    right: Mapping[str, Any]
    lane: str
    detector: str
    kind: str
    graph: Mapping[str, Any]
    cosine: float | None
    duplicate_tokens_estimate: int
    disposition: str
    selection: str
    score_decile: int | None
    graph_class: str
    skill_family: str
    schema_version: str = "pair-evidence-v1"


@dataclass(frozen=True)
class DatasetV1(_ImmutableContract):
    source_report_digest: str
    preprocessing_digest: str
    pairs: tuple[PairEvidenceV1, ...]
    schema_version: str = "dataset-v1"


@dataclass(frozen=True)
class AnnotationV1(_ImmutableContract):
    pair_id: str
    human_relation: RelationKind
    llm_relation: RelationKind | None
    atoms: tuple[Mapping[str, Any], ...]
    reconciliation: Mapping[str, Any]
    reviewer: str
    status: str
    schema_version: str = "annotation-v1"


@dataclass(frozen=True)
class DistillationRun(_ImmutableContract):
    run_id: str
    state: RunState
    human_labels_digest: str | None = None
    llm_labels_digest: str | None = None
    human_labels_frozen_at: str | None = None
    schema_version: str = "distillation-run-v1"

    def __post_init__(self) -> None:
        super().__post_init__()
        required_digests = {
            RunState.PREPARED: (False, False),
            RunState.HUMAN_FROZEN: (True, False),
            RunState.LLM_RECORDED: (True, True),
            RunState.RECONCILED: (True, True),
        }
        requires_human, requires_llm = required_digests[self.state]
        if bool(self.human_labels_digest) != requires_human:
            raise ValueError(f"{self.state} requires human_labels_digest={requires_human}")
        if bool(self.human_labels_frozen_at) != requires_human:
            raise ValueError(
                f"{self.state} requires human_labels_frozen_at={requires_human}"
            )
        if bool(self.llm_labels_digest) != requires_llm:
            raise ValueError(f"{self.state} requires llm_labels_digest={requires_llm}")


@dataclass(frozen=True)
class ModelLock(_ImmutableContract):
    model_id: str
    artifact_revision: str
    artifact_digest: str
    runtime: str
    runtime_digest: str
    schema_version: str = "model-lock-v1"


@dataclass(frozen=True)
class FusionProfile(_ImmutableContract):
    split_seed: str
    fold_seed: str
    weights: tuple[float, float, float]
    candidate_cutoff: int
    training_digest: str
    held_out_identity: str
    schema_version: str = "fusion-profile-v1"


@dataclass(frozen=True)
class ScoresV1(_ImmutableContract):
    model_profile_digest: str
    fusion_profile_digest: str
    pair_id: str
    dense: float
    sparse: float
    colbert: float
    fused: float
    schema_version: str = "scores-v1"


@dataclass(frozen=True)
class CanonicalCenter(_ImmutableContract):
    family_id: str
    clauses: tuple[Mapping[str, Any], ...]
    member_residuals: Mapping[str, tuple[Mapping[str, Any], ...]]
    schema_version: str = "canonical-center-v1"


@dataclass(frozen=True)
class DistillationFamily(_ImmutableContract):
    family_id: str
    relation: RelationKind
    members: tuple[str, ...]
    canonical_center: CanonicalCenter
    schema_version: str = "distillation-family-v1"


@dataclass(frozen=True)
class ProposalV1(_ImmutableContract):
    family_id: str
    canonical_center: CanonicalCenter
    residuals: Mapping[str, tuple[Mapping[str, Any], ...]]
    physical_reference_variant: Mapping[str, Any]
    compact_inline_variant: Mapping[str, Any]
    loaded_token_delta: int
    behavioral_evidence: Mapping[str, Any]
    reversal_patch: str
    schema_version: str = "proposal-v1"


@dataclass(frozen=True)
class TokenizerIdentity(_ImmutableContract):
    tokenizer_artifact: str
    tokenizer_revision: str
    tokenizer_hash: str
    runtime: str
    identity_digest: str
    text_encoding: str = "utf-8"
    event_mode: str = "independent"
    chat_template: str = "none"
    add_special_tokens: bool = False
    schema_version: str = "tokenizer-identity-v1"


@dataclass(frozen=True)
class LoadEvent(_ImmutableContract):
    role: str
    canonical_path: str
    content_digest: str
    tokenizer_identity_digest: str
    token_count: int
    schema_version: str = "load-event-v1"


@dataclass(frozen=True)
class TokenMetricProfile(_ImmutableContract):
    tokenizer_identity_digest: str
    load_events: tuple[LoadEvent, ...]
    schema_version: str = "token-metric-profile-v1"


@dataclass(frozen=True)
class BehaviorHarness(_ImmutableContract):
    harness_id: str
    model_identity: str
    tokenizer_identity_digest: str
    fixtures: tuple[Mapping[str, Any], ...]
    schema_version: str = "behavior-harness-v1"


@dataclass(frozen=True)
class BehaviorScorecard(_ImmutableContract):
    matrix_id: str
    subject: str
    scenario: str
    phrasing: str
    repetition: int
    obligation_id: str
    critical: bool
    expected: bool
    observed: bool
    passed: bool
    schema_version: str = "behavior-scorecard-v1"


@dataclass(frozen=True)
class RelationAdjudication(_ImmutableContract):
    pair_id: str
    adjudicator: str
    relation: RelationKind
    atom_resolution: Mapping[str, Any]
    rationale: str
    schema_version: str = "relation-adjudication-v1"

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "relation", RelationKind(self.relation))
        if not self.pair_id or not self.adjudicator or not self.rationale:
            raise ValueError("adjudications require pair_id, adjudicator, and rationale")


@dataclass(frozen=True)
class DependencyInventoryV1(_ImmutableContract):
    inventory_digest: str
    dependencies: Mapping[str, str]
    schema_version: str = "dependency-inventory-v1"

