"""Wheypoint schema objects as canonical payloads, digests, and claims.

This module is the seam between the frozen `easy_cheese_schemas` types and the
bytes on disk. Three things live here because they belong to the record rather
than to whoever is holding it:

* **The digests.** `record_digest` deliberately excludes `revision_digest`:
  the record points at the receipt that quotes the record back, and one of the
  two pointers has to stay outside the other's hash or neither can be computed.
  Excluding it loses nothing -- a forged `revision_digest` names a receipt that
  either does not exist or does not quote this record, which storage recovery
  checks in both directions.
* **Coverage claims.** An artifact may claim to cover protected entries, but a
  claim is only worth as much as the pin behind it. An unpinned, missing, stale,
  or entry-inventing claim is *reported*; the inline entries it claimed to cover
  stay exactly where they are. Nothing in this module removes protected state.
* **Transition legality.** A transition may only move an entry that exists and
  is still active, and a supersede must name a successor that exists.
"""

from __future__ import annotations

from collections.abc import Callable, Container, Mapping, Sequence
from enum import Enum
from typing import Protocol, TypeVar, cast, runtime_checkable

import attrs
from attrs import define, field
from attrs import AttrsInstance
from easy_cheese_schemas import (
    ArtifactLink,
    EntryState,
    EntryTransition,
    ProtectedEntry,
    WheypointDelta,
    WheypointRecord,
    WheypointRevision,
    load,
)
from easy_cheese_schemas.compat import STAMP_KEY

from . import canonical, ref_grammar

T = TypeVar("T")

# The record's pointer at its own receipt: see the module docstring.
_RECEIPT_POINTER = "revision_digest"
# Records and receipts stamped below this version are digested from their raw
# parsed payload; the schema has dropped receipt fields since.
RAW_DIGEST_BELOW = 5


class RecordError(ValueError):
    """Raised when a payload is not the schema type it claims to be."""


def _serialize(_instance: object, _attribute: object, value: object) -> object:
    return cast(object, value.value) if isinstance(value, Enum) else value


# Fields added after schema_version 2 carry `metadata={"since": 3}` on the
# producer side (ADR wheypoint-ergonomics-004). They are omitted from canonical
# bytes while they hold their declared default, so a record or receipt written
# by the v2 runtime re-serializes byte-identically and keeps its digests. The
# rule is read from the field itself: a new field needs no entry here, and a
# field without the marker is never omitted.
_SINCE_KEY = "since"
# The permanent v2 digest floor: canonical bytes for a schema_version-2 record
# must never change, so a field is compat-additive only when declared after
# this floor. This is fixed by ADR wheypoint-ergonomics-004 and is NOT derived
# from `SCHEMA_VERSION`, which keeps advancing as the schema grows.
_DIGEST_COMPAT_FLOOR = 2


# `attrs.Factory` is a class at runtime, but the stub types it as a function
# returning `_T`, so `isinstance(default, attrs.Factory)` cannot type-check.
# A structural protocol over its two attributes is the narrowest honest check.
@runtime_checkable
class _Factory(Protocol):
    factory: Callable[[], object]
    takes_self: bool


def _added_after_compat(attribute: attrs.Attribute[object]) -> bool:
    metadata = attribute.metadata or {}
    since = metadata.get(_SINCE_KEY)
    return isinstance(since, int) and since > _DIGEST_COMPAT_FLOOR


def _is_declared_default(attribute: attrs.Attribute[object], value: object) -> bool:
    default = attribute.default
    if isinstance(default, _Factory):
        # takes_self=True factories derive from the instance under
        # construction, which is not available here; treat as never-default.
        return False if default.takes_self else value == default.factory()
    return value is default


def _omit_post_compat_defaults(attribute: attrs.Attribute[object], value: object) -> bool:
    return not (_added_after_compat(attribute) and _is_declared_default(attribute, value))


def unstructure(obj: AttrsInstance) -> dict[str, object]:
    """A schema instance as plain JSON data, enums flattened to their values.

    Fields marked `since: 3` are dropped while at their declared default.
    """
    return attrs.asdict(
        obj, recurse=True, value_serializer=_serialize, filter=_omit_post_compat_defaults
    )


def structure(payload: object, cls: type[T], *, forbid_unknown: bool = False) -> T:
    """Structure `payload` into `cls` or raise with everything that was wrong.

    `forbid_unknown` names every key `cls` cannot hold by its path; it is the
    rule on every write path (S6), never on a read.
    """
    loaded = load(
        cast(dict[str, object], payload), cls, strict=True, forbid_unknown=forbid_unknown
    )
    if loaded.value is None:
        detail = "; ".join(loaded.problems) or "payload is not readable"
        raise RecordError(f"{cls.__name__}: {detail}")
    return loaded.value


_KEPT_EDGE_KINDS = frozenset({"forked_from", "supersedes", "checkpoints"})
_REMOVED_ENTRY_KEYS = ("origin", "successor", "copies")


def _plain_entry(entry: object, *, blocker: bool = False) -> object:
    """A stored entry without the keys schema 5 dropped; a blocker becomes a question."""
    if not isinstance(entry, dict):
        return entry
    plain = {
        key: value
        for key, value in cast("dict[str, object]", entry).items()
        if key not in _REMOVED_ENTRY_KEYS
    }
    if blocker:
        plain["kind"] = "question"
    return plain


def _entry_list(value: object) -> list[object]:
    return list(cast("list[object]", value)) if isinstance(value, list) else []


def _kept_edges(value: object) -> object:
    if not isinstance(value, list):
        return value
    kept: list[object] = [
        edge
        for edge in cast("list[object]", value)
        if not isinstance(edge, dict)
        or cast("dict[str, object]", edge).get("kind") in _KEPT_EDGE_KINDS
    ]
    return kept


def normalize_stored(payload: object) -> object:
    """A pre-v5 stored payload shaped for the v5 types; the input is untouched.

    Drops the keys schema 5 removed (dossier, entry lineage, edges of removed
    kinds) and turns each blocker into a question with the same id, summary, and
    stored blocks_continuation. Reads only: nothing here is written back, and the agreement checks
    hash the raw payload before this runs. A v5 payload passes through.
    """
    if not isinstance(payload, dict):
        return payload
    stored = cast("dict[str, object]", payload)
    if not _hashed_raw(stored):
        return stored
    out = dict(stored)
    _ = out.pop("decision_dossier", None)
    blockers = _entry_list(out.pop("blockers", None))
    if "questions" in out or blockers:
        out["questions"] = [
            *(_plain_entry(entry) for entry in _entry_list(out.get("questions"))),
            *(_plain_entry(entry, blocker=True) for entry in blockers),
        ]
    for name in ("decisions", "directives"):
        if name in out:
            out[name] = [_plain_entry(entry) for entry in _entry_list(out[name])]
    if "applied_additions" in out:
        out["applied_additions"] = [
            _plain_entry(
                entry,
                blocker=isinstance(entry, dict)
                and cast("dict[str, object]", entry).get("kind") == "blocker",
            )
            for entry in _entry_list(out["applied_additions"])
        ]
    for name in ("edges", "applied_edges", "removed_edges"):
        if name in out:
            out[name] = _kept_edges(out[name])
    return out


def structure_stored(payload: object, cls: type[T]) -> T:
    """`structure` for a payload read from disk, normalizing a pre-v5 stamp."""
    return structure(normalize_stored(payload), cls)


def canonical_payload(obj: AttrsInstance) -> bytes:
    """The exact bytes a schema instance is stored and hashed as."""
    return canonical.canonical_bytes(unstructure(obj))


def record_digest(record: WheypointRecord) -> str:
    payload = unstructure(record)
    _ = payload.pop(_RECEIPT_POINTER)
    return canonical.digest_value(payload)


def revision_digest(revision: AttrsInstance) -> str:
    return canonical.digest_value(unstructure(revision))


def _hashed_raw(payload: Mapping[str, object]) -> bool:
    """Whether a stored payload's digest is taken over its raw parsed bytes."""
    stamp = payload.get(STAMP_KEY)
    return isinstance(stamp, int) and stamp < RAW_DIGEST_BELOW


def stored_record_digest(payload: Mapping[str, object], record: WheypointRecord) -> str:
    """The `record_digest` a stored record's writer hashed.

    A record stamped below 5 is hashed from its raw parsed payload, minus the
    receipt pointer, before any normalization: a later schema must not make an
    older store look inconsistent. A v5 record re-serializes to its own bytes.
    """
    if not _hashed_raw(payload):
        return record_digest(record)
    return canonical.digest_value(
        {key: value for key, value in payload.items() if key != _RECEIPT_POINTER}
    )


def stored_revision_digest(
    payload: Mapping[str, object], revision: WheypointRevision
) -> str:
    """The `revision_digest` a stored receipt's writer hashed; see above."""
    if not _hashed_raw(payload):
        return revision_digest(revision)
    return canonical.digest_value(dict(payload))

def request_fingerprint(delta: WheypointDelta) -> str:
    """Identity of one request, so an identical replay is recognisable.

    Omitted and explicitly-emptied fields encode differently, so "leave this
    alone" and "replace this with nothing" are different requests.
    """
    return canonical.digest_value(unstructure(delta))


def entries(record: WheypointRecord) -> tuple[ProtectedEntry, ...]:
    """Every protected entry: decisions, questions, then directives."""
    return (*record.decisions, *record.questions, *record.directives)


def find_entry(record: WheypointRecord, entry_id: str) -> ProtectedEntry | None:
    for entry in entries(record):
        if entry.entry_id == entry_id:
            return entry
    return None


def validate_transitions(
    record: WheypointRecord,
    transitions: Sequence[EntryTransition],
    *,
    added_ids: Container[str] = (),
) -> tuple[str, ...]:
    """Everything that stops these transitions from applying to this record.

    A supersede may name an entry the same delta adds (`added_ids`).
    """
    problems: list[str] = []
    moved_ids = {transition.entry_id for transition in transitions}
    for transition in transitions:
        entry = find_entry(record, transition.entry_id)
        if entry is None:
            problems.append(f"transition names unknown entry {transition.entry_id!r}")
            continue
        if entry.state is not EntryState.ACTIVE:
            problems.append(f"entry {entry.entry_id!r} is already {entry.state.value}")
            continue
        target = transition.target_entry_id
        if target is None:
            continue
        if target == transition.entry_id:
            problems.append(f"entry {target!r} cannot supersede itself")
            continue
        successor = find_entry(record, target)
        if successor is None and target not in added_ids:
            problems.append(f"transition targets unknown entry {target!r}")
        elif successor is not None and successor.state is not EntryState.ACTIVE:
            problems.append(
                f"transition targets {target!r}, which is already {successor.state.value}"
            )
        elif target in moved_ids:
            problems.append(
                f"transition targets {target!r}, which this delta also transitions"
            )
    return tuple(problems)


def effective_ref(link: ArtifactLink) -> str:
    """The reference a link names: its `ref`, else `repo:` over its `path`."""
    return link.ref if link.ref is not None else f"repo:{link.path}"



@define(frozen=True)
class CoverageFailure:
    """One artifact whose coverage claim cannot be trusted, and why."""

    path: str
    reason: str


@define(frozen=True)
class CoverageReport:
    """Which claims held. Protected entries are never touched either way."""

    covered_entry_ids: tuple[str, ...] = field(default=())
    failures: tuple[CoverageFailure, ...] = field(default=())

    @property
    def valid(self) -> bool:
        return not self.failures


def coverage_report(
    record: WheypointRecord,
    *,
    artifact_digest: Callable[[str], str | None],
    ancestor_revision_ids: Container[str],
) -> CoverageReport:
    """Re-check every coverage claim the record's artifact links make.

    `artifact_digest` returns the artifact's current digest or None when it is
    gone; `ancestor_revision_ids` holds the revisions this record descends
    from. Ancestry, not mere existence, is what a revision pin has to resolve
    against: an abandoned sibling is still a file on disk, and a claim pinned
    to one describes work this record never took. A claim survives only if it
    is pinned, the artifact is still there, and the pin still resolves.
    """
    known_entry_ids = {entry.entry_id for entry in entries(record)}
    covered: list[str] = []
    failures: list[CoverageFailure] = []

    for link in record.artifact_links:
        if not link.covers_entry_ids:
            continue
        unknown = [id_ for id_ in link.covers_entry_ids if id_ not in known_entry_ids]
        if unknown:
            failures.append(
                CoverageFailure(
                    path=link.path,
                    reason=f"coverage names unknown entry {unknown[0]!r}",
                )
            )
            continue
        reason = _pin_failure(link, artifact_digest, ancestor_revision_ids)
        if reason is not None:
            failures.append(CoverageFailure(path=link.path, reason=reason))
            continue
        covered.extend(link.covers_entry_ids)

    return CoverageReport(tuple(covered), tuple(failures))


def _pin_failure(
    link: ArtifactLink,
    artifact_digest: Callable[[str], str | None],
    ancestor_revision_ids: Container[str],
) -> str | None:
    ref = effective_ref(link)
    try:
        scheme = ref_grammar.parse_ref(ref).scheme
    except ValueError as exc:
        return str(exc)
    if not ref_grammar.is_pinnable(scheme):
        return "unpinnable-scheme"
    if link.digest is None and link.revision_id is None:
        return "coverage claim has neither a digest nor a revision to pin it"
    # Existence first: every pin says what the file was, which a deleted file
    # cannot be either way. Then each pin the claim supplies is checked, so a
    # matching digest cannot carry an unresolvable revision past the gate.
    current = artifact_digest(ref)
    if current is None:
        return "artifact is missing"
    if link.digest is not None and current != link.digest:
        return "artifact digest mismatch"
    if link.revision_id is not None and link.revision_id not in ancestor_revision_ids:
        return f"coverage pins unknown revision {link.revision_id!r}"
    return None
