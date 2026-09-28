"""The easy-cheese side of the milknado seam: data plus a presence gate (F-1).

A `checkpoints` edge to a `milknado:<project_key>/<node_key>` ref binds a
record to a Mikado goal or task. This module owns every wheypoint-aware line
that touches milknado, and it touches nothing: no milknado import, no tool
call, no network. It reads the edge, checks for `.milknado/` at the repo
root, and reports the state. The address a record gives milknado is
`wheypoint:<project_key>/<work_id>`, never a projection path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from attrs import define
from easy_cheese_schemas import WheypointRecord
from easy_cheese_schemas.contracts import EdgeKind

from . import ref_grammar

__all__ = [
    "GATE_MAPPING",
    "MILKNADO_DIRNAME",
    "BridgeState",
    "GateMapping",
    "bind",
    "is_present",
    "payload",
]

MILKNADO_DIRNAME = ".milknado"


@define(frozen=True)
class GateMapping:
    """One wheypoint gate event and the milknado state it corresponds to."""

    wheypoint: str
    milknado: str


GATE_MAPPING: tuple[GateMapping, ...] = (
    GateMapping(wheypoint="gated question", milknado="pending goal review"),
    GateMapping(wheypoint="resolve", milknado="accepted review"),
    GateMapping(wheypoint="active blocker", milknado="blocked node"),
    GateMapping(wheypoint="checkpoint", milknado="snapshot receipt"),
)


@define(frozen=True)
class BridgeState:
    """Whether a record is bound to a milknado node that this repo can reach."""

    state: Literal["bound", "bridge-inactive", "unbound"]
    node_ref: str | None
    wheypoint_ref: str


def is_present(repo_root: Path) -> bool:
    """Whether milknado keeps state in this repo."""
    return (repo_root / MILKNADO_DIRNAME).is_dir()


def bind(record: WheypointRecord, *, repo_root: Path) -> BridgeState:
    """The record's first `checkpoints` edge to a milknado node, gated on presence."""
    wheypoint_ref = f"wheypoint:{record.project_key}/{record.work_id}"
    node_ref = next(
        (
            edge.to
            for edge in record.edges
            if edge.kind is EdgeKind.CHECKPOINTS and _is_milknado(edge.to)
        ),
        None,
    )
    if node_ref is None:
        return BridgeState(state="unbound", node_ref=None, wheypoint_ref=wheypoint_ref)
    state = "bound" if is_present(repo_root) else "bridge-inactive"
    return BridgeState(state=state, node_ref=node_ref, wheypoint_ref=wheypoint_ref)


def payload(state: BridgeState) -> dict[str, object]:
    return {
        "state": state.state,
        "node_ref": state.node_ref,
        "wheypoint_ref": state.wheypoint_ref,
    }


def _is_milknado(ref: str) -> bool:
    try:
        return ref_grammar.parse_ref(ref).scheme is ref_grammar.Scheme.MILKNADO
    except ValueError:
        return False
