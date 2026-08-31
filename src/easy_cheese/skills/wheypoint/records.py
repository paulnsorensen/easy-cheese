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

from collections.abc import Callable, Container, Sequence
from enum import Enum
from typing import TypeVar, cast

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
    load,
)

from . import canonical

T = TypeVar("T")

# The record's pointer at its own receipt: see the module docstring.
_RECEIPT_POINTER = "revision_digest"


class RecordError(ValueError):
    """Raised when a payload is not the schema type it claims to be."""


def _serialize(_instance: object, _attribute: object, value: object) -> object:
    return cast(object, value.value) if isinstance(value, Enum) else value


def unstructure(obj: AttrsInstance) -> dict[str, object]:
    """A schema instance as plain JSON data, enums flattened to their values."""
    return attrs.asdict(obj, recurse=True, value_serializer=_serialize)


def structure(payload: object, cls: type[T]) -> T:
    """Structure `payload` into `cls` or raise with everything that was wrong."""
    loaded = load(cast(dict[str, object], payload), cls, strict=True)
    if loaded.value is None:
        detail = "; ".join(loaded.problems) or "payload is not readable"
        raise RecordError(f"{cls.__name__}: {detail}")
    return loaded.value


def canonical_payload(obj: AttrsInstance) -> bytes:
    """The exact bytes a schema instance is stored and hashed as."""
    return canonical.canonical_bytes(unstructure(obj))


def record_digest(record: WheypointRecord) -> str:
    payload = unstructure(record)
    _ = payload.pop(_RECEIPT_POINTER)
    return canonical.digest_value(payload)


def revision_digest(revision: AttrsInstance) -> str:
    return canonical.digest_value(unstructure(revision))


def request_fingerprint(delta: WheypointDelta) -> str:
    """Identity of one request, so an identical replay is recognisable.

    Omitted and explicitly-emptied fields encode differently, so "leave this
    alone" and "replace this with nothing" are different requests.
    """
    return canonical.digest_value(unstructure(delta))


def entries(record: WheypointRecord) -> tuple[ProtectedEntry, ...]:
    """Every protected entry, decisions then questions then blockers."""
    return (*record.decisions, *record.questions, *record.blockers)


def find_entry(record: WheypointRecord, entry_id: str) -> ProtectedEntry | None:
    for entry in entries(record):
        if entry.entry_id == entry_id:
            return entry
    return None


def validate_transitions(
    record: WheypointRecord, transitions: Sequence[EntryTransition]
) -> tuple[str, ...]:
    """Everything that stops these transitions from applying to this record."""
    problems: list[str] = []
    for transition in transitions:
        entry = find_entry(record, transition.entry_id)
        if entry is None:
            problems.append(
                f"transition names unknown entry {transition.entry_id!r}"
            )
            continue
        if entry.state is not EntryState.ACTIVE:
            problems.append(
                f"entry {entry.entry_id!r} is already {entry.state.value}"
            )
            continue
        target = transition.target_entry_id
        if target is not None and find_entry(record, target) is None:
            problems.append(f"transition targets unknown entry {target!r}")
    return tuple(problems)


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
    if link.digest is not None:
        current = artifact_digest(link.path)
        if current is None:
            return "artifact is missing"
        if current != link.digest:
            return "artifact digest mismatch"
        return None
    if link.revision_id is not None:
        # Existence first: a revision pin says "this file was what it was at
        # that revision", which a deleted file cannot be either way.
        if artifact_digest(link.path) is None:
            return "artifact is missing"
        if link.revision_id not in ancestor_revision_ids:
            return f"coverage pins unknown revision {link.revision_id!r}"
        return None
    return "coverage claim has neither a digest nor a revision to pin it"
