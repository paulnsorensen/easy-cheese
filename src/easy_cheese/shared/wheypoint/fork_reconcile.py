"""The parent side of a fork: what a child asks its parent to reconcile.

`fork` writes only the child (F-2). The child's `forked_from` edge names the
parent at the revision it forked from, and its rationale records which parent
entries moved and which were copied. The parent learns of the fork on read,
as a pending fork, and its own next checkpoint applies it host-side: moved
entries transition to `forked`, copied entries gain `copies`, the moved
dossier forks and links leave, and a `forked_to` edge closes the pending fork.

`commit` imports this module, so it must not import `commit` or `fork`.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path

from attrs import define
from easy_cheese_schemas import (
    EntryState,
    EntryTransition,
    TransitionAction,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge

from . import records, storage
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
_RATIONALE_RE = re.compile(
    r"fork of (?P<parent>[^@\s]+)@(?P<revision>[^;\s]+); "
    + r"moved: (?P<moved>[^;]*); copied: (?P<copied>[^;]*)"
)


@define(frozen=True, kw_only=True)
class PendingFork:
    """A child's fork its parent has not yet reconciled.

    Each pair in `moved` and `copied` is `(parent_entry_id, child_entry_id)`.
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


def fork_rationale(
    parent: str, revision_id: str, moved: Sequence[str], copied: Sequence[str]
) -> str:
    """The machine-readable rationale a child's `forked_from` edge carries."""
    return (
        f"fork of {parent}@{revision_id}; moved: {', '.join(moved) or _NONE}; "
        + f"copied: {', '.join(copied) or _NONE}"
    )


def _split_ids(text: str) -> tuple[str, ...]:
    ids = tuple(part.strip() for part in text.split(",") if part.strip())
    return () if ids == (_NONE,) else ids


def _parsed_rationale(text: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    match = None if text is None else _RATIONALE_RE.fullmatch(text)
    if match is None:
        return (), ()
    return _split_ids(match["moved"]), _split_ids(match["copied"])


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
    record: WheypointRecord, *, corpus_root: Path
) -> tuple[PendingFork, ...]:
    """Every child whose `forked_from` names `record` without a `forked_to` back.

    Sibling records are read without their locks, as `pending_reciprocals`
    reads them: a stale read only defers the fork to a later checkpoint.
    """
    this = (record.project_key, record.work_id)
    reconciled = {
        target[:2]
        for edge in record.edges
        if edge.kind is EdgeKind.FORKED_TO
        and (target := _wheypoint_target(edge.to)) is not None
    }
    pending: list[PendingFork] = []
    for store in storage.WorkStore.enumerate(corpus_root):
        if store.work_id == record.work_id:
            continue
        try:
            child = store.read_record()
        except (ValueError, OSError):
            continue
        if child is None or (child.project_key, child.work_id) in reconciled:
            continue
        edge = next(
            (
                edge
                for edge in child.edges
                if edge.kind is EdgeKind.FORKED_FROM
                and (target := _wheypoint_target(edge.to)) is not None
                and target[:2] == this
            ),
            None,
        )
        if edge is None:
            continue
        pending.append(_pending_fork(record, child, edge))
    return tuple(sorted(pending, key=lambda item: item.child_work_id))


def _pending_fork(
    parent: WheypointRecord, child: WheypointRecord, edge: WorkEdge
) -> PendingFork:
    moved, copied = _parsed_rationale(edge.rationale)
    child_of: dict[str, str] = {}
    for entry in records.entries(child):
        origin = _wheypoint_target(entry.origin)
        if origin is not None and origin[:2] == (parent.project_key, parent.work_id):
            if origin[2] is not None:
                child_of[origin[2]] = entry.entry_id
    parent_titles = {fork.fork for fork in parent.decision_dossier}
    parent_links = {
        _link_ref(records.effective_ref(link)) for link in parent.artifact_links
    }
    child_links = (
        _link_ref(records.effective_ref(link)) for link in child.artifact_links
    )
    return PendingFork(
        child_ref=f"wheypoint:{child.project_key}/{child.work_id}",
        child_work_id=child.work_id,
        child_revision_id=edge.revision_id or child.revision_id,
        moved=tuple((item, child_of[item]) for item in moved if item in child_of),
        copied=tuple((item, child_of[item]) for item in copied if item in child_of),
        dossier_titles=tuple(
            fork.fork for fork in child.decision_dossier if fork.fork in parent_titles
        ),
        link_refs=tuple(ref for ref in child_links if ref in parent_links),
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
    since the fork, keeps its state.
    """
    by_id = {entry.entry_id: entry for entry in records.entries(current)}
    transitions: list[EntryTransition] = []
    copies: dict[str, tuple[str, ...]] = {}
    dossier: list[str] = []
    links: list[str] = []
    forked_to: list[WorkEdge] = []
    for item in pending:
        for parent_id, child_id in item.moved:
            entry = by_id.get(parent_id)
            if (
                entry is None
                or entry.state is not EntryState.ACTIVE
                or parent_id in agent_transitioned
            ):
                continue
            transitions.append(
                EntryTransition(
                    entry_id=parent_id,
                    action=TransitionAction.FORK,
                    rationale=f"forked to {item.child_ref}",
                    successor=item.successor(child_id),
                )
            )
        for parent_id, child_id in item.copied:
            entry = by_id.get(parent_id)
            ref = item.successor(child_id)
            if entry is None or ref in entry.copies + copies.get(parent_id, ()):
                continue
            copies[parent_id] = (*copies.get(parent_id, ()), ref)
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
