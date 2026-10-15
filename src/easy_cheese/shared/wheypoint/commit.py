"""The commit transaction: one delta becomes one revision, or nothing at all.

Everything from reading the current record to replacing it happens inside the
store's exclusive per-record lock, because every check this module makes is a
claim about the record *as it is right now*: a parent comparison made outside
the lock is a guess by the time it is acted on.

The order of the checks is the contract:

1. **Replay before conflict.** A request is identified by its fingerprint
   against its declared parent, so an identical resubmission finds the receipt
   it already produced and returns it -- even when the record has since moved
   on. Only a *different* request against a parent that is no longer current is
   a conflict, and a conflict promotes nothing. The one receipt that is *not* a
   replay is one the record has not caught up to: a complete pair whose parent
   is still the current revision is an interrupted promotion, and the retry
   finishes it instead of reporting a save no reader can serve.
2. **Receipt before application.** The parent the record names has to have a
   structurable receipt whose digest the record still quotes. The check reads
   receipts only: whether an ancestor's projection is present is recovery's
   question, not this one's.
3. **No compaction proofs.** A delta that declares compaction is refused.
   Compaction safety is the parent rule above: a writer that lost its context
   re-reads the record and names the revision it read.

Identity is derived, never drawn. Revision ids hash the parent and the request;
entry ids hash the parent and the proposed entry. Nothing here reads a clock or
a random source, so the same request against the same parent produces the same
names -- which is what makes replay recognisable at all.

Omission carries forward. A delta field left `None` means "unchanged", and the
additive fields only ever add, so no protected entry or artifact link
can leave the record without an `EntryTransition` naming it.

A delta whose `expected_revision_id` is `GENESIS_PARENT` is the one request with
nothing to carry forward from: it *creates* the first record for a work id. It
must therefore supply the semantic context itself, and it is refused outright
once the store holds anything -- a live record, or complete revisions whose
record has gone missing -- because creation over existing history is exactly the
erasure the carry-forward rules above exist to prevent. Rule 1 still comes
first: an identical genesis resubmission is a replay, not a conflict.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from attrs import define, evolve
from easy_cheese_schemas import (
    SCHEMA_VERSION,
    ArtifactLink,
    Durability,
    EntryKind,
    EntryState,
    EntryTransition,
    NextAction,
    ProposedEntry,
    ProtectedEntry,
    RepositoryProvenance,
    TransitionAction,
    WheypointDelta,
    WheypointProjection,
    WheypointRecord,
    WheypointRevision,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge, WorkEdgeKey

from easy_cheese.shared import paths

from . import canonical
from . import edges as edges_mod
from . import projection as projection_mod
from . import records, refs, storage

# A record digest deliberately excludes `revision_digest` (see records.py), so
# the draft record can be hashed, quoted by its receipt, and only then told
# which receipt quoted it. This placeholder holds that field open in between.
_UNPINNED_DIGEST = f"{canonical.DIGEST_PREFIX}{'0' * 64}"
_ID_HEX = 12
_FORK_EDGE_KINDS = frozenset({EdgeKind.FORKED_FROM})
# The parent a delta names when it is asking for the *first* record. Every
# derived revision id is `rev-<12 hex>` (see `_revision_id`), so this sentinel
# lives outside that namespace by construction: no hash can produce it, and no
# real parent can be mistaken for it.
GENESIS_PARENT = "genesis"
_KIND_PREFIX = {
    EntryKind.DECISION: "d",
    EntryKind.QUESTION: "q",
    EntryKind.DIRECTIVE: "v",
}
ADDITION_FIELDS = {
    EntryKind.DECISION: "add_decisions",
    EntryKind.QUESTION: "add_questions",
    EntryKind.DIRECTIVE: "add_directives",
}
_RECORD_FIELDS = {
    EntryKind.DECISION: "decisions",
    EntryKind.QUESTION: "questions",
    EntryKind.DIRECTIVE: "directives",
}


class CommitError(RuntimeError):
    """Raised when a delta cannot be applied. Nothing has been promoted."""


class StaleParentError(CommitError):
    """A different request arrived against a parent that is no longer current.

    Distinct from the rest because it is the one failure a caller can act on:
    re-read the record, rebuild the delta against the revision that won, and
    submit again.
    """


class GenesisConflictError(CommitError):
    """A genesis delta arrived for work that already has a record.

    Also actionable, and the more dangerous of the two: creating from scratch
    over a live record would drop every protected entry it carries, which is
    precisely what this kernel exists to make impossible. The caller re-reads
    the record and submits against its current revision instead.
    """


@define(frozen=True)
class CommitResult:
    """What the store holds after the call.

    `record` is the store's current record, which on a replay may be a
    descendant of the returned revision: the receipt is the one this request
    produced, the record is what the work has since become.
    """

    revision: WheypointRevision
    record: WheypointRecord
    projection: WheypointProjection
    markdown: str
    replayed: bool


@define(frozen=True)
class PendingRevision:
    """A typed revision awaiting the one durability finalizer."""

    revision: WheypointRevision
    record: WheypointRecord
    projection: WheypointProjection
    markdown: str
    replayed: bool = False


def commit(
    delta: WheypointDelta,
    *,
    store: storage.WorkStore,
    repository: RepositoryProvenance | None = None,
    durability: Durability = Durability.CANONICAL_LOCAL,
    finalize: Callable[[PendingRevision], None] | None = None,
    artifact_root: Path | str | None = None,
    fork_edge: WorkEdge | None = None,
    imported_stamps: tuple[int | None, int | None] | None = None,
) -> CommitResult:
    """Apply `delta` to the store's current record under the record lock.

    `imported_stamps` is host-only input for an import genesis: the source
    record's `(notes_revision_number, decisions_revision_number)`, kept so the
    drift marker the source projection showed still renders.

    `fork_edge` is host-only input too: the `forked_from` edge `fork()` writes
    into a child. A delta cannot author a fork edge itself.
    """
    forged_edges = [
        edge.to
        for edge in [*(delta.add_edges or ()), *(delta.remove_edges or ())]
        if edge.kind in _FORK_EDGE_KINDS
    ]
    if forged_edges:
        raise CommitError(
            "host-only-edge: the fork edge is written by the host when it forks, "
            + f"not on request ({', '.join(forged_edges)})"
        )
    repository_value: RepositoryProvenance = (
        RepositoryProvenance() if repository is None else repository
    )
    digest_root = (
        _digest_root() if artifact_root is None else Path(artifact_root).resolve()
    )
    digest_of = refs.digester(digest_root, paths.corpus_home())

    if delta.work_id != store.work_id:
        raise CommitError(
            f"delta names work {delta.work_id!r} but the store holds "
            + f"{store.work_id!r}"
        )
    if delta.compacted or delta.compaction is not None:
        raise CommitError(
            "compaction-unsupported: a delta no longer declares compaction; "
            + "re-read the record and name the revision you read as the parent"
        )
    fingerprint = records.request_fingerprint(delta)
    with store.lock():
        try:
            current = store.read_record()
        except ValueError as exc:
            raise CommitError(
                f"{storage.RECORD_FILENAME} for work {store.work_id!r} cannot be "
                + f"read, so no delta can be applied to it: {exc}"
            ) from exc
        if delta.expected_revision_id == GENESIS_PARENT:
            replay = _find_replay(store, delta, fingerprint)
            if current is not None:
                if replay is not None:
                    return _finalize(
                        store,
                        _replayed(store, replay, current),
                        finalize=finalize,
                    )
                raise GenesisConflictError(
                    f"work {store.work_id!r} already holds revision "
                    + f"{current.revision_id!r}: a genesis delta creates the first "
                    + "record and never replaces a live one"
                )
            if replay is None:
                # No record, but the history it pointed at can still be on
                # disk. Keying the guard on the record alone would let one lost
                # file turn genesis into a second lineage, leaving every
                # revision behind it unreachable -- the same erasure, reached
                # the long way round.
                _refuse_over_existing_history(store)
            # `replay is not None` here means this genesis already wrote its
            # pair and died before the record swap. `_genesis` re-derives the
            # identical triple and `promote` settles the pointer onto it.
            return _finalize(
                store,
                _genesis(
                    store,
                    delta,
                    fingerprint=fingerprint,
                    repository=repository_value,
                    project_key=paths.project_key(digest_root),
                    durability=durability,
                    digest_of=digest_of,
                    checkout=digest_root,
                    fork_edge=fork_edge,
                    imported_stamps=imported_stamps,
                ),
                finalize=finalize,
            )
        if current is None:
            raise CommitError(
                f"work {store.work_id!r} has no record to apply a delta to; "
                + f"a first delta must name {GENESIS_PARENT!r} as its parent"
            )
        replay = _find_replay(store, delta, fingerprint)
        if replay is not None and replay.parent_revision_id != current.revision_id:
            return _finalize(
                store,
                _replayed(store, replay, current),
                finalize=finalize,
            )
        # A replay whose parent is still the current revision is not a replay:
        # the record never moved onto it, so the promotion that wrote it never
        # finished. Falling through re-derives the same triple and completes it.
        if delta.expected_revision_id != current.revision_id:
            raise StaleParentError(
                f"delta expects revision {delta.expected_revision_id!r} but the "
                + f"current revision is {current.revision_id!r}"
            )
        _check_lineage(store, current)
        return _finalize(
            store,
            _apply(
                store,
                delta,
                current,
                fingerprint=fingerprint,
                repository=repository_value,
                digest_of=digest_of,
                checkout=digest_root,
                durability=durability,
                fork_edge=fork_edge,
            ),
            finalize=finalize,
        )


def _refuse_over_existing_history(store: storage.WorkStore) -> None:
    """Refuse a genesis into a work directory that already holds revisions.

    Completeness is the wrong question here: a store missing one half of every
    pair still holds the work, and creating a second lineage beside it is the
    erasure this guard exists to prevent. Any receipt or projection at all is
    enough to refuse.
    """
    report = store.recover()
    held = [file.path.name for file in report.complete] + list(report.incomplete)
    if not held:
        return
    raise GenesisConflictError(
        f"work {store.work_id!r} has no {storage.RECORD_FILENAME}, but its work "
        + f"directory still holds {'; '.join(held)}: a genesis delta creates the "
        + "first record and never orphans existing history"
    )


def _find_replay(
    store: storage.WorkStore, delta: WheypointDelta, fingerprint: str
) -> WheypointRevision | None:
    """The receipt this exact request already produced against this parent.

    The receipt's id is a pure function of the request and its parent, so the
    replay is looked up by name and then made to prove it: a file at that name
    that does not quote this request against this parent is not a replay. A
    genesis receipt records no parent at all, so the sentinel the delta names
    is translated to the `None` the receipt actually carries.
    """
    parent = (
        None
        if delta.expected_revision_id == GENESIS_PARENT
        else delta.expected_revision_id
    )
    revision = store.find_complete_revision(_revision_id(delta, fingerprint))
    if revision is None:
        return None
    if revision.parent_revision_id != parent or revision.request_digest != fingerprint:
        return None
    return revision


def _replayed(
    store: storage.WorkStore, revision: WheypointRevision, current: WheypointRecord
) -> PendingRevision:
    markdown = store.projection_path(
        revision.revision_number, revision.revision_id
    ).read_text(encoding="utf-8")
    return PendingRevision(
        revision=revision,
        record=current,
        projection=projection_mod.parse(markdown),
        markdown=markdown,
        replayed=True,
    )


def resume_revision(
    revision_id: str,
    *,
    store: storage.WorkStore,
    finalize: Callable[[PendingRevision], None] | None = None,
) -> CommitResult:
    """Resume finalization for a complete revision already written to disk."""
    with store.lock():
        current = store.read_record()
        if current is None:
            raise CommitError(
                f"work {store.work_id!r} has no record while resuming "
                + f"revision {revision_id!r}"
            )
        revision = store.find_complete_revision(revision_id)
        if revision is None:
            raise CommitError(
                f"revision {revision_id!r} is not a complete immutable revision "
                + f"in work {store.work_id!r}"
            )
        return _finalize(
            store,
            _replayed(store, revision, current),
            finalize=finalize,
        )


def _finalize(
    store: storage.WorkStore,
    pending: PendingRevision,
    *,
    finalize: Callable[[PendingRevision], None] | None,
) -> CommitResult:
    """Make one pending revision durable, then collect durability evidence.

    The finalizer runs first, while the record lock is still held. The
    projection it writes claims the durability the caller asked for, so a
    finalizer that fails must leave no promoted record behind to carry that
    claim.
    """
    if finalize is not None:
        finalize(pending)
    if not pending.replayed:
        store.promote(pending.record, pending.revision, pending.markdown)
    return CommitResult(
        revision=pending.revision,
        record=pending.record,
        projection=pending.projection,
        markdown=pending.markdown,
        replayed=pending.replayed,
    )


def _check_lineage(store: storage.WorkStore, current: WheypointRecord) -> None:
    found = store.stored_receipt(current.revision_number, current.revision_id)
    if found is None:
        raise CommitError(
            f"current revision {current.revision_id!r} has no immutable receipt "
            + "in this store"
        )
    if found.digest != current.revision_digest:
        raise CommitError(
            f"current revision {current.revision_id!r} does not match the digest "
            + "the record quotes"
        )


def ancestry(
    receipts: tuple[WheypointRevision, ...], current: WheypointRevision
) -> tuple[WheypointRevision, ...]:
    """The current-first receipts reachable through parent pointers."""
    known = {receipt.revision_id: receipt for receipt in receipts}
    chain = [current]
    seen = {current.revision_id}
    parent_id = current.parent_revision_id
    while parent_id is not None and parent_id not in seen:
        parent = known.get(parent_id)
        if parent is None:
            break
        chain.append(parent)
        seen.add(parent_id)
        parent_id = parent.parent_revision_id
    return tuple(chain)


def proposed_entry_id(
    work_id: str,
    parent: str,
    kind: EntryKind,
    summary: str,
    blocks_continuation: bool,
    index: int,
) -> str:
    """A name derived from the request that proposed the entry.

    The parent revision and the proposal's own content and position are all in
    the hash, so two writers proposing the same entry against the same parent
    agree on its id -- and the replay of one request cannot collide with a
    different request's entry. `index` is the position among the proposals of
    the same kind.
    """
    digest = canonical.digest_value(
        {
            "work_id": work_id,
            "parent": parent,
            "kind": kind.value,
            "summary": summary,
            "blocks_continuation": blocks_continuation,
            "index": index,
        }
    )
    hexdigest = digest[len(canonical.DIGEST_PREFIX) :]
    return f"{_KIND_PREFIX[kind]}-{hexdigest[:_ID_HEX]}"


def kind_of_entry_id(entry_id: str) -> EntryKind | None:
    """The kind an entry id's prefix names, or None for a foreign id."""
    for kind, prefix in _KIND_PREFIX.items():
        if entry_id.startswith(f"{prefix}-"):
            return kind
    return None


def _entry_id(delta: WheypointDelta, proposed: ProposedEntry, index: int) -> str:
    return proposed_entry_id(
        delta.work_id,
        delta.expected_revision_id,
        proposed.kind,
        proposed.summary,
        proposed.blocks_continuation,
        index,
    )


def _revision_id(delta: WheypointDelta, fingerprint: str) -> str:
    digest = canonical.digest_value(
        {
            "work_id": delta.work_id,
            "parent": delta.expected_revision_id,
            "request": fingerprint,
        }
    )
    return f"rev-{digest[len(canonical.DIGEST_PREFIX) :][:_ID_HEX]}"


def _proposed_entries(delta: WheypointDelta, kind: EntryKind) -> list[ProposedEntry]:
    return list(
        cast("list[ProposedEntry] | None", getattr(delta, ADDITION_FIELDS[kind])) or []
    )


def _additions(delta: WheypointDelta) -> dict[EntryKind, list[ProtectedEntry]]:
    """New entries by kind."""
    additions: dict[EntryKind, list[ProtectedEntry]] = {}
    for kind in ADDITION_FIELDS:
        additions[kind] = [
            ProtectedEntry(
                entry_id=_entry_id(delta, entry, index),
                kind=entry.kind,
                summary=entry.summary,
                state=EntryState.ACTIVE,
                blocks_continuation=entry.blocks_continuation,
                rationale=entry.rationale,
                quote=entry.quote,
                owner=entry.owner,
                when=entry.when,
                scope=entry.scope,
            )
            for index, entry in enumerate(_proposed_entries(delta, kind))
        ]
    return additions


def revision_id_for(delta: WheypointDelta) -> str:
    """Return the deterministic receipt id for a request delta."""
    return _revision_id(delta, records.request_fingerprint(delta))


def _existing_entries(
    current: WheypointRecord, kind: EntryKind
) -> list[ProtectedEntry]:
    return cast(list[ProtectedEntry], getattr(current, _RECORD_FIELDS[kind]))


def _digest_root() -> Path:
    """Return the default repository root for artifact links.

    ``commit`` resolves this root once per transaction and passes the resulting
    digest callback through the revision builder, so a multi-link revision does
    not rediscover the Git root for every path.
    """
    return paths.resolve_repo_root(None)


def _merge_artifact_links(
    current_links: list[ArtifactLink],
    add: list[ArtifactLink] | None,
    remove: list[str] | None,
    *,
    revision_id: str,
    digest_of: Callable[[str], str | None],
) -> list[ArtifactLink]:
    """Artifact links as a set keyed by normalized reference (S3, S4).

    An added link replaces the one already carried for its reference and is
    pinned to the revision being written, with the target's digest computed
    here. A pinnable reference that does not resolve is refused; an
    unpinnable one is linked with no digest and may cover no entry. Removal
    names a reference or a bare repository path; an unknown one is refused
    rather than ignored, and an empty list never reaches this point.

    A `wheypoint:` ref with no `@rev` names its target at any revision: an
    add replaces the link held for that target, and a removal deletes it. A
    ref with an explicit `@rev` matches that pin only.
    """
    if add is None and remove is None:
        return current_links
    order = [_link_key(link) for link in current_links]
    by_ref = dict(zip(order, current_links, strict=True))
    for link in add or ():
        try:
            requested = refs.normalize_ref(records.effective_ref(link))
            # An unpinned record link names whatever the target is now; the
            # link pins that revision so a later read resolves the same record.
            ref = refs.pin_record(requested, corpus_home=paths.corpus_home())
        except ValueError as exc:
            raise CommitError(f"add_artifact_links names an unusable ref: {exc}") from exc
        scheme = refs.parse_ref(ref).scheme
        # The digest is host-computed from the target (S3): a caller-supplied
        # value is never honoured.
        digest: str | None = None
        if not refs.is_pinnable(scheme):
            if link.covers_entry_ids:
                raise CommitError(
                    f"unpinnable-scheme: {ref!r} cannot pin a digest, so it "
                    + "cannot cover protected entries"
                )
        else:
            digest = digest_of(ref)
            if digest is None:
                raise CommitError(
                    f"add_artifact_links names a ref this host cannot digest: {ref!r}"
                )
        target = _unpinned_record(requested)
        if target is not None:
            # An unpinned record ref refreshes the link it pinned earlier.
            for key in [k for k in by_ref if k != ref and _record_target(k) == target]:
                del by_ref[key]
                order[order.index(key)] = ref
        # A line ref pinned at a new HEAD replaces the one pinned at an old HEAD.
        key = refs.strip_pin(ref)
        if key not in order:
            order.append(key)
        by_ref[key] = evolve(
            link,
            ref=ref,
            path=ref.partition(":")[2],
            digest=digest,
            revision_id=revision_id,
        )
    for value in remove or ():
        key = _removal_key(value)
        target = _unpinned_record(key)
        matched = [
            k for k in by_ref if k == key or (target and _record_target(k) == target)
        ]
        if not matched:
            raise CommitError(
                f"remove_artifact_links names a path this record does not carry: {value!r}"
            )
        for k in matched:
            del by_ref[k]
    return [by_ref[key] for key in dict.fromkeys(order) if key in by_ref]


def _record_target(ref: str) -> str | None:
    """A `wheypoint:` ref without its `@rev`, or None for any other ref."""
    try:
        parsed = refs.parse_ref(ref)
    except ValueError:
        return None
    if parsed.scheme is not refs.Scheme.WHEYPOINT:
        return None
    entry = "" if parsed.entry_id is None else f"#{parsed.entry_id}"
    return refs.normalize_ref(f"wheypoint:{parsed.project_key}/{parsed.work_id}{entry}")


record_target = _record_target


def _unpinned_record(ref: str) -> str | None:
    """The target of a `wheypoint:` ref that names no `@rev`, else None."""
    target = _record_target(ref)
    return target if target == ref else None


def _link_key(link: ArtifactLink) -> str:
    ref = records.effective_ref(link)
    try:
        return refs.strip_pin(refs.normalize_ref(ref))
    except ValueError:
        return ref


def _removal_key(value: str) -> str:
    """A removal names a reference, or a bare path read as `repo:`."""
    try:
        return refs.strip_pin(refs.normalize_ref(value))
    except ValueError:
        return _link_key(ArtifactLink(path=value))


def _transitioned(
    entry: ProtectedEntry, transition: EntryTransition | None
) -> ProtectedEntry:
    if transition is None:
        return entry
    return evolve(
        entry,
        state=transition.resulting_state,
        rationale=transition.rationale,
        superseded_by=transition.target_entry_id,
    )


def _apply(
    store: storage.WorkStore,
    delta: WheypointDelta,
    current: WheypointRecord,
    *,
    fingerprint: str,
    repository: RepositoryProvenance,
    digest_of: Callable[[str], str | None],
    checkout: Path,
    durability: Durability,
    fork_edge: WorkEdge | None,
) -> PendingRevision:
    """The next revision of `current`."""
    transitions = list(delta.transitions or [])
    forged = [t.entry_id for t in transitions if t.action is TransitionAction.FORK]
    if forged:
        raise CommitError(
            "fork transitions are host-derived, not on request "
            + f"({', '.join(forged)})"
        )
    additions = _additions(delta)
    added_ids = {entry.entry_id for group in additions.values() for entry in group}
    problems = records.validate_transitions(current, transitions, added_ids=added_ids)
    if problems:
        raise CommitError("; ".join(problems))
    by_entry = {transition.entry_id: transition for transition in transitions}

    kept: dict[EntryKind, list[ProtectedEntry]] = {}
    for kind in _RECORD_FIELDS:
        existing = _existing_entries(current, kind)
        kept[kind] = [
            _transitioned(entry, by_entry.get(entry.entry_id)) for entry in existing
        ]

    revision_id = _revision_id(delta, fingerprint)
    number = current.revision_number + 1
    draft = _draft_record(
        current,
        delta,
        revision_id=revision_id,
        number=number,
        kept=kept,
        additions=additions,
        digest_of=digest_of,
        decisions_moved=bool(additions[EntryKind.DECISION])
        or any(
            (entry := records.find_entry(current, transition.entry_id)) is not None
            and entry.kind is EntryKind.DECISION
            for transition in transitions
        ),
    )
    merged = _merge_edges(
        current.edges, delta, host=fork_edge, revision_id=revision_id
    )
    draft = _with_edges(draft, merged.edges)
    return _finish(
        store,
        delta,
        draft,
        parent_revision_id=current.revision_id,
        # `_check_lineage` has already proven the record's own pointer against
        # the receipt on disk, so quoting it here pins the ancestor rather than
        # re-asserting it.
        parent_revision_digest=current.revision_digest,
        fingerprint=fingerprint,
        additions=[entry for kind in ADDITION_FIELDS for entry in additions[kind]],
        transitions=transitions,
        applied_edges=merged.applied,
        removed_edges=merged.removed,
        repository=repository,
        durability=durability,
        checkout=checkout,
    )


def _with_edges(
    draft: WheypointRecord, edges: tuple[WorkEdge, ...]
) -> WheypointRecord:
    try:
        return evolve(draft, edges=edges)
    except ValueError as exc:
        raise CommitError(f"the delta does not produce a legal record: {exc}") from exc


def _genesis(
    store: storage.WorkStore,
    delta: WheypointDelta,
    *,
    fingerprint: str,
    repository: RepositoryProvenance,
    project_key: str,
    digest_of: Callable[[str], str | None],
    checkout: Path,
    durability: Durability,
    fork_edge: WorkEdge | None,
    imported_stamps: tuple[int | None, int | None] | None = None,
) -> PendingRevision:
    """The first record for a work id, built from the delta alone.

    There is no parent to carry anything forward from, so everything a record
    needs has to be in the request: the semantic context it replaces, and the
    provenance that names when it was captured. `project_key` is the one
    exception -- it identifies the corpus the record is being written into, so
    it is derived from the artifact root that owns the transaction rather than
    accepted from a caller who could claim another project's identity.
    """
    missing = [
        name
        for name in ("orientation", "working_context", "next_action")
        if getattr(delta, name) is None
    ]
    if missing:
        raise CommitError(
            "a genesis delta has no parent to carry state from, so it must "
            + f"carry {', '.join(missing)}"
        )
    next_action = cast(NextAction, delta.next_action)
    if delta.transitions:
        raise CommitError("a genesis delta has no existing entries to transition")
    created = (
        delta.session_provenance.captured_at
        if delta.session_provenance is not None
        else None
    )
    if created is None:
        raise CommitError(
            "a genesis delta must carry session_provenance.captured_at: the "
            + "runtime derives the record's created time rather than reading a clock"
        )

    additions = _additions(delta)
    if not any(additions.values()) and delta.notes is None and fork_edge is None:
        raise CommitError(
            "a first checkpoint must capture at least one decision, question, "
            + "or directive, or a notes body: orientation alone is not a record"
        )
    revision_id = _revision_id(delta, fingerprint)
    merged = _merge_edges((), delta, host=fork_edge, revision_id=revision_id)
    try:
        draft = WheypointRecord(
            schema_version=SCHEMA_VERSION,
            work_id=store.work_id,
            # A genesis record answers to its own work id: the runtime invents no
            # second name for work whose caller has not given it one.
            slug=store.work_id,
            title=_title(delta.orientation or ""),
            created=created,
            project_key=project_key,
            revision_id=revision_id,
            revision_number=1,
            revision_digest=_UNPINNED_DIGEST,
            orientation=delta.orientation or "",
            working_context=list(delta.working_context or []),
            notes=delta.notes,
            notes_revision_number=(
                (1 if delta.notes is not None else None)
                if imported_stamps is None
                else (imported_stamps[0] if delta.notes is not None else None)
            ),
            decisions_revision_number=(
                (1 if additions[EntryKind.DECISION] else None)
                if imported_stamps is None
                else imported_stamps[1]
            ),
            next_action=next_action,
            decisions=additions[EntryKind.DECISION],
            questions=additions[EntryKind.QUESTION],
            directives=additions[EntryKind.DIRECTIVE],
            artifact_links=_merge_artifact_links(
                [],
                delta.add_artifact_links,
                delta.remove_artifact_links,
                revision_id=revision_id,
                digest_of=digest_of,
            ),
            edges=merged.edges,
        )
    except ValueError as exc:
        raise CommitError(f"the delta does not produce a legal record: {exc}") from exc

    return _finish(
        store,
        delta,
        draft,
        parent_revision_id=None,
        parent_revision_digest=None,
        fingerprint=fingerprint,
        additions=[entry for kind in ADDITION_FIELDS for entry in additions[kind]],
        transitions=[],
        applied_edges=merged.applied,
        removed_edges=merged.removed,
        repository=repository,
        durability=durability,
        checkout=checkout,
    )


def _merge_edges(
    current: tuple[WorkEdge, ...],
    delta: WheypointDelta,
    *,
    host: WorkEdge | None,
    revision_id: str,
) -> edges_mod.MergedEdges:
    """The delta's edges plus the host's fork edge; `None` when both are absent."""
    add = [*(delta.add_edges or ()), *([host] if host else [])]
    try:
        return edges_mod.merge_edges(
            current, add or None, delta.remove_edges, revision_id=revision_id
        )
    except edges_mod.EdgeError as exc:
        raise CommitError(str(exc)) from exc


def _title(orientation: str) -> str:
    """The record's readable name: the first line of what the delta oriented on."""
    return orientation.strip().splitlines()[0].strip()


def _finish(
    store: storage.WorkStore,
    delta: WheypointDelta,
    draft: WheypointRecord,
    *,
    parent_revision_id: str | None,
    parent_revision_digest: str | None,
    fingerprint: str,
    additions: list[ProtectedEntry],
    transitions: list[EntryTransition],
    applied_edges: tuple[WorkEdge, ...],
    removed_edges: tuple[WorkEdgeKey, ...],
    repository: RepositoryProvenance,
    durability: Durability,
    checkout: Path,
) -> PendingRevision:
    """Render the draft into one typed pending revision."""
    projected, markdown = projection_mod.build_projection(
        draft, durability=durability, checkout=checkout
    )
    revision = WheypointRevision(
        schema_version=SCHEMA_VERSION,
        work_id=store.work_id,
        parent_revision_id=parent_revision_id,
        revision_id=draft.revision_id,
        revision_number=draft.revision_number,
        request_digest=fingerprint,
        record_digest=records.record_digest(draft),
        applied_additions=additions,
        applied_transitions=transitions,
        applied_edges=applied_edges,
        removed_edges=removed_edges,
        projection_path=store.relative_projection_path(
            draft.revision_number, draft.revision_id
        ),
        repository=repository,
        parent_revision_digest=parent_revision_digest,
        session_provenance=delta.session_provenance,
    )
    record = evolve(draft, revision_digest=records.revision_digest(revision))
    return PendingRevision(
        revision=revision,
        record=record,
        projection=projected,
        markdown=markdown,
    )


def _draft_record(
    current: WheypointRecord,
    delta: WheypointDelta,
    *,
    revision_id: str,
    number: int,
    kept: dict[EntryKind, list[ProtectedEntry]],
    additions: dict[EntryKind, list[ProtectedEntry]],
    digest_of: Callable[[str], str | None],
    decisions_moved: bool,
) -> WheypointRecord:
    """The next record: replacements where the delta spoke, carry-forward else.

    `notes_revision_number` and `decisions_revision_number` move to `number`
    exactly when the delta replaced the notes or added or transitioned a
    decision.

    Every committed revision restamps `schema_version` at the runtime's
    current version, not just the genesis record. A carried-forward record
    that keeps an older stamp would let this runtime write content only a
    newer schema allows while still claiming the older version, which a
    reader that trusts the stamp cannot detect.
    """
    try:
        return evolve(
            current,
            schema_version=SCHEMA_VERSION,
            revision_id=revision_id,
            revision_number=number,
            revision_digest=_UNPINNED_DIGEST,
            orientation=_replaced(delta.orientation, current.orientation),
            working_context=_replaced(delta.working_context, current.working_context),
            notes=_replaced(delta.notes, current.notes),
            notes_revision_number=_replaced(
                None if delta.notes is None else number,
                current.notes_revision_number,
            ),
            decisions_revision_number=number
            if decisions_moved
            else current.decisions_revision_number,
            next_action=_replaced(delta.next_action, current.next_action),
            decisions=kept[EntryKind.DECISION] + additions[EntryKind.DECISION],
            questions=kept[EntryKind.QUESTION] + additions[EntryKind.QUESTION],
            directives=kept[EntryKind.DIRECTIVE] + additions[EntryKind.DIRECTIVE],
            artifact_links=_merge_artifact_links(
                list(current.artifact_links),
                delta.add_artifact_links,
                delta.remove_artifact_links,
                revision_id=revision_id,
                digest_of=digest_of,
            ),
        )
    except ValueError as exc:
        raise CommitError(f"the delta does not produce a legal record: {exc}") from exc


def _replaced(proposed: object, carried: object) -> object:
    """`None` means unchanged; an explicit value -- including `[]` -- replaces."""
    return carried if proposed is None else proposed
