"""The parent side of a fork: what a child asks its parent to reconcile.

`fork` writes only the child (F-2). The child's `forked_from` edge names the
parent at the revision it forked from, and its rationale records the fork-time
selection: which parent entries moved, which were copied, and which dossier
forks and links the child took. The parent learns of the fork on read, as a
pending fork, and its own next checkpoint applies it host-side: moved
entries transition to `forked`, copied entries gain `copies`, the selected
dossier forks and links leave, and a `forked_to` edge closes the pending fork.
A `forked_from` edge whose rationale does not parse is not a fork.

`commit` imports this module, so it must not import `commit` or `fork`.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Sequence

from attrs import define
from easy_cheese_schemas import (
    EntryState,
    EntryTransition,
    TransitionAction,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge

from . import records
from .ref_grammar import Scheme, normalize_ref, parse_ref

__all__ = [
    "FORK_RATIONALE_LIMIT",
    "AppliedFork",
    "PendingFork",
    "apply_pending_forks",
    "fork_payload",
    "fork_rationale",
    "pending_forks",
]

FORK_RATIONALE_LIMIT = 2000
_NONE = "none"
# Dossier titles may hold commas, so titles and link refs use this separator.
_LIST_SEPARATOR = " | "
_RATIONALE_RE = re.compile(
    r"fork of (?P<parent>[^@\s]+)@(?P<revision>[^;\s]+); "
    + r"moved: (?P<moved>[^;]*); copied: (?P<copied>[^;]*); "
    + r"dossier: (?P<dossier>.*); links: (?P<links>.*)",
    re.DOTALL,
)


@define(frozen=True, kw_only=True)
class PendingFork:
    """A child's fork its parent has not yet reconciled.

    Each pair in `moved` and `copied` is `(parent_entry_id, child_entry_id)`.
    `dossier_titles` and `link_refs` are the fork-time selection.
    """

    child_ref: str
    child_work_id: str
    child_revision_id: str
    moved: tuple[tuple[str, str], ...]
    copied: tuple[tuple[str, str], ...]
    dossier_titles: tuple[str, ...]
    link_refs: tuple[str, ...]

    def successor(self, child_entry_id: str) -> str:
        """The ref of one child entry, for `successor` and `copies`."""
        return f"{self.child_ref}#{child_entry_id}"


@define(frozen=True, kw_only=True)
class AppliedFork:
    """What the parent's next commit changes to reconcile its pending forks.

    `copies` maps a parent entry id to the child refs it gains. `edges` are
    unstamped `forked_to` edges; the commit stamps them when it merges them.
    """

    transitions: tuple[EntryTransition, ...]
    copies: dict[str, tuple[str, ...]]
    dossier_removed: tuple[str, ...]
    link_refs_removed: tuple[str, ...]
    edges: tuple[WorkEdge, ...]


@define(frozen=True)
class _Selection:
    moved: tuple[str, ...]
    copied: tuple[str, ...]
    dossier: tuple[str, ...]
    links: tuple[str, ...]


def fork_rationale(
    parent: str,
    revision_id: str,
    *,
    moved: Sequence[str],
    copied: Sequence[str],
    dossier: Sequence[str],
    links: Sequence[str],
) -> str:
    """The machine-readable rationale a child's `forked_from` edge carries."""
    return (
        f"fork of {parent}@{revision_id}; moved: {', '.join(moved) or _NONE}; "
        + f"copied: {', '.join(copied) or _NONE}; "
        + f"dossier: {_LIST_SEPARATOR.join(dossier) or _NONE}; "
        + f"links: {_LIST_SEPARATOR.join(links) or _NONE}"
    )


def _split(text: str, separator: str) -> tuple[str, ...]:
    items = tuple(part.strip() for part in text.split(separator) if part.strip())
    return () if items == (_NONE,) else items


def _parsed_rationale(text: str | None) -> _Selection | None:
    match = None if text is None else _RATIONALE_RE.fullmatch(text)
    if match is None:
        return None
    return _Selection(
        moved=_split(match["moved"], ","),
        copied=_split(match["copied"], ","),
        dossier=_split(match["dossier"], _LIST_SEPARATOR),
        links=_split(match["links"], _LIST_SEPARATOR),
    )


def _wheypoint_target(ref: str | None) -> tuple[str, str, str | None] | None:
    """`(project_key, work_id, entry_id)` of a `wheypoint:` ref, or None."""
    if ref is None:
        return None
    try:
        parsed = parse_ref(ref)
    except ValueError:
        return None
    if parsed.scheme is not Scheme.WHEYPOINT or parsed.project_key is None:
        return None
    return parsed.project_key, parsed.work_id or "", parsed.entry_id


def _link_ref(ref: str) -> str:
    try:
        return normalize_ref(ref)
    except ValueError:
        return ref


def pending_forks(
    record: WheypointRecord, *, siblings: Iterable[WheypointRecord]
) -> tuple[PendingFork, ...]:
    """Every child whose `forked_from` names `record` without a `forked_to` back.

    `siblings` are the other records of the corpus, read without their locks
    (see `edges.sibling_records`): a stale read only defers the fork to a
    later checkpoint.
    """
    this = (record.project_key, record.work_id)
    reconciled = {
        target[:2]
        for edge in record.edges
        if edge.kind is EdgeKind.FORKED_TO
        and (target := _wheypoint_target(edge.to)) is not None
    }
    pending: list[PendingFork] = []
    for child in siblings:
        key = (child.project_key, child.work_id)
        if key == this or key in reconciled:
            continue
        found = next(
            (
                (edge, selection)
                for edge in child.edges
                if edge.kind is EdgeKind.FORKED_FROM
                and (target := _wheypoint_target(edge.to)) is not None
                and target[:2] == this
                and (selection := _parsed_rationale(edge.rationale)) is not None
            ),
            None,
        )
        if found is None:
            continue
        pending.append(_pending_fork(record, child, *found))
    return tuple(sorted(pending, key=lambda item: item.child_work_id))


def _pending_fork(
    parent: WheypointRecord,
    child: WheypointRecord,
    edge: WorkEdge,
    selection: _Selection,
) -> PendingFork:
    child_of: dict[str, str] = {}
    for entry in records.entries(child):
        origin = _wheypoint_target(entry.origin)
        if origin is not None and origin[:2] == (parent.project_key, parent.work_id):
            if origin[2] is not None:
                child_of[origin[2]] = entry.entry_id
    return PendingFork(
        child_ref=f"wheypoint:{child.project_key}/{child.work_id}",
        child_work_id=child.work_id,
        child_revision_id=edge.revision_id or child.revision_id,
        moved=tuple(
            (item, child_of[item]) for item in selection.moved if item in child_of
        ),
        copied=tuple(
            (item, child_of[item]) for item in selection.copied if item in child_of
        ),
        dossier_titles=selection.dossier,
        link_refs=tuple(_link_ref(ref) for ref in selection.links),
    )


def apply_pending_forks(
    current: WheypointRecord,
    pending: Iterable[PendingFork],
    *,
    agent_transitioned: Collection[str] = (),
) -> AppliedFork:
    """The host-side changes that reconcile `pending` on `current`.

    A moved entry transitions only while it is still active and the agent's
    own delta does not transition it: an entry already `forked`, or settled
    since the fork, keeps its state. When two pending forks move one entry,
    the first in `pending` order moves it and each later one gains a copy.
    """
    by_id = {entry.entry_id: entry for entry in records.entries(current)}
    transitions: list[EntryTransition] = []
    moved_ids: set[str] = set()
    copies: dict[str, tuple[str, ...]] = {}
    dossier: list[str] = []
    links: list[str] = []
    forked_to: list[WorkEdge] = []

    def copy(parent_id: str, ref: str) -> None:
        entry = by_id.get(parent_id)
        if entry is None or ref in entry.copies + copies.get(parent_id, ()):
            return
        copies[parent_id] = (*copies.get(parent_id, ()), ref)

    for item in pending:
        for parent_id, child_id in item.moved:
            entry = by_id.get(parent_id)
            if parent_id in moved_ids:
                copy(parent_id, item.successor(child_id))
                continue
            if (
                entry is None
                or entry.state is not EntryState.ACTIVE
                or parent_id in agent_transitioned
            ):
                continue
            moved_ids.add(parent_id)
            transitions.append(
                EntryTransition(
                    entry_id=parent_id,
                    action=TransitionAction.FORK,
                    rationale=f"forked to {item.child_ref}",
                    successor=item.successor(child_id),
                )
            )
        for parent_id, child_id in item.copied:
            copy(parent_id, item.successor(child_id))
        dossier.extend(item.dossier_titles)
        links.extend(item.link_refs)
        forked_to.append(
            WorkEdge(
                to=f"{item.child_ref}@{item.child_revision_id}",
                kind=EdgeKind.FORKED_TO,
                rationale=(
                    f"moved: {', '.join(p for p, _ in item.moved) or _NONE}; "
                    + f"copied: {', '.join(p for p, _ in item.copied) or _NONE}"
                ),
            )
        )
    return AppliedFork(
        transitions=tuple(transitions),
        copies=copies,
        dossier_removed=tuple(dossier),
        link_refs_removed=tuple(links),
        edges=tuple(forked_to),
    )


def fork_payload(pending: Iterable[PendingFork]) -> list[dict[str, object]]:
    """The JSON shape a reply carries for each pending fork.

    `kind` is always `"fork"`, which no `EdgeKind` value spells, so a reader
    tells these entries apart from the pending reciprocal edges beside them.
    """
    return [
        {
            "kind": "fork",
            "child": item.child_ref,
            "revision_id": item.child_revision_id,
            "moved": [
                {"entry_id": parent_id, "child_entry_id": child_id}
                for parent_id, child_id in item.moved
            ],
            "copied": [
                {"entry_id": parent_id, "child_entry_id": child_id}
                for parent_id, child_id in item.copied
            ],
            "dossier": list(item.dossier_titles),
            "links": list(item.link_refs),
        }
        for item in pending
    ]
