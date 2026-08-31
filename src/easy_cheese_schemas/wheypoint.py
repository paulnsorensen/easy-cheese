"""Wheypoint continuity types: the durable record, its deltas and receipts.

A Wheypoint note is a *projection*. The authority is `WheypointRecord`, which
only ever changes by applying a `WheypointDelta` and leaves a `WheypointRevision`
receipt behind. Three rules in this module are what make that authority worth
trusting, and each is attached to the field that produces it rather than left to
every reader to remember:

* **Status is derived, never stored.** Neither the record nor the projection has
  a `status` field; both compute it from the protected entries that are still
  active and still block continuation. A payload that declares `status: ok` over
  an open gate is not repaired -- the key is simply not read.
* **Protected state leaves by transition, not by omission.** Every delta field
  is optional and `None` means "unchanged", which is why an explicit `[]` is a
  distinct, deliberate replacement. Entries change state only through an
  `EntryTransition` naming the entry, the action, and why; there is no delete.
* **Session evidence is provenance, not authority.** `SessionProvenance` records
  which harness wrote a revision. Nothing in this module selects on it.

All three persisted artifacts -- record, revision, projection -- carry their own
`schema_version`. A revision is immutable and its record is not, so a receipt
written under version N stays a version-N document however far the record it
describes has since moved; inheriting the stamp from the referencing record
would report the reader's vintage rather than the writer's.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Protocol, cast

from attrs import define, field, validators

# The central bounds. A Wheypoint record is written by an agent under context
# pressure, so "as much text as you like" is a denial-of-service on the next
# cold reader as much as on the store.
_MAX_TEXT = 2000
_MAX_ITEMS = 64
# A ledger is an aggregate over the three protected lists, not a peer of one of
# them: a receipt has to be able to name every entry a legal record can hold,
# and a delta may propose an addition of each kind.
_MAX_LEDGER = 3 * _MAX_ITEMS
_MAX_ID = 64
_ID_RE = re.compile(rf"[a-z0-9][a-z0-9._-]{{0,{_MAX_ID - 1}}}")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{7,64}")


class _NamedAttribute(Protocol):
    name: str


__all__ = [
    "ArtifactLink",
    "CompactionRecord",
    "DecisionFork",
    "DossierOption",
    "Durability",
    "EntryKind",
    "EntryState",
    "EntryTransition",
    "NextAction",
    "NextMove",
    "ProposedEntry",
    "ProtectedEntry",
    "RepositoryProvenance",
    "SessionProvenance",
    "TransitionAction",
    "WheypointDelta",
    "WheypointProjection",
    "WheypointRecord",
    "WheypointRevision",
    "WheypointStatus",
]


class WheypointStatus(str, Enum):
    """Derived, never stored: see the module docstring."""

    OK = "ok"
    GATED = "gated"


class NextMove(str, Enum):
    """What a cold reader should do next -- the `next:` vocabulary the
    /wheypoint handoff slug already publishes."""

    MOLD = "mold"
    CUT = "cut"
    COOK = "cook"
    PRESS = "press"
    AGE = "age"
    CURE = "cure"
    AFFINAGE = "affinage"
    BRIESEARCH = "briesearch"
    CULTURE = "culture"
    HOLD = "hold"
    TASKS = "tasks"
    DONE = "done"


class EntryKind(str, Enum):
    """What a protected entry is. Only a question or a blocker can gate."""

    DECISION = "decision"
    QUESTION = "question"
    BLOCKER = "blocker"


class EntryState(str, Enum):
    """Where an entry stands. There is no `deleted`: protected state leaves the
    record by transition, with a rationale, or not at all."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class TransitionAction(str, Enum):
    """The only ways a delta may move an entry out of `ACTIVE`."""

    RESOLVE = "resolve"
    SUPERSEDE = "supersede"
    WITHDRAW = "withdraw"


class Durability(str, Enum):
    """How far a projection has travelled. Reported, never acted on: nothing
    here commits or publishes."""

    CANONICAL_LOCAL = "canonical-local"
    REPO_SNAPSHOT = "repo-snapshot"
    PUBLISHED = "published"


_SETTLED = {EntryState.RESOLVED, EntryState.SUPERSEDED, EntryState.WITHDRAWN}
_TRANSITION_STATE = {
    TransitionAction.RESOLVE: EntryState.RESOLVED,
    TransitionAction.SUPERSEDE: EntryState.SUPERSEDED,
    TransitionAction.WITHDRAW: EntryState.WITHDRAWN,
}


def _bounded_text(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute.name} must be a non-empty string")
    if len(value) > _MAX_TEXT:
        raise ValueError(
            f"{attribute.name} must be at most {_MAX_TEXT} characters, not {len(value)}"
        )


def _bounded_text_list(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{attribute.name} must be a list")
    items = cast("list[object]", value)
    if len(items) > _MAX_ITEMS:
        raise ValueError(
            f"{attribute.name} must be at most {_MAX_ITEMS} items, not {len(items)}"
        )
    for index, item in enumerate(items, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{attribute.name}[{index}] must be a non-empty string")
        if len(item) > _MAX_TEXT:
            raise ValueError(
                f"{attribute.name}[{index}] must be at most {_MAX_TEXT} characters"
            )


def _identifier(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ValueError(
            f"{attribute.name} must be a lowercase identifier of at most "
            + f"{_MAX_ID} characters matching {_ID_RE.pattern}"
        )


def _each_identifier(attribute: _NamedAttribute, value: list[object]) -> None:
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or _ID_RE.fullmatch(item) is None:
            raise ValueError(
                f"{attribute.name}[{index}] must be a lowercase identifier "
                + f"matching {_ID_RE.pattern}"
            )


def _identifier_list(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    _bounded_list(instance, attribute, value)
    if isinstance(value, list):
        _each_identifier(attribute, cast("list[object]", value))


def _identifier_ledger(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    _bounded_ledger(instance, attribute, value)
    if isinstance(value, list):
        _each_identifier(attribute, cast("list[object]", value))


def _digest(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError(
            f"{attribute.name} must be sha256: followed by 64 lowercase "
            + "hexadecimal characters"
        )


def _commit(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise ValueError(
            f"{attribute.name} must be 7 to 64 lowercase hexadecimal characters"
        )


def _list_within(attribute: _NamedAttribute, value: object, limit: int) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{attribute.name} must be a list")
    items = cast("list[object]", value)
    if len(items) > limit:
        raise ValueError(
            f"{attribute.name} must be at most {limit} items, not {len(items)}"
        )


def _bounded_list(_instance: object, attribute: _NamedAttribute, value: object) -> None:
    _list_within(attribute, value, _MAX_ITEMS)


def _bounded_ledger(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    """For a list that aggregates the per-kind lists rather than mirroring one."""
    _list_within(attribute, value, _MAX_LEDGER)


def _non_empty_bounded_list(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    _bounded_list(instance, attribute, value)
    if not value:
        raise ValueError(f"{attribute.name} must be a non-empty list")


def _gates(entry: ProtectedEntry) -> bool:
    return entry.state is EntryState.ACTIVE and entry.blocks_continuation


def _derived_status(gating_entry_ids: Sequence[str]) -> WheypointStatus:
    """The one derivation, read by both the record and its projection."""
    return WheypointStatus.GATED if gating_entry_ids else WheypointStatus.OK


@define(frozen=True)
class DossierOption:
    """One option on an open fork: what it is, what pins it, what it costs."""

    option: str = field(validator=_bounded_text)
    evidence: list[str] = field(validator=_bounded_text_list)
    breaks: str = field(validator=_bounded_text)


@define(frozen=True)
class DecisionFork:
    """An open fork a resumed session has to re-weigh rather than re-derive."""

    fork: str = field(validator=_bounded_text)
    options: list[DossierOption] = field(validator=_non_empty_bounded_list)
    prior_leaning: str | None = field(
        default=None, validator=validators.optional(_bounded_text)
    )


@define(frozen=True)
class NextAction:
    """The desired next move plus the orientation a cold reader needs to take
    it. `artifact` points at the richer report the move should start from."""

    move: NextMove
    orientation: str = field(validator=_bounded_text)
    artifact: str | None = field(
        default=None, validator=validators.optional(_bounded_text)
    )


def _successor_rule(
    instance: ProtectedEntry, attribute: _NamedAttribute, value: object
) -> None:
    if instance.state is EntryState.SUPERSEDED and value is None:
        raise ValueError(f"{attribute.name} must name the entry that replaced this one")
    if instance.state is not EntryState.SUPERSEDED and value is not None:
        raise ValueError(
            f"{attribute.name} must be null unless the entry is superseded, "
            + f"not {value!r}"
        )
    if value is not None:
        _identifier(instance, attribute, value)


def _rationale_rule(
    instance: ProtectedEntry, attribute: _NamedAttribute, value: object
) -> None:
    if instance.state in _SETTLED and value is None:
        raise ValueError(
            f"{attribute.name} must say why the entry left {EntryState.ACTIVE.value}"
        )
    if value is not None:
        _bounded_text(instance, attribute, value)


def _gating_kind_rule(
    instance: ProtectedEntry | ProposedEntry,
    attribute: _NamedAttribute,
    value: object,
) -> None:
    if value and instance.kind is EntryKind.DECISION:
        raise ValueError(
            f"{attribute.name} must be false for a decision: only a question or "
            + "a blocker gates continuation"
        )


@define(frozen=True)
class ProtectedEntry:
    """A decision, question, or blocker the record carries forward until a
    transition moves it. `blocks_continuation` is what makes an open item a gate
    rather than a note."""

    entry_id: str = field(validator=_identifier)
    kind: EntryKind
    summary: str = field(validator=_bounded_text)
    state: EntryState
    blocks_continuation: bool = field(validator=_gating_kind_rule)
    rationale: str | None = field(default=None, validator=_rationale_rule)
    superseded_by: str | None = field(default=None, validator=_successor_rule)


@define(frozen=True)
class ProposedEntry:
    """A protected entry a delta asks for. It deliberately carries no
    `entry_id`: the runtime assigns one, so a delta cannot address -- and so
    cannot overwrite -- an entry that already exists."""

    kind: EntryKind
    summary: str = field(validator=_bounded_text)
    blocks_continuation: bool = field(default=False, validator=_gating_kind_rule)


def _target_rule(
    instance: EntryTransition, attribute: _NamedAttribute, value: object
) -> None:
    supersede = instance.action is TransitionAction.SUPERSEDE
    if supersede and value is None:
        raise ValueError(
            f"{attribute.name} must name the superseding entry for a "
            + f"{TransitionAction.SUPERSEDE.value} transition"
        )
    if not supersede and value is not None:
        raise ValueError(
            f"{attribute.name} must be null for a {instance.action.value} transition"
        )
    if value is not None:
        _identifier(instance, attribute, value)


@define(frozen=True)
class EntryTransition:
    """The only way protected state changes: an entry, what happens to it, and
    why. `TransitionAction` has no deletion member, so a delta can never make an
    entry disappear without a reason attached."""

    entry_id: str = field(validator=_identifier)
    action: TransitionAction
    rationale: str = field(validator=_bounded_text)
    target_entry_id: str | None = field(default=None, validator=_target_rule)

    @property
    def resulting_state(self) -> EntryState:
        return _TRANSITION_STATE[self.action]


@define(frozen=True)
class ArtifactLink:
    """A report the record leans on. A digest or a revision pins the version the
    coverage claim was made against; without one the claim cannot be revalidated
    later, which is why both are optional but recorded when known."""

    path: str = field(validator=_bounded_text)
    digest: str | None = field(default=None, validator=validators.optional(_digest))
    revision_id: str | None = field(
        default=None, validator=validators.optional(_identifier)
    )
    covers_entry_ids: list[str] = field(factory=list, validator=_identifier_list)


@define(frozen=True)
class SessionProvenance:
    """Which session wrote a revision. Evidence only -- no resolution, ordering,
    or authority decision in this kernel reads it."""

    harness: str | None = field(
        default=None, validator=validators.optional(_bounded_text)
    )
    session_id: str | None = field(
        default=None, validator=validators.optional(_identifier)
    )
    captured_at: str | None = field(
        default=None, validator=validators.optional(_bounded_text)
    )


@define(frozen=True)
class CompactionRecord:
    """What a session did to earn the right to write after a compaction.

    A compacted session has lost the context it was holding, so the revision it
    remembers is a guess. Naming the revision it re-read is not enough on its
    own -- an id can be copied out of a stale transcript -- so the record also
    quotes the *digest* of the record it re-read and lists the protected entries
    it reconciled against. Together those three are a reconciliation report: a
    claim that can only be made by a session that actually reloaded the durable
    state, and one a later reader can re-derive rather than take on faith.

    `prior_compaction_revision_id` chains one compaction to the one before it,
    so a lineage that survived several of them reads as a history rather than as
    a single most-recent event. It is *derived by the runtime*, never accepted
    from the delta: the compacted session is the one writer whose memory of the
    lineage is known to be unreliable, and letting it name its own predecessor
    would let it name none. `reconciliation_source_session_ids` is provenance in
    the sense the module docstring means -- it says which sessions the reconciled
    state was gathered from, and nothing selects on it.
    """

    rehydrated_from_revision_id: str = field(validator=_identifier)
    rehydrated_record_digest: str = field(validator=_digest)
    reconciled_entry_ids: list[str] = field(validator=_identifier_ledger)
    prior_compaction_revision_id: str | None = field(
        default=None, validator=validators.optional(_identifier)
    )
    reconciliation_source_session_ids: list[str] = field(
        factory=list, validator=_identifier_list
    )


@define(frozen=True)
class RepositoryProvenance:
    """Where the repository stood when a revision was written. Absent fields
    mean git could not be inspected, not that the work was clean."""

    branch: str | None = field(
        default=None, validator=validators.optional(_bounded_text)
    )
    commit: str | None = field(default=None, validator=validators.optional(_commit))


def _protected_entries(
    kind: EntryKind, *preceding: str
) -> Callable[[WheypointRecord, _NamedAttribute, list[ProtectedEntry]], None]:
    """The rules every protected list carries.

    Each list owns one kind, so a reader counting blockers never has to filter a
    mixed collection first. Entry IDs address protected state across all three
    lists, so a duplicate would make a transition ambiguous -- each list is
    checked against the lists declared before it, which puts the blame on the
    list the repeated id was actually found in.
    """

    def rule(
        instance: WheypointRecord,
        attribute: _NamedAttribute,
        value: list[ProtectedEntry],
    ) -> None:
        _bounded_list(instance, attribute, value)
        seen = {
            entry.entry_id
            for name in preceding
            for entry in cast("list[ProtectedEntry]", getattr(instance, name))
        }
        for entry in value:
            if entry.kind is not kind:
                raise ValueError(
                    f"{attribute.name} must contain only {kind.value} entries, "
                    + f"but {entry.entry_id!r} is a {entry.kind.value}"
                )
            if entry.entry_id in seen:
                raise ValueError(
                    f"{attribute.name} must not repeat an entry id already used "
                    + f"in this record: {entry.entry_id!r}"
                )
            seen.add(entry.entry_id)

    return rule


def _dossier_rule(
    attribute: _NamedAttribute, value: list[DecisionFork], gating: Sequence[str]
) -> None:
    """A dossier and a gate stand or fall together.

    A gated record without a dossier is one misfire this kernel exists to stop:
    the resumed session sees a gate and no way to weigh it. A dossier without a
    gate is the other, and the quieter one -- an open fork nobody has to answer
    derives `status: ok`, so the resumed session dispatches straight past the
    decision a human still owes. Closing a fork is a transition on the entry
    that gated it, so the two always empty together.
    """
    if gating and not value:
        raise ValueError(
            f"{attribute.name} must describe the open fork for gating entries "
            + f"{', '.join(gating)}"
        )
    if value and not gating:
        raise ValueError(
            f"{attribute.name} describes {len(value)} open fork(s) while nothing "
            + "blocks continuation: gate the fork with an active blocking "
            + "question or blocker, or clear the dossier"
        )


def _record_dossier(
    instance: WheypointRecord, attribute: _NamedAttribute, value: list[DecisionFork]
) -> None:
    _bounded_list(instance, attribute, value)
    _dossier_rule(attribute, value, instance.gating_entry_ids)


def _projection_dossier(
    instance: WheypointProjection,
    attribute: _NamedAttribute,
    value: list[DecisionFork],
) -> None:
    _bounded_list(instance, attribute, value)
    _dossier_rule(attribute, value, instance.gating_entry_ids)


@define(frozen=True)
class WheypointRecord:
    """The living authority for one unit of work: what it is, where it stands,
    and the protected state no narrowed update may quietly drop."""

    schema_version: int = field(validator=validators.ge(1))
    work_id: str = field(validator=_identifier)
    slug: str = field(validator=_identifier)
    title: str = field(validator=_bounded_text)
    created: str = field(validator=_bounded_text)
    # Produced by shared/scripts/paths.py::project_key; carried, not recomputed.
    project_key: str = field(validator=_bounded_text)
    revision_id: str = field(validator=_identifier)
    revision_number: int = field(validator=validators.ge(1))
    revision_digest: str = field(validator=_digest)
    orientation: str = field(validator=_bounded_text)
    working_context: list[str] = field(validator=_bounded_text_list)
    next_action: NextAction
    decisions: list[ProtectedEntry] = field(
        validator=_protected_entries(EntryKind.DECISION)
    )
    questions: list[ProtectedEntry] = field(
        validator=_protected_entries(EntryKind.QUESTION, "decisions")
    )
    blockers: list[ProtectedEntry] = field(
        validator=_protected_entries(EntryKind.BLOCKER, "decisions", "questions")
    )
    artifact_links: list[ArtifactLink] = field(validator=_bounded_list)
    decision_dossier: list[DecisionFork] = field(validator=_record_dossier)

    @property
    def gating_entry_ids(self) -> tuple[str, ...]:
        """The active, human-blocking questions and blockers, in record order."""
        return tuple(
            entry.entry_id
            for entry in (*self.questions, *self.blockers)
            if _gates(entry)
        )

    @property
    def status(self) -> WheypointStatus:
        return _derived_status(self.gating_entry_ids)


def _rehydration_rule(
    instance: WheypointDelta, attribute: _NamedAttribute, value: object
) -> None:
    if value is not None and not instance.compacted:
        raise ValueError(
            f"{attribute.name} must be null unless the delta declares compaction"
        )


def _one_transition_per_entry(
    _instance: object, attribute: _NamedAttribute, value: list[EntryTransition] | None
) -> None:
    if value is None:
        return
    _bounded_list(_instance, attribute, value)
    seen: set[str] = set()
    for transition in value:
        if transition.entry_id in seen:
            raise ValueError(
                f"{attribute.name} must transition each entry at most once, "
                + f"but {transition.entry_id!r} appears twice"
            )
        seen.add(transition.entry_id)


def _optional_bounded_list(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if value is not None:
        _bounded_list(instance, attribute, value)


def _optional_bounded_text_list(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    if value is not None:
        _bounded_text_list(instance, attribute, value)


@define(frozen=True)
class WheypointDelta:
    """One semantic update against an expected parent revision.

    Every field past the identity pair is optional and `None` means "leave this
    alone", so a narrowed update cannot delete protected state by forgetting it.
    An explicit `[]` is therefore a different request from an omitted field: it
    replaces the semantic context with nothing on purpose.
    """

    work_id: str = field(validator=_identifier)
    expected_revision_id: str = field(validator=_identifier)
    orientation: str | None = field(
        default=None, validator=validators.optional(_bounded_text)
    )
    working_context: list[str] | None = field(
        default=None, validator=_optional_bounded_text_list
    )
    next_action: NextAction | None = None
    decision_dossier: list[DecisionFork] | None = field(
        default=None, validator=_optional_bounded_list
    )
    add_decisions: list[ProposedEntry] | None = field(
        default=None, validator=_optional_bounded_list
    )
    add_questions: list[ProposedEntry] | None = field(
        default=None, validator=_optional_bounded_list
    )
    add_blockers: list[ProposedEntry] | None = field(
        default=None, validator=_optional_bounded_list
    )
    add_artifact_links: list[ArtifactLink] | None = field(
        default=None, validator=_optional_bounded_list
    )
    transitions: list[EntryTransition] | None = field(
        default=None, validator=_one_transition_per_entry
    )
    compacted: bool = field(default=False, validator=validators.instance_of(bool))
    # Declaring compaction is not the same as surviving it: the flag says the
    # harness detected one, the record is the evidence that durable state was
    # reloaded and reconciled first. The runtime refuses the flag without the
    # record, so a compacted session cannot write until it has rehydrated.
    compaction: CompactionRecord | None = field(
        default=None, validator=_rehydration_rule
    )
    session_provenance: SessionProvenance | None = None


@define(frozen=True)
class WheypointRevision:
    """The immutable receipt for one applied delta.

    It records what the request was (`request_digest`), what the record became
    (`record_digest`), what changed, and -- through `preserved_entry_ids` --
    what was carried forward untouched, so a later reader can prove nothing was
    dropped rather than take the resulting record on faith.
    """

    schema_version: int = field(validator=validators.ge(1))
    work_id: str = field(validator=_identifier)
    # Null exactly once, for the genesis revision.
    parent_revision_id: str | None = field(validator=validators.optional(_identifier))
    revision_id: str = field(validator=_identifier)
    revision_number: int = field(validator=validators.ge(1))
    request_digest: str = field(validator=_digest)
    record_digest: str = field(validator=_digest)
    applied_additions: list[ProtectedEntry] = field(validator=_bounded_ledger)
    applied_transitions: list[EntryTransition] = field(
        validator=_one_transition_per_entry
    )
    preserved_entry_ids: list[str] = field(validator=_identifier_ledger)
    projection_path: str = field(validator=_bounded_text)
    projection_digest: str = field(validator=_digest)
    repository: RepositoryProvenance
    compaction: CompactionRecord | None = None
    session_provenance: SessionProvenance | None = None


@define(frozen=True)
class WheypointProjection:
    """The generated Markdown view of a record, as data.

    It carries the gating entry IDs rather than a status, so `status` is a
    derivation here too: a producer cannot present an open gate as `ok` by
    writing the word.
    """

    schema_version: int = field(validator=validators.ge(1))
    work_id: str = field(validator=_identifier)
    revision_id: str = field(validator=_identifier)
    record_digest: str = field(validator=_digest)
    projection_digest: str = field(validator=_digest)
    next_action: NextAction
    gating_entry_ids: list[str] = field(validator=_identifier_ledger)
    decision_dossier: list[DecisionFork] = field(validator=_projection_dossier)
    durability: Durability = Durability.CANONICAL_LOCAL

    @property
    def status(self) -> WheypointStatus:
        return _derived_status(self.gating_entry_ids)
