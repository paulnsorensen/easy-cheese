"""Decomposition artifact: the curds and wiring a run will fan out.

A decomposition is written before any run exists, so its curds carry no
dispatch lifecycle -- demanding `id` / `status` / `retry_count` here would make
the type unable to read the artifact it models. `DecomposedCurd` is the content
half `CurdRecord` extends once a run manifest starts tracking a dispatch.

A decomposition is only safe to dispatch in parallel if no two curds can touch
the same file, so that invariant lives here with the collection that owns it
rather than in each dispatcher. Below `PARALLEL_THRESHOLD` the decomposition
runs as one linear unit and is trivially disjoint, which is why the check is
conditional. src/fanout/validate_decomposition.py delegates its curd content
and disjointness rules here; it keeps its own wiring DAG check locally, since
`WiringRow` demands a run-lifecycle `status` a decomposition document never
carries.
"""

from __future__ import annotations

from typing import Protocol

from attrs import define, field

from easy_cheese_schemas.manifest import (
    PARALLEL_THRESHOLD,
    DecomposedCurd,
    WiringRow,
    reject_shared_curd_files,
    reject_unschedulable_wiring,
)

__all__ = ["PARALLEL_THRESHOLD", "DecomposedCurd", "Decomposition"]


class _NamedAttribute(Protocol):
    name: str


def _non_empty_list(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not value:
        raise ValueError(f"{attribute.name} must be a non-empty list")


@define(frozen=True)
class Decomposition:
    """The curds and wiring rows a run was decomposed into."""

    curds: list[DecomposedCurd] = field(
        validator=[_non_empty_list, reject_shared_curd_files]
    )
    wiring: list[WiringRow] = field(
        factory=list, validator=reject_unschedulable_wiring
    )