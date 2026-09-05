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
2. **Lineage before application.** The parent the record names has to be a
   complete immutable revision whose digest the record still quotes; a chain
   that cannot be walked backwards is not extended forwards.
3. **Rehydration before compaction.** A delta written after a context
   compaction has to prove it read the *current* revision, not the revision the
   compacted session remembered.

Identity is derived, never drawn. Revision ids hash the parent and the request;
entry ids hash the parent and the proposed entry. Nothing here reads a clock or
a random source, so the same request against the same parent produces the same
names -- which is what makes replay recognisable at all.

Omission carries forward. A delta field left `None` means "unchanged", and the
additive fields only ever add, so no protected entry, artifact link, or dossier
fork can leave the record without an `EntryTransition` naming it.

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
    CompactionRecord,
    Durability,
    EntryKind,
    EntryState,
    EntryTransition,
    NextAction,
    ProposedEntry,
    ProtectedEntry,
    RepositoryProvenance,
    WheypointDelta,
    WheypointProjection,
    WheypointRecord,
    WheypointRevision,
)

from easy_cheese.shared import paths

from . import canonical
from . import lineage
from . import lint as lint_mod
from . import projection as projection_mod
from . import records, storage

# A record digest deliberately excludes `revision_digest` (see records.py), so
# the draft record can be hashed, quoted by its receipt, and only then told
# which receipt quoted it. This placeholder holds that field open in between.
_UNPINNED_DIGEST = f"{canonical.DIGEST_PREFIX}{'0' * 64}"
_ID_HEX = 12
# The parent a delta names when it is asking for the *first* record. Every
# derived revision id is `rev-<12 hex>` (see `_revision_id`), so this sentinel
# lives outside that namespace by construction: no hash can produce it, and no
# real parent can be mistaken for it.
GENESIS_PARENT = "genesis"
_KIND_PREFIX = {
    EntryKind.DECISION: "d",
    EntryKind.QUESTION: "q",
    EntryKind.BLOCKER: "b",
    EntryKind.DIRECTIVE: "v",
}
ADDITION_FIELDS = {
    EntryKind.DECISION: "add_decisions",
    EntryKind.QUESTION: "add_questions",
    EntryKind.BLOCKER: "add_blockers",
    EntryKind.DIRECTIVE: "add_directives",
}
_RECORD_FIELDS = {
    EntryKind.DECISION: "decisions",
    EntryKind.QUESTION: "questions",
    EntryKind.BLOCKER: "blockers",
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
) -> CommitResult:
    """Apply `delta` to the store's current record under the record lock."""
    repository_value: RepositoryProvenance = (
        RepositoryProvenance() if repository is None else repository
    )
    if delta.work_id != store.work_id:
        raise CommitError(
            f"delta names work {delta.work_id!r} but the store holds "
            + f"{store.work_id!r}"
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
                    durability=durability,
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
        checked_lineage = _check_lineage(store, current)
        _check_rehydration(delta, current)
        return _finalize(
            store,
            _apply(
                store,
                delta,
                current,
                lineage=checked_lineage,
                fingerprint=fingerprint,
                repository=repository_value,
                durability=durability,
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
    if (
        revision.parent_revision_id != parent
        or revision.request_digest != fingerprint
    ):
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


def _check_lineage(
    store: storage.WorkStore, current: WheypointRecord
) -> lineage.Lineage:
    parent = store.read_revision(current.revision_number, current.revision_id)
    if parent is None:
        raise CommitError(
            f"current revision {current.revision_id!r} has no immutable receipt "
            + "in this store"
        )
    if records.revision_digest(parent) != current.revision_digest:
        raise CommitError(
            f"current revision {current.revision_id!r} does not match the digest "
            + "the record quotes"
        )
    checked = lineage.walk(
        (file.revision for file in store.recover().complete),
        parent,
    )
    if checked.issues:
        raise CommitError(_lineage_issue_detail(checked.issues[0]))
    return checked


def _lineage_issue_detail(issue: lineage.LineageIssue) -> str:
    if issue.kind is lineage.LineageIssueKind.PARENT_UNRESOLVED:
        if issue.cycle:
            return (
                f"revision {issue.revision.revision_id!r} re-enters the chain at "
                + f"{issue.parent_revision_id!r}"
            )
        return (
            f"revision {issue.revision.revision_id!r} names parent "
            + f"{issue.parent_revision_id!r}, which is not a complete immutable "
            + "revision"
        )
    if issue.kind is lineage.LineageIssueKind.PARENT_NOT_CONTIGUOUS:
        parent = issue.parent
        assert parent is not None
        return (
            f"revision {issue.revision.revision_id!r} of work "
            + f"{issue.revision.work_id!r} names parent "
            + f"{issue.parent_revision_id!r} of work {parent.work_id!r} at "
            + f"revision number {parent.revision_number}, but its own revision "
            + f"number is {issue.revision.revision_number}"
        )
    if issue.expected_digest is None:
        return (
            f"revision {issue.revision.revision_id!r} is stamped schema version "
            + f"{issue.revision.schema_version} and names parent "
            + f"{issue.parent_revision_id!r} without pinning its digest"
        )
    return (
        f"revision {issue.revision.revision_id!r} pins parent "
        + f"{issue.parent_revision_id!r} at {issue.expected_digest}, but that "
        + f"receipt now hashes to {issue.actual_digest}"
    )




def _check_rehydration(delta: WheypointDelta, current: WheypointRecord) -> None:
    """Make a compacted delta prove it re-read the record it is writing over.

    The flag says a compaction happened; the record is the evidence that the
    durable state was reloaded first. Naming the current revision is the weakest
    of the three checks -- an id survives in a stale transcript -- so the record
    also has to quote the digest of the record it re-read and account for every
    protected entry that record still carries. Only a session that actually
    reloaded the record can produce all three, and a later reader can re-derive
    each of them rather than take the claim on faith.
    """
    if not delta.compacted:
        return
    compaction = delta.compaction
    if compaction is not None and compaction.prior_compaction_revision_id is not None:
        raise CommitError(
            "a delta may not declare prior_compaction_revision_id "
            + f"{compaction.prior_compaction_revision_id!r}: the runtime derives "
            + "the previous compaction from the lineage on disk, because a "
            + "compacted session's memory of that lineage is exactly what was lost"
        )
    if compaction is None:
        raise CommitError(
            "a compacted delta must rehydrate first: it carries no compaction "
            + f"record naming the current revision {current.revision_id!r}, the "
            + "digest of the record it re-read, and the entries it reconciled"
        )
    if compaction.rehydrated_from_revision_id != current.revision_id:
        raise CommitError(
            "a compacted delta must be rehydrated from the current revision "
            + f"{current.revision_id!r}, not "
            + f"{compaction.rehydrated_from_revision_id!r}"
        )
    expected_digest = records.record_digest(current)
    if compaction.rehydrated_record_digest != expected_digest:
        raise CommitError(
            "the compaction record quotes record digest "
            + f"{compaction.rehydrated_record_digest}, but revision "
            + f"{current.revision_id!r} hashes to {expected_digest}: the delta "
            + "did not re-read the record it is writing over"
        )
    reconciled = set(compaction.reconciled_entry_ids)
    unreconciled = [
        entry.entry_id
        for entry in records.entries(current)
        if entry.entry_id not in reconciled
    ]
    if unreconciled:
        raise CommitError(
            "the compaction record does not reconcile protected entries "
            + f"{', '.join(repr(entry_id) for entry_id in unreconciled)} held by "
            + f"revision {current.revision_id!r}"
        )




def _entry_id(delta: WheypointDelta, proposed: ProposedEntry, index: int) -> str:
    """A name derived from the request that proposed the entry.

    The parent revision and the proposal's own content and position are all in
    the hash, so two writers proposing the same entry against the same parent
    agree on its id -- and the replay of one request cannot collide with a
    different request's entry.
    """
    digest = canonical.digest_value(
        {
            "work_id": delta.work_id,
            "parent": delta.expected_revision_id,
            "kind": proposed.kind.value,
            "summary": proposed.summary,
            "blocks_continuation": proposed.blocks_continuation,
            "index": index,
        }
    )
    hexdigest = digest[len(canonical.DIGEST_PREFIX) :]
    return f"{_KIND_PREFIX[proposed.kind]}-{hexdigest[:_ID_HEX]}"


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
    return list(cast("list[ProposedEntry] | None", getattr(delta, ADDITION_FIELDS[kind])) or [])


def _additions(delta: WheypointDelta, kind: EntryKind) -> list[ProtectedEntry]:
    proposed = _proposed_entries(delta, kind)
    return [
        ProtectedEntry(
            entry_id=_entry_id(delta, entry, index),
            kind=entry.kind,
            summary=entry.summary,
            state=EntryState.ACTIVE,
            blocks_continuation=entry.blocks_continuation,
            rationale=entry.rationale,
            quote=entry.quote,
        )
        for index, entry in enumerate(proposed)
    ]


def revision_id_for(delta: WheypointDelta) -> str:
    """Return the deterministic receipt id for a request delta."""
    return _revision_id(delta, records.request_fingerprint(delta))


def _existing_entries(
    current: WheypointRecord, kind: EntryKind
) -> list[ProtectedEntry]:
    return cast(list[ProtectedEntry], getattr(current, _RECORD_FIELDS[kind]))


def _artifact_digest() -> Callable[[str], str | None]:
    """Digest repo-relative artifact files from the repository root (S3).

    The root is the Git toplevel when there is one, so the digest does not
    depend on which subdirectory the checkpoint was run from; outside a
    repository the working directory is the root. The root is resolved lazily,
    on the first path actually digested, so a delta with no artifact links to
    add never spawns `git rev-parse --show-toplevel`.
    """
    digest_of: Callable[[str], str | None] | None = None

    def digest(path: str) -> str | None:
        nonlocal digest_of
        if digest_of is None:
            digest_of = lint_mod.artifact_digest_in(paths.git_toplevel() or Path.cwd())
        return digest_of(path)

    return digest


def _merge_artifact_links(
    current_links: list[ArtifactLink],
    add: list[ArtifactLink] | None,
    remove: list[str] | None,
    *,
    revision_id: str,
    digest_of: Callable[[str], str | None],
) -> list[ArtifactLink]:
    """Artifact links as a set keyed by path (S3, S4).

    An added link replaces the one already carried for its path and is pinned
    to the revision being written, with the file's digest computed here when
    the path resolves to a file. Removal names paths; an unknown path is
    refused rather than ignored, and an empty list never reaches this point.
    """
    if add is None and remove is None:
        return current_links
    order = [link.path for link in current_links]
    by_path = {link.path: link for link in current_links}
    for link in add or ():
        # The digest is host-computed from the file (S3): a path that does not
        # resolve to a file under the repository root carries no digest, and a
        # caller-supplied value is never honoured.
        if link.path not in by_path:
            order.append(link.path)
        digest = digest_of(link.path)
        if digest is None:
            raise CommitError(
                f"add_artifact_links names a path this host cannot digest: {link.path!r}"
            )
        by_path[link.path] = evolve(link, digest=digest, revision_id=revision_id)
    for path in remove or ():
        if path not in by_path:
            raise CommitError(
                f"remove_artifact_links names a path this record does not carry: {path!r}"
            )
        del by_path[path]
    return [by_path[path] for path in order if path in by_path]


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
    lineage: lineage.Lineage,
    fingerprint: str,
    repository: RepositoryProvenance,
    durability: Durability,
) -> PendingRevision:
    transitions = list(delta.transitions or [])
    problems = records.validate_transitions(current, transitions)
    if problems:
        raise CommitError("; ".join(problems))
    by_entry = {transition.entry_id: transition for transition in transitions}

    kept: dict[EntryKind, list[ProtectedEntry]] = {}
    preserved: list[str] = []
    for kind in _RECORD_FIELDS:
        existing = _existing_entries(current, kind)
        kept[kind] = [
            _transitioned(entry, by_entry.get(entry.entry_id)) for entry in existing
        ]
        preserved.extend(
            entry.entry_id for entry in existing if entry.entry_id not in by_entry
        )

    additions = {kind: _additions(delta, kind) for kind in ADDITION_FIELDS}
    revision_id = _revision_id(delta, fingerprint)
    number = current.revision_number + 1
    draft = _draft_record(
        current,
        delta,
        revision_id=revision_id,
        number=number,
        kept=kept,
        additions=additions,
    )
    compaction = (
        None
        if delta.compaction is None
        else evolve(
            delta.compaction,
            prior_compaction_revision_id=lineage.prior_compaction_revision_id,
        )
    )
    return _finish(
        store,
        delta,
        draft,
        compaction=compaction,
        parent_revision_id=current.revision_id,
        # `_check_lineage` has already proven the record's own pointer against
        # the receipt on disk, so quoting it here pins the ancestor rather than
        # re-asserting it.
        parent_revision_digest=current.revision_digest,
        fingerprint=fingerprint,
        additions=[entry for kind in ADDITION_FIELDS for entry in additions[kind]],
        transitions=transitions,
        preserved=preserved,
        repository=repository,
        durability=durability,
    )


def _genesis(
    store: storage.WorkStore,
    delta: WheypointDelta,
    *,
    fingerprint: str,
    repository: RepositoryProvenance,
    durability: Durability,
) -> PendingRevision:
    """The first record for a work id, built from the delta alone.

    There is no parent to carry anything forward from, so everything a record
    needs has to be in the request: the semantic context it replaces, and the
    provenance that names when it was captured. `project_key` is the one
    exception -- it identifies the corpus the record is being written into, so
    it is read from the environment that owns it rather than accepted from a
    caller who could claim another project's identity.
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
    if delta.compacted:
        raise CommitError(
            "a genesis delta cannot declare compaction: there is no current "
            + "revision to rehydrate from"
        )
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

    additions = {kind: _additions(delta, kind) for kind in ADDITION_FIELDS}
    if not any(additions.values()) and delta.notes is None:
        raise CommitError(
            "a first checkpoint must capture at least one decision, question, "
            + "blocker, or directive, or a notes body: orientation alone is not a record"
        )
    revision_id = _revision_id(delta, fingerprint)
    try:
        draft = WheypointRecord(
            schema_version=SCHEMA_VERSION,
            work_id=store.work_id,
            # A genesis record answers to its own work id: the runtime invents no
            # second name for work whose caller has not given it one.
            slug=store.work_id,
            title=_title(delta.orientation or ""),
            created=created,
            project_key=paths.project_key(),
            revision_id=revision_id,
            revision_number=1,
            revision_digest=_UNPINNED_DIGEST,
            orientation=delta.orientation or "",
            working_context=list(delta.working_context or []),
            notes=delta.notes,
            next_action=next_action,
            decisions=additions[EntryKind.DECISION],
            questions=additions[EntryKind.QUESTION],
            blockers=additions[EntryKind.BLOCKER],
            directives=additions[EntryKind.DIRECTIVE],
            artifact_links=_merge_artifact_links(
                [],
                delta.add_artifact_links,
                delta.remove_artifact_links,
                revision_id=revision_id,
                digest_of=_artifact_digest(),
            ),
            decision_dossier=list(delta.decision_dossier or []),
        )
    except ValueError as exc:
        raise CommitError(f"the delta does not produce a legal record: {exc}") from exc

    return _finish(
        store,
        delta,
        draft,
        compaction=None,
        parent_revision_id=None,
        parent_revision_digest=None,
        fingerprint=fingerprint,
        additions=[entry for kind in ADDITION_FIELDS for entry in additions[kind]],
        transitions=[],
        preserved=[],
        repository=repository,
        durability=durability,
    )


def _title(orientation: str) -> str:
    """The record's readable name: the first line of what the delta oriented on."""
    return orientation.strip().splitlines()[0].strip()


def _finish(
    store: storage.WorkStore,
    delta: WheypointDelta,
    draft: WheypointRecord,
    *,
    compaction: CompactionRecord | None,
    parent_revision_id: str | None,
    parent_revision_digest: str | None,
    fingerprint: str,
    additions: list[ProtectedEntry],
    transitions: list[EntryTransition],
    preserved: list[str],
    repository: RepositoryProvenance,
    durability: Durability,
) -> PendingRevision:
    """Render the draft into one typed pending revision."""
    projected, markdown = projection_mod.build_projection(
        draft, durability=durability
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
        preserved_entry_ids=preserved,
        projection_path=store.relative_projection_path(
            draft.revision_number, draft.revision_id
        ),
        projection_digest=projected.projection_digest,
        repository=repository,
        parent_revision_digest=parent_revision_digest,
        compaction=compaction,
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
) -> WheypointRecord:
    """The next record: replacements where the delta spoke, carry-forward else."""
    try:
        return evolve(
            current,
            revision_id=revision_id,
            revision_number=number,
            revision_digest=_UNPINNED_DIGEST,
            orientation=_replaced(delta.orientation, current.orientation),
            working_context=_replaced(
                delta.working_context, current.working_context
            ),
            notes=_replaced(delta.notes, current.notes),
            next_action=_replaced(delta.next_action, current.next_action),
            decision_dossier=_replaced(
                delta.decision_dossier, current.decision_dossier
            ),
            decisions=kept[EntryKind.DECISION] + additions[EntryKind.DECISION],
            questions=kept[EntryKind.QUESTION] + additions[EntryKind.QUESTION],
            blockers=kept[EntryKind.BLOCKER] + additions[EntryKind.BLOCKER],
            directives=kept[EntryKind.DIRECTIVE] + additions[EntryKind.DIRECTIVE],
            artifact_links=_merge_artifact_links(
                list(current.artifact_links),
                delta.add_artifact_links,
                delta.remove_artifact_links,
                revision_id=revision_id,
                digest_of=_artifact_digest(),
            ),
        )
    except ValueError as exc:
        raise CommitError(f"the delta does not produce a legal record: {exc}") from exc


def _replaced(proposed: object, carried: object) -> object:
    """`None` means unchanged; an explicit value -- including `[]` -- replaces."""
    return carried if proposed is None else proposed
