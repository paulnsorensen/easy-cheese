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
   a conflict, and a conflict promotes nothing.
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
"""

from __future__ import annotations

from attrs import define, evolve
from easy_cheese_schemas import (
    SCHEMA_VERSION,
    Durability,
    EntryKind,
    EntryState,
    EntryTransition,
    ProposedEntry,
    ProtectedEntry,
    RepositoryProvenance,
    WheypointDelta,
    WheypointProjection,
    WheypointRecord,
    WheypointRevision,
)

import canonical
import projection as projection_mod
import records
import storage

# A record digest deliberately excludes `revision_digest` (see records.py), so
# the draft record can be hashed, quoted by its receipt, and only then told
# which receipt quoted it. This placeholder holds that field open in between.
_UNPINNED_DIGEST = f"{canonical.DIGEST_PREFIX}{'0' * 64}"
_ID_HEX = 12
_KIND_PREFIX = {
    EntryKind.DECISION: "d",
    EntryKind.QUESTION: "q",
    EntryKind.BLOCKER: "b",
}
_ADDITION_FIELDS = {
    EntryKind.DECISION: "add_decisions",
    EntryKind.QUESTION: "add_questions",
    EntryKind.BLOCKER: "add_blockers",
}
_RECORD_FIELDS = {
    EntryKind.DECISION: "decisions",
    EntryKind.QUESTION: "questions",
    EntryKind.BLOCKER: "blockers",
}


class CommitError(RuntimeError):
    """Raised when a delta cannot be applied. Nothing has been promoted."""


class StaleParentError(CommitError):
    """A different request arrived against a parent that is no longer current.

    Distinct from the rest because it is the one failure a caller can act on:
    re-read the record, rebuild the delta against the revision that won, and
    submit again.
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


def commit(
    delta: WheypointDelta,
    *,
    store: storage.WorkStore,
    repository: RepositoryProvenance = RepositoryProvenance(),
    durability: Durability = Durability.CANONICAL_LOCAL,
) -> CommitResult:
    """Apply `delta` to the store's current record under the record lock."""
    if delta.work_id != store.work_id:
        raise CommitError(
            f"delta names work {delta.work_id!r} but the store holds "
            f"{store.work_id!r}"
        )
    with store.lock():
        current = store.read_record()
        if current is None:
            raise CommitError(
                f"work {store.work_id!r} has no record to apply a delta to"
            )
        fingerprint = records.request_fingerprint(delta)
        replay = _find_replay(store, delta, fingerprint)
        if replay is not None:
            return _replayed(store, replay, current)
        if delta.expected_revision_id != current.revision_id:
            raise StaleParentError(
                f"delta expects revision {delta.expected_revision_id!r} but the "
                f"current revision is {current.revision_id!r}"
            )
        _check_lineage(store, current)
        _check_rehydration(delta, current)
        return _apply(
            store,
            delta,
            current,
            fingerprint=fingerprint,
            repository=repository,
            durability=durability,
        )


def _find_replay(
    store: storage.WorkStore, delta: WheypointDelta, fingerprint: str
) -> WheypointRevision | None:
    """The receipt this exact request already produced against this parent."""
    for file in store.recover().complete:
        revision = file.revision
        if (
            revision.parent_revision_id == delta.expected_revision_id
            and revision.request_digest == fingerprint
        ):
            return revision
    return None


def _replayed(
    store: storage.WorkStore, revision: WheypointRevision, current: WheypointRecord
) -> CommitResult:
    markdown = store.projection_path(
        revision.revision_number, revision.revision_id
    ).read_text(encoding="utf-8")
    return CommitResult(
        revision=revision,
        record=current,
        projection=projection_mod.parse(markdown),
        markdown=markdown,
        replayed=True,
    )


def _check_lineage(store: storage.WorkStore, current: WheypointRecord) -> None:
    parent = store.read_revision(current.revision_number, current.revision_id)
    if parent is None:
        raise CommitError(
            f"current revision {current.revision_id!r} has no immutable receipt "
            "in this store"
        )
    if records.revision_digest(parent) != current.revision_digest:
        raise CommitError(
            f"current revision {current.revision_id!r} does not match the digest "
            "the record quotes"
        )


def _check_rehydration(delta: WheypointDelta, current: WheypointRecord) -> None:
    if not delta.compacted:
        return
    if delta.rehydrated_from_revision_id != current.revision_id:
        raise CommitError(
            "a compacted delta must be rehydrated from the current revision "
            f"{current.revision_id!r}, not "
            f"{delta.rehydrated_from_revision_id!r}"
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


def _additions(delta: WheypointDelta, kind: EntryKind) -> list[ProtectedEntry]:
    proposed = getattr(delta, _ADDITION_FIELDS[kind]) or []
    return [
        ProtectedEntry(
            entry_id=_entry_id(delta, entry, index),
            kind=entry.kind,
            summary=entry.summary,
            state=EntryState.ACTIVE,
            blocks_continuation=entry.blocks_continuation,
        )
        for index, entry in enumerate(proposed)
    ]


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
    durability: Durability,
) -> CommitResult:
    transitions = list(delta.transitions or [])
    problems = records.validate_transitions(current, transitions)
    if problems:
        raise CommitError("; ".join(problems))
    by_entry = {transition.entry_id: transition for transition in transitions}

    kept: dict[EntryKind, list[ProtectedEntry]] = {}
    preserved: list[str] = []
    for kind, record_field in _RECORD_FIELDS.items():
        existing = getattr(current, record_field)
        kept[kind] = [
            _transitioned(entry, by_entry.get(entry.entry_id)) for entry in existing
        ]
        preserved.extend(
            entry.entry_id for entry in existing if entry.entry_id not in by_entry
        )

    additions = {kind: _additions(delta, kind) for kind in _ADDITION_FIELDS}
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
    projected, markdown = projection_mod.build_projection(
        draft, durability=durability
    )
    revision = WheypointRevision(
        schema_version=SCHEMA_VERSION,
        work_id=store.work_id,
        parent_revision_id=current.revision_id,
        revision_id=revision_id,
        revision_number=number,
        request_digest=fingerprint,
        record_digest=records.record_digest(draft),
        applied_additions=[
            entry for kind in _ADDITION_FIELDS for entry in additions[kind]
        ],
        applied_transitions=transitions,
        preserved_entry_ids=preserved,
        projection_path=store.relative_projection_path(number, revision_id),
        projection_digest=projected.projection_digest,
        repository=repository,
        rehydrated_from_revision_id=delta.rehydrated_from_revision_id,
        session_provenance=delta.session_provenance,
    )
    record = evolve(draft, revision_digest=records.revision_digest(revision))
    store.promote(record, revision, markdown)
    return CommitResult(
        revision=revision,
        record=record,
        projection=projected,
        markdown=markdown,
        replayed=False,
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
            next_action=_replaced(delta.next_action, current.next_action),
            decision_dossier=_replaced(
                delta.decision_dossier, current.decision_dossier
            ),
            decisions=kept[EntryKind.DECISION] + additions[EntryKind.DECISION],
            questions=kept[EntryKind.QUESTION] + additions[EntryKind.QUESTION],
            blockers=kept[EntryKind.BLOCKER] + additions[EntryKind.BLOCKER],
            artifact_links=[
                *current.artifact_links,
                *(delta.add_artifact_links or []),
            ],
        )
    except ValueError as exc:
        raise CommitError(f"the delta does not produce a legal record: {exc}") from exc


def _replaced(proposed: object, carried: object) -> object:
    """`None` means unchanged; an explicit value -- including `[]` -- replaces."""
    return carried if proposed is None else proposed