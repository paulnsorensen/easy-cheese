"""Decomposition artifact: the curds and wiring a run will fan out.

A decomposition is only safe to dispatch in parallel if no two curds can touch
the same file, so that invariant lives here with the collection that owns it
rather than in each dispatcher. Below `PARALLEL_THRESHOLD` the decomposition
runs as one linear unit and is trivially disjoint, which is why the check is
conditional -- it mirrors src/fanout/validate_decomposition.py exactly.
"""

from __future__ import annotations

from attrs import define, field, validators

from easy_cheese_schemas.manifest import CurdRecord, WiringRow

# Exactly one number governs the linear/parallel split (src/fanout/mode.py).
PARALLEL_THRESHOLD = 2


def _reject_shared_files(curds: list[CurdRecord]) -> None:
    owner: dict[str, int] = {}
    for curd in curds:
        for path in curd.files:
            if path in owner:
                raise ValueError(
                    f"file {path!r} appears in curd {owner[path]} and curd "
                    f"{curd.id} -- curds must be file-disjoint (move shared "
                    "content to seed or wiring)"
                )
            owner[path] = curd.id


@define(frozen=True)
class Decomposition:
    """The curds and wiring rows a run was decomposed into."""

    curds: list[CurdRecord] = field(validator=validators.min_len(1))
    wiring: list[WiringRow] = field(factory=list)

    def __attrs_post_init__(self) -> None:
        if len(self.curds) >= PARALLEL_THRESHOLD:
            _reject_shared_files(self.curds)
