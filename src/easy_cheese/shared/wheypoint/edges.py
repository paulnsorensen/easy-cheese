"""Typed work edges: the set a record holds, and the reciprocals it owes.

A record holds its edges as a set keyed by `(normalize_ref(to), kind)`. The
host stamps every edge it writes with the revision that wrote it; a caller
cannot author that pin.

A link writes only the record that makes it (F-2). A `wheypoint:` target
learns of the link on read, as a pending reciprocal edge, and the target's
own next checkpoint adds that reciprocal host-side. `pending_reciprocals`
reads sibling records without their locks: one flock per record is the whole
concurrency contract, and a stale read only defers the reciprocal to a later
checkpoint.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from attrs import define, evolve
from easy_cheese_schemas import WheypointRecord
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge, WorkEdgeKey

from . import storage
from .ref_grammar import Scheme, normalize_ref, parse_ref

__all__ = [
    "RECIPROCAL",
    "EdgeError",
    "MergedEdges",
    "PendingEdge",
    "apply_pending_reciprocals",
    "edge_key",
    "merge_edges",
    "pending_payload",
    "pending_reciprocals",
]

RECIPROCAL: Mapping[EdgeKind, EdgeKind] = {
    EdgeKind.FORKED_FROM: EdgeKind.FORKED_TO,
    EdgeKind.FORKED_TO: EdgeKind.FORKED_FROM,
    EdgeKind.SUPERSEDES: EdgeKind.SUPERSEDED_BY,
    EdgeKind.SUPERSEDED_BY: EdgeKind.SUPERSEDES,
    EdgeKind.RELATES_TO: EdgeKind.RELATES_TO,
}
# A fork is reconciled whole by `fork_reconcile.pending_forks` -- entries,
# dossier, links, and the `forked_to` edge together -- never as a bare
# reciprocal edge. `RECIPROCAL` still maps the fork kinds for readers that
# only need the edge's other half.
_FORK_KINDS = frozenset({EdgeKind.FORKED_FROM, EdgeKind.FORKED_TO})


class EdgeError(ValueError):
    """Raised when a delta names an edge the record cannot take or give up."""


@define(frozen=True)
class MergedEdges:
    """The edge set after a merge, and what the merge wrote and removed."""

    edges: tuple[WorkEdge, ...]
    applied: tuple[WorkEdge, ...]
    removed: tuple[WorkEdgeKey, ...]


@define(frozen=True, kw_only=True)
class PendingEdge:
    """A reciprocal edge a record owes to a sibling that links to it.

    `kind` and `to` are the edge this record must add; the sibling's own edge
    has kind `RECIPROCAL[kind]`.
    """

    source_ref: str
    source_work_id: str
    source_revision_id: str
    kind: EdgeKind
    to: str


def edge_key(edge: WorkEdge | WorkEdgeKey) -> tuple[str, EdgeKind]:
    """The `(to, kind)` identity of an edge, with `to` in canonical spelling."""
    try:
        return normalize_ref(edge.to), edge.kind
    except ValueError:
        return edge.to, edge.kind


def merge_edges(
    current: Iterable[WorkEdge],
    add: Iterable[WorkEdge] | None,
    remove: Iterable[WorkEdgeKey] | None,
    *,
    revision_id: str,
) -> MergedEdges:
    """Add and remove edges by key; every added edge carries `revision_id`.

    An added key the record already holds refreshes its rationale and pin and
    still counts as applied. Removing a key the record does not hold raises.
    """
    by_key = {edge_key(edge): edge for edge in current}
    applied: dict[tuple[str, EdgeKind], WorkEdge] = {}
    for edge in add or ():
        try:
            to = normalize_ref(edge.to)
        except ValueError as exc:
            raise EdgeError(f"invalid-edge: {exc}") from exc
        stamped = evolve(edge, to=to, revision_id=revision_id)
        key = edge_key(stamped)
        by_key[key] = stamped
        applied[key] = stamped
    removed: dict[tuple[str, EdgeKind], WorkEdgeKey] = {}
    for value in remove or ():
        key = edge_key(value)
        if key not in by_key:
            raise EdgeError(
                f"unknown-edge: this record holds no {key[1].value} edge to {value.to!r}"
            )
        del by_key[key]
        _ = applied.pop(key, None)
        removed[key] = WorkEdgeKey(to=key[0], kind=key[1])
    return MergedEdges(
        edges=tuple(by_key.values()),
        applied=tuple(applied.values()),
        removed=tuple(removed.values()),
    )


def pending_reciprocals(
    record: WheypointRecord, *, corpus_root: Path
) -> tuple[PendingEdge, ...]:
    """Every reciprocal edge a sibling record's link asks `record` to add.

    Fork edges are excluded: `fork_reconcile.pending_forks` owns them.
    """
    held = {(target, kind) for target, kind in map(_target, record.edges) if target}
    pending: list[PendingEdge] = []
    for store in storage.WorkStore.enumerate(corpus_root):
        if store.work_id == record.work_id:
            continue
        try:
            source = store.read_record()
        except (ValueError, OSError):
            continue
        if source is None:
            continue
        for edge in source.edges:
            reciprocal = RECIPROCAL.get(edge.kind)
            if (
                reciprocal is None
                or edge.kind in _FORK_KINDS
                or _target(edge)[0] != (record.project_key, record.work_id)
            ):
                continue
            if ((source.project_key, source.work_id), reciprocal) in held:
                continue
            pending.append(
                PendingEdge(
                    source_ref=f"wheypoint:{source.project_key}/{source.work_id}",
                    source_work_id=source.work_id,
                    source_revision_id=edge.revision_id or source.revision_id,
                    kind=reciprocal,
                    to=f"wheypoint:{source.project_key}/{source.work_id}",
                )
            )
    return tuple(
        sorted(pending, key=lambda item: (item.source_work_id, item.kind.value))
    )


def apply_pending_reciprocals(
    edges: Iterable[WorkEdge],
    pending: Iterable[PendingEdge],
    *,
    revision_id: str,
) -> MergedEdges:
    """Add each pending reciprocal the edge set does not already hold."""
    by_key = {edge_key(edge): edge for edge in edges}
    applied: list[WorkEdge] = []
    for item in pending:
        edge = WorkEdge(
            to=item.to,
            kind=item.kind,
            revision_id=revision_id,
            rationale=(
                f"reciprocal of {RECIPROCAL[item.kind].value} from "
                + f"{item.source_ref}@{item.source_revision_id}"
            ),
        )
        key = edge_key(edge)
        if key in by_key:
            continue
        by_key[key] = edge
        applied.append(edge)
    return MergedEdges(edges=tuple(by_key.values()), applied=tuple(applied), removed=())


def pending_payload(pending: Iterable[PendingEdge]) -> list[dict[str, object]]:
    """The JSON shape a reply carries for each pending reciprocal edge."""
    return [
        {
            "source": item.source_ref,
            "kind": item.kind.value,
            "to": item.to,
            "revision_id": item.source_revision_id,
        }
        for item in pending
    ]


def _target(edge: WorkEdge) -> tuple[tuple[str, str] | None, EdgeKind]:
    """The `(project_key, work_id)` a `wheypoint:` edge names, pins ignored."""
    try:
        parsed = parse_ref(edge.to)
    except ValueError:
        return None, edge.kind
    if parsed.scheme is not Scheme.WHEYPOINT or parsed.project_key is None:
        return None, edge.kind
    return (parsed.project_key, parsed.work_id or ""), edge.kind
