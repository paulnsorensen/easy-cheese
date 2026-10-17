"""Typed work edges: the set a record holds.

A record holds its edges as a set keyed by `(normalize_ref(to), kind)`. The
host stamps every edge it writes with the revision that wrote it; a caller
cannot author that pin. An edge writes only the record that holds it: no
sibling record learns of it, and none owes a reciprocal.
"""

from __future__ import annotations

from collections.abc import Iterable

from attrs import define, evolve
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge, WorkEdgeKey

from .ref_grammar import normalize_ref

__all__ = [
    "EdgeError",
    "MergedEdges",
    "edge_key",
    "merge_edges",
]


class EdgeError(ValueError):
    """Raised when a delta names an edge the record cannot take or give up."""


@define(frozen=True)
class MergedEdges:
    """The edge set after a merge, and what the merge wrote and removed."""

    edges: tuple[WorkEdge, ...]
    applied: tuple[WorkEdge, ...]
    removed: tuple[WorkEdgeKey, ...]


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