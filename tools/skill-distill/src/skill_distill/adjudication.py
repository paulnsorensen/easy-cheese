"""Blind human/LLM annotation lifecycle and reconciliation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Protocol, Sequence

from .contracts import (
    AnnotationV1,
    DistillationRun,
    RelationKind,
    RunState,
)
from .obligations import ObligationAtomV1, SourceSpan
from .relations import eligible_for_rewrite, parse_relation


class AnnotationLifecycleError(ValueError):
    """A lifecycle command was called in a state where it cannot run."""


class PairWithSourceSpans(Protocol):
    pair_id: str
    left: Mapping[str, Any]
    right: Mapping[str, Any]


@dataclass(frozen=True)
class HumanRelationLabel:
    pair_id: str
    relation: RelationKind
    reviewer: str
    atoms: tuple[ObligationAtomV1, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation", parse_relation(self.relation))
        if not self.pair_id or not self.reviewer:
            raise ValueError("human labels require pair_id and reviewer")


@dataclass(frozen=True)
class LlmRelationLabel:
    pair_id: str
    relation: RelationKind
    atoms: tuple[ObligationAtomV1, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation", parse_relation(self.relation))
        if not self.pair_id:
            raise ValueError("LLM labels require pair_id")


@dataclass(frozen=True)
class SourceOnlyPair:
    pair_id: str
    left_source_span: SourceSpan
    right_source_span: SourceSpan


@dataclass(frozen=True)
class ReconciliationResult:
    run: DistillationRun
    annotations: tuple[AnnotationV1, ...]


def _field(record: Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record[name]
    return getattr(record, name)


def _optional_field(record: Any, name: str, default: Any) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _json_value(value: Any) -> Any:
    if isinstance(value, SourceSpan):
        return {"path": value.path, "start": value.start, "end": value.end}
    if isinstance(value, RelationKind):
        return value.value
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value


def labels_digest(labels: Sequence[Any]) -> str:
    """Digest label content in pair order, independent of input order."""
    payload = sorted(
        (_json_value(label) for label in labels),
        key=lambda item: item["pair_id"],
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def _require_state(run: DistillationRun, expected: RunState, command: str) -> None:
    if run.state is not expected:
        raise AnnotationLifecycleError(
            f"{command} requires {expected}; run {run.run_id} is {run.state}"
        )


def freeze_human_labels(
    run: DistillationRun, labels: Sequence[Any], *, frozen_at: str
) -> DistillationRun:
    _require_state(run, RunState.PREPARED, "freeze-human-labels")
    if not labels:
        raise ValueError("human labels cannot be empty")
    if not frozen_at:
        raise ValueError("human label freeze requires a timestamp")
    return DistillationRun(
        run_id=run.run_id,
        state=RunState.HUMAN_FROZEN,
        human_labels_digest=labels_digest(labels),
        human_labels_frozen_at=frozen_at,
    )


def _source_span(value: Mapping[str, Any]) -> SourceSpan:
    span = value.get("source_span")
    if isinstance(span, SourceSpan):
        return span
    if isinstance(span, Mapping):
        return SourceSpan(
            path=str(span["path"]), start=int(span["start"]), end=int(span["end"])
        )
    raise ValueError("pair side is missing an exact source_span")


def export_llm_pairs(
    run: DistillationRun, pairs: Sequence[PairWithSourceSpans]
) -> tuple[SourceOnlyPair, ...]:
    """Export pair identity and source spans only, after human-label commitment."""
    _require_state(run, RunState.HUMAN_FROZEN, "export-llm-pairs")
    if not run.human_labels_digest or not run.human_labels_frozen_at:
        raise ValueError("LLM export requires a human label digest and timestamp")
    return tuple(
        SourceOnlyPair(pair.pair_id, _source_span(pair.left), _source_span(pair.right))
        for pair in pairs
    )


def record_llm_labels(run: DistillationRun, labels: Sequence[Any]) -> DistillationRun:
    _require_state(run, RunState.HUMAN_FROZEN, "record-llm-labels")
    if not labels:
        raise ValueError("LLM labels cannot be empty")
    return DistillationRun(
        run_id=run.run_id,
        state=RunState.LLM_RECORDED,
        human_labels_digest=run.human_labels_digest,
        llm_labels_digest=labels_digest(labels),
        human_labels_frozen_at=run.human_labels_frozen_at,
    )


def _by_pair(labels: Sequence[Any]) -> dict[str, Any]:
    by_pair = {_field(label, "pair_id"): label for label in labels}
    if len(by_pair) != len(labels):
        raise ValueError("each label sequence must contain unique pair IDs")
    return by_pair


def _required_adjudication(human: Any, llm: Any) -> bool:
    human_relation = parse_relation(_field(human, "relation"))
    llm_relation = parse_relation(_field(llm, "relation"))
    disagreement = human_relation is not llm_relation
    compression_positive = (
        eligible_for_rewrite(_field(human, "pair_id"), human_relation, complete=True).eligible
        or eligible_for_rewrite(_field(llm, "pair_id"), llm_relation, complete=True).eligible
    )
    return disagreement or compression_positive


def _atom_key(atom: Any) -> str:
    encoded = json.dumps(_json_value(atom), sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def _reconcile_atoms(
    human_atoms: Sequence[Any],
    llm_atoms: Sequence[Any],
    atom_resolution: Mapping[str, Any],
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    human_by_atom = {_atom_key(atom): atom for atom in human_atoms}
    llm_by_atom = {_atom_key(atom): atom for atom in llm_atoms}
    if len(human_by_atom) != len(human_atoms) or len(llm_by_atom) != len(llm_atoms):
        raise ValueError("each atom sequence must contain unique atoms")

    atom_ids = human_by_atom.keys() | llm_by_atom.keys()
    unknown_atom_ids = atom_resolution.keys() - atom_ids
    if unknown_atom_ids:
        raise ValueError("atom adjudication includes atoms outside the label pair")

    reconciled_atoms = []
    for atom_id in sorted(atom_ids):
        human_atom = human_by_atom.get(atom_id)
        llm_atom = llm_by_atom.get(atom_id)
        relation = (
            parse_relation(atom_resolution[atom_id])
            if atom_id in atom_resolution
            else RelationKind.EQUIVALENT
            if human_atom is not None and llm_atom is not None
            else None
        )
        reconciled_atoms.append(
            {
                "atom_id": atom_id,
                "human_atom": _json_value(human_atom) if human_atom is not None else None,
                "llm_atom": _json_value(llm_atom) if llm_atom is not None else None,
                "relation": relation,
                "complete": relation is not None,
            }
        )
    return tuple(reconciled_atoms), all(
        atom["complete"] for atom in reconciled_atoms
    )


def reconcile(
    run: DistillationRun,
    human_labels: Sequence[Any],
    llm_labels: Sequence[Any],
    adjudications: Sequence[Any],
) -> ReconciliationResult:
    """Verify commitments and atomically return immutable reconciled annotations."""
    _require_state(run, RunState.LLM_RECORDED, "reconcile")
    if labels_digest(human_labels) != run.human_labels_digest:
        raise ValueError("human label digest does not match the frozen commitment")
    if labels_digest(llm_labels) != run.llm_labels_digest:
        raise ValueError("LLM label digest does not match the recorded commitment")

    human_by_pair = _by_pair(human_labels)
    llm_by_pair = _by_pair(llm_labels)
    if human_by_pair.keys() != llm_by_pair.keys():
        raise ValueError("human and LLM labels must cover the same pairs")
    adjudication_by_pair = _by_pair(adjudications)

    annotations = []
    for pair_id in sorted(human_by_pair):
        human = human_by_pair[pair_id]
        llm = llm_by_pair[pair_id]
        adjudication = adjudication_by_pair.get(pair_id)
        if _required_adjudication(human, llm) and adjudication is None:
            raise ValueError(f"{pair_id} requires second-human adjudication")
        if (
            adjudication is not None
            and _field(adjudication, "adjudicator") == _field(human, "reviewer")
        ):
            raise ValueError(f"{pair_id} adjudicator must be a second human")

        human_relation = parse_relation(_field(human, "relation"))
        llm_relation = parse_relation(_field(llm, "relation"))
        resolved_relation = (
            parse_relation(_field(adjudication, "relation"))
            if adjudication is not None
            else human_relation
        )
        atom_resolution = (
            _field(adjudication, "atom_resolution") if adjudication is not None else {}
        )
        reconciled_atoms, complete = _reconcile_atoms(
            _optional_field(human, "atoms", ()),
            _optional_field(llm, "atoms", ()),
            atom_resolution,
        )
        eligibility = eligible_for_rewrite(pair_id, resolved_relation, complete=complete)
        annotations.append(
            AnnotationV1(
                pair_id=pair_id,
                human_relation=human_relation,
                llm_relation=llm_relation,
                atoms=reconciled_atoms,
                reconciliation={
                    "resolved_relation": resolved_relation,
                    "complete": complete,
                    "rewrite_eligible": eligibility.eligible,
                },
                reviewer=(
                    _field(adjudication, "adjudicator")
                    if adjudication is not None
                    else _field(human, "reviewer")
                ),
                status="reconciled" if complete else "incomplete",
            )
        )

    reconciled_run = DistillationRun(
        run_id=run.run_id,
        state=RunState.RECONCILED,
        human_labels_digest=run.human_labels_digest,
        llm_labels_digest=run.llm_labels_digest,
        human_labels_frozen_at=run.human_labels_frozen_at,
    )
    return ReconciliationResult(reconciled_run, tuple(annotations))