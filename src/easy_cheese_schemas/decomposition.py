"""Decomposition artifact: the curds and wiring a run will fan out.

A decomposition is written before any run exists, so its curds carry no
dispatch lifecycle -- demanding `id` / `status` / `retry_count` here would make
the type unable to read the artifact it models. `DecomposedCurd` is the content
half `CurdRecord` extends once a run manifest starts tracking a dispatch.

A decomposition is only safe to dispatch in parallel if no two curds can touch
the same file, so that invariant lives here with the collection that owns it
rather than in each dispatcher. Below `PARALLEL_THRESHOLD` the decomposition
runs as one linear unit and is trivially disjoint, which is why the check is
conditional -- it mirrors src/fanout/validate_decomposition.py, which also ends
with the wiring graph check.
"""

from __future__ import annotations

from attrs import define, field, validators

from easy_cheese_schemas.manifest import (
    PARALLEL_THRESHOLD,
    DecomposedCurd,
    WiringRow,
    reject_shared_curd_files,
    reject_unschedulable_wiring,
)

__all__ = ["PARALLEL_THRESHOLD", "DecomposedCurd", "Decomposition"]


@define(frozen=True)
class Decomposition:
    """The curds and wiring rows a run was decomposed into."""

    curds: list[DecomposedCurd] = field(validator=validators.min_len(1))
    wiring: list[WiringRow] = field(factory=list)

    def __attrs_post_init__(self) -> None:
        if len(self.curds) >= PARALLEL_THRESHOLD:
            reject_shared_curd_files(self.curds)
        reject_unschedulable_wiring(self.wiring)