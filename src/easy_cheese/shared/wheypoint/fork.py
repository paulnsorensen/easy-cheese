"""Fork a child record from a parent in one revision: the child genesis.

`fork` writes only the child (F-2). It reads the parent without its lock and
writes nothing to it. The child's `forked_from` edge pins the parent revision
the fork read, and its rationale records the fork-time selection in the form
`fork_reconcile.fork_rationale` writes and `fork_reconcile.pending_forks`
parses. The edge and each re-proposed entry's `origin` are host-only commit
inputs.

When no entry is named, questions and blockers move, directives and decisions
copy, and every dossier fork moves with them. The parent reconciles at its
own next checkpoint (see `fork_reconcile`), so an entry that a pending fork
already moves cannot move again.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from easy_cheese_schemas import (
    ArtifactLink,
    DecisionFork,
    Durability,
    EntryKind,
    EntryState,
    NextAction,
    NextMove,
    ProposedEntry,
    ProtectedEntry,
    RepositoryProvenance,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge

from . import commit, edges, records, storage
from .fork_reconcile import FORK_RATIONALE_LIMIT, fork_rationale, pending_forks
from .ref_grammar import normalize_ref

__all__ = ["ForkError", "fork"]

_MOVED_BY_DEFAULT = (EntryKind.QUESTION, EntryKind.BLOCKER)
# `fork_rationale` joins titles and link refs with ` | ` and ends each field
# with `; `, so a selected item that holds either would mis-parse at reconcile.
_RATIONALE_SEPARATORS = (" | ", "; ")


class ForkError(ValueError):
    """The fork cannot be made. The message starts with a `code:` prefix."""


def fork(
    *,
    parent: str,
    child: str,
    corpus_root: Path,
    session_provenance: SessionProvenance,
    orientation: str,
    move: Sequence[str] = (),
    copy: Sequence[str] = (),
    dossier: Sequence[str] = (),
    links: Sequence[str] = (),
    context: Sequence[str] = (),
    notes: str | None = None,
    next: NextMove | None = None,  # noqa: A002 -- the `--next` verb flag
    artifact: str | None = None,
    repository: RepositoryProvenance | None = None,
    durability: Durability = Durability.CANONICAL_LOCAL,
    artifact_root: Path | str | None = None,
    finalize: Callable[[commit.PendingRevision], None] | None = None,
) -> commit.CommitResult:
    """Write the child genesis for a fork of `parent`, and nothing else.

    `session_provenance.captured_at` becomes the child's created time: the
    kernel reads no clock.
    """
    source = storage.WorkStore.open(parent, corpus_root=corpus_root).read_record()
    if source is None:
        raise ForkError(f"unknown-parent: work {parent!r} has no record")
    target = storage.WorkStore.open(child, corpus_root=corpus_root)
    if target.record_path.exists() or any(target.revisions_dir.glob("*.json")):
        raise ForkError(f"fork-exists: work {child!r} already has a record or history")

    if not move and not copy:
        active = [e for e in records.entries(source) if e.state is EntryState.ACTIVE]
        move = [e.entry_id for e in active if e.kind in _MOVED_BY_DEFAULT]
        copy = [e.entry_id for e in active if e.kind not in _MOVED_BY_DEFAULT]
        if not dossier:
            dossier = [item.fork for item in source.decision_dossier]
    taken = {
        parent_id: item.child_ref
        for item in pending_forks(
            source, siblings=edges.sibling_records(corpus_root, work_id=parent)
        )
        for parent_id, _ in item.moved
    }
    for entry_id in move:
        if entry_id in taken:
            raise ForkError(
                f"already-forked: entry {entry_id!r} moves to {taken[entry_id]} "
                + "at the parent's next checkpoint"
            )
    titles = list(dict.fromkeys(dossier))
    link_refs = list(dict.fromkeys(_normalized(ref) for ref in links))
    for text in [*titles, *link_refs]:
        if any(separator in text for separator in _RATIONALE_SEPARATORS):
            raise ForkError(
                f"fork-title: {text!r} holds a separator the fork rationale "
                + f"uses ({' or '.join(map(repr, _RATIONALE_SEPARATORS))})"
            )
    rationale = fork_rationale(
        parent,
        source.revision_id,
        moved=move,
        copied=copy,
        dossier=titles,
        links=link_refs,
    )
    if len(rationale) > FORK_RATIONALE_LIMIT:
        raise ForkError(
            f"fork-too-large: the fork selection needs {len(rationale)} "
            + f"characters; the edge rationale holds {FORK_RATIONALE_LIMIT}"
        )
    selected = _selected(source, [*move, *copy])
    if not selected:
        raise ForkError(f"fork-empty: work {parent!r} has no entry to move or copy")
    gates = [e.entry_id for e in selected if e.entry_id in source.gating_entry_ids]
    if gates and not titles:
        raise ForkError(
            f"dossier-required: entries {', '.join(gates)} gate continuation, so "
            + "the fork must take the dossier fork that describes them"
        )
    proposed = {
        kind: [entry for entry in selected if entry.kind is kind]
        for kind in commit.ADDITION_FIELDS
    }
    ordered = [entry for kind in commit.ADDITION_FIELDS for entry in proposed[kind]]
    origin = f"wheypoint:{source.project_key}/{parent}@{source.revision_id}"
    delta = WheypointDelta(
        work_id=child,
        expected_revision_id=commit.GENESIS_PARENT,
        orientation=orientation,
        working_context=list(context),
        notes=notes,
        next_action=NextAction(
            move=NextMove.HOLD if next is None else next,
            orientation=orientation,
            artifact=artifact,
        ),
        decision_dossier=_dossier(source, titles),
        add_decisions=_proposals(proposed[EntryKind.DECISION]),
        add_questions=_proposals(proposed[EntryKind.QUESTION]),
        add_blockers=_proposals(proposed[EntryKind.BLOCKER]),
        add_directives=_proposals(proposed[EntryKind.DIRECTIVE]),
        add_artifact_links=_links(source, links),
        session_provenance=session_provenance,
    )
    return commit.commit(
        delta,
        store=target,
        repository=repository,
        durability=durability,
        artifact_root=artifact_root,
        origins={
            index: f"{origin}#{entry.entry_id}" for index, entry in enumerate(ordered)
        },
        fork_edge=WorkEdge(to=origin, kind=EdgeKind.FORKED_FROM, rationale=rationale),
        finalize=finalize,
    )


def _selected(source: WheypointRecord, entry_ids: Sequence[str]) -> list[ProtectedEntry]:
    """The named entries in record order, each active and named once."""
    seen: set[str] = set()
    for entry_id in entry_ids:
        if entry_id in seen:
            raise ForkError(f"fork-overlap: entry {entry_id!r} is named twice")
        seen.add(entry_id)
        entry = records.find_entry(source, entry_id)
        if entry is None:
            raise ForkError(
                f"unknown-entry: work {source.work_id!r} holds no entry {entry_id!r}"
            )
        if entry.state is EntryState.FORKED:
            raise ForkError(
                f"already-forked: entry {entry_id!r} moved to {entry.successor}"
            )
        if entry.state is not EntryState.ACTIVE:
            raise ForkError(
                f"inactive-entry: entry {entry_id!r} is {entry.state.value}"
            )
    return [entry for entry in records.entries(source) if entry.entry_id in seen]


def _proposals(entries: Sequence[ProtectedEntry]) -> list[ProposedEntry] | None:
    if not entries:
        return None
    return [
        ProposedEntry(
            kind=entry.kind,
            summary=entry.summary,
            blocks_continuation=entry.blocks_continuation,
            rationale=entry.rationale,
            quote=entry.quote,
        )
        for entry in entries
    ]


def _dossier(source: WheypointRecord, titles: Sequence[str]) -> list[DecisionFork]:
    by_title = {item.fork: item for item in source.decision_dossier}
    unknown = [title for title in titles if title not in by_title]
    if unknown:
        raise ForkError(
            f"unknown-dossier: work {source.work_id!r} has no dossier fork "
            + ", ".join(repr(title) for title in unknown)
        )
    return [by_title[title] for title in dict.fromkeys(titles)]


def _links(source: WheypointRecord, refs: Sequence[str]) -> list[ArtifactLink] | None:
    """Copies of the named parent links; the child pins its own digests."""
    if not refs:
        return None
    by_ref = {
        _normalized(records.effective_ref(link)): link for link in source.artifact_links
    }
    unknown = [ref for ref in refs if _normalized(ref) not in by_ref]
    if unknown:
        raise ForkError(
            f"unknown-link: work {source.work_id!r} carries no link "
            + ", ".join(repr(ref) for ref in unknown)
        )
    return [
        ArtifactLink(path=by_ref[ref].path, ref=ref)
        for ref in dict.fromkeys(_normalized(ref) for ref in refs)
    ]


def _normalized(ref: str) -> str:
    try:
        return normalize_ref(ref)
    except ValueError:
        return ref
