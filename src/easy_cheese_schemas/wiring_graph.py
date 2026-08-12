"""Shared graph checks and wave scheduling for wiring rows.

The schema and fan-out validators own their domain-specific validation (for
example, whether a ``W<n>`` dependency exists).  This module only knows the
wiring graph shape: ``(id, dependencies)`` pairs whose dependencies that are
not graph nodes are ignored.
"""

from __future__ import annotations

import graphlib
from collections.abc import Iterable, Sequence
from typing import TypeAlias


WiringGraph: TypeAlias = Iterable[tuple[str, Sequence[str]]]


def _normalise(nodes: WiringGraph) -> list[tuple[str, Sequence[str]]]:
    return list(nodes)


def _sorter(
    nodes: list[tuple[str, Sequence[str]]], *, include_self: bool
) -> graphlib.TopologicalSorter[str]:
    ids = {node for node, _ in nodes}
    sorter: graphlib.TopologicalSorter[str] = graphlib.TopologicalSorter()
    for node, dependencies in nodes:
        sorter.add(
            node,
            *(
                dependency
                for dependency in dependencies
                if dependency in ids and (include_self or dependency != node)
            ),
        )
    return sorter


def _cycle_message(exc: graphlib.CycleError) -> str:
    path = " -> ".join(str(node) for node in exc.args[1])
    return f"the dependency graph has cycle {path}"


def _prepare(sorter: graphlib.TopologicalSorter[str]) -> str | None:
    try:
        sorter.prepare()
    except graphlib.CycleError as exc:
        return _cycle_message(exc)
    return None


def cycle_errors(nodes: WiringGraph) -> list[str]:
    """Return canonical errors for cycles in ``(id, dependencies)`` pairs.

    Dependencies that do not name a node in ``nodes`` are external references
    (usually curd IDs) and do not participate in cycle detection.
    """
    normalised = _normalise(nodes)
    message = _prepare(_sorter(normalised, include_self=True))
    return [] if message is None else [message]


def compute_waves(nodes: WiringGraph) -> list[list[str]]:
    """Group graph IDs into deterministic, dependency-ready waves.

    External dependencies are ignored, and self-dependencies are ignored to
    preserve the fan-out scheduler's historical progress behavior.  Other
    cycles raise ``ValueError`` with the same canonical wording as
    :func:`cycle_errors`.
    """
    normalised = _normalise(nodes)
    sorter = _sorter(normalised, include_self=False)
    message = _prepare(sorter)
    if message is not None:
        raise ValueError(message)

    waves: list[list[str]] = []
    while ready := sorted(sorter.get_ready()):
        waves.append(ready)
        sorter.done(*ready)
    return waves


__all__ = ["WiringGraph", "compute_waves", "cycle_errors"]
