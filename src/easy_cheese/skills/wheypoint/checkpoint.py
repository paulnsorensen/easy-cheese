"""Checkpoint authoring: a semantic intent, bound to the record it lands on.

`commit` is the kernel. It takes a delta that already names the revision it
expects and refuses anything else, and that strictness is the point -- it is
what makes a stale writer lose. But it also means a caller has to read the
record, copy a revision id out of it, and remember a sentinel for the case
where there is no record at all. None of that is a decision; all of it is
bookkeeping the runtime can do, and every step of it is a way to get an
otherwise-correct checkpoint refused.

This module does that bookkeeping and nothing else. It reads the record, binds
`expected_revision_id` to whatever is current (or `GENESIS_PARENT` when the
work has no record yet), assembles the `NextAction`, and hands the resulting
delta to `commit` unchanged. Every guarantee stays where it was:

* **A concurrent writer still loses.** The revision bound here is read outside
  the lock, so it is a guess by the time the delta is applied; `commit`
  re-checks it under the lock and raises `StaleParentError` when it has moved.
  Binding a parent is not the same as winning a race.
* **A caller that did read the state can still say so.** `base_revision_id` is
  optional, and when it is given it is bound *instead of* the current revision,
  which hands the caller the kernel's own rule verbatim: an exact resubmission
  replays into the receipt it already produced, and a changed request against a
  parent that has been superseded is refused as stale. Binding the current
  revision is the convenience; pinning a base is how a caller who did read the
  state keeps the answer it read from being silently written over.
* **Compaction still has to be proved.** A rehydration record is evidence that
  a compacted session reloaded durable state before writing, so filling one in
  from the store would make it evidence of nothing. The compaction fields are
  refused outright here and belong to `commit`.
* **Retirement still needs a reason.** Omission carries forward because the
  same kernel is underneath, and an entry leaves the record only through a
  caller-authored `EntryTransition` with a rationale.

The one clock read is deliberately conditional. `session_provenance` is inside
the request fingerprint, so stamping every checkpoint with the current time
would make every resubmission a different request and destroy the replay a
pinned base exists to make possible. The clock is read only where a timestamp
is *required* -- genesis, whose `captured_at` becomes the record's `created` --
or where the caller has already made the request session-specific by naming a
harness or a session id. An intent that names neither therefore resubmits
byte-identically; one that means to replay a genesis has to supply its own
`captured_at` alongside `base_revision_id: "genesis"`, because the clock would
otherwise move underneath it.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable, Mapping
from typing import cast

from attrs import Attribute, define, fields
from easy_cheese_schemas import (
    ArtifactLink,
    DecisionFork,
    EntryTransition,
    NextAction,
    NextMove,
    ProposedEntry,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)

from . import commit as commit_mod

# The shape `captured_at` already takes everywhere else in the record.
_TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"

# Delta fields a checkpoint intent may never carry. `expected_revision_id` is
# bound from the record here, and the compaction pair is a proof rather than a
# field: both belong to the low-level `commit` path.
COMMIT_ONLY_FIELDS = ("expected_revision_id", "compacted", "compaction")


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime(_TIMESTAMP)


class IntentError(ValueError):
    """The intent does not describe a checkpoint this record can take."""


@define(frozen=True)
class CheckpointIntent:
    """What a caller means by a checkpoint, with none of the bookkeeping.

    `next` is the bare move; the artifact it works on rides beside it rather
    than inside a `NextAction` the caller would otherwise have to assemble.
    `session` carries only what a harness knows about itself -- the timestamp
    is filled in by the rule in the module docstring.
    """

    work_id: str
    orientation: str | None = None
    working_context: list[str] | None = None
    next: NextMove | None = None
    artifact: str | None = None
    decision_dossier: list[DecisionFork] | None = None
    add_decisions: list[ProposedEntry] | None = None
    add_questions: list[ProposedEntry] | None = None
    add_blockers: list[ProposedEntry] | None = None
    add_artifact_links: list[ArtifactLink] | None = None
    transitions: list[EntryTransition] | None = None
    base_revision_id: str | None = None
    session: SessionProvenance | None = None


def commit_only_fields(payload: object) -> tuple[str, ...]:
    """The `commit`-only delta fields this payload tried to author.

    Unknown keys are ignored when the intent is structured, so a caller who
    reached for `compaction` would otherwise be told nothing and have their
    rehydration proof silently dropped.
    """
    if not isinstance(payload, Mapping):
        return ()
    mapping = cast(Mapping[str, object], payload)
    return tuple(name for name in COMMIT_ONLY_FIELDS if name in mapping)


# attrs' `fields()` is untyped, so the attributes are cast once here.
_INTENT_ATTRIBUTES = cast(
    "tuple[Attribute[object], ...]", fields(CheckpointIntent)
)
_INTENT_FIELD_NAMES: tuple[str, ...] = tuple(
    attribute.name for attribute in _INTENT_ATTRIBUTES
)


def unknown_fields(payload: object) -> tuple[str, ...]:
    """Every key the payload carries that `CheckpointIntent` cannot hold.

    The structure step ignores an unknown key, so an author who reaches for a
    field the record has no place for would otherwise be told nothing and lose
    it. `commit`-only fields are reported by `commit_only_fields`, which names
    the command that does author them.
    """
    if not isinstance(payload, Mapping):
        return ()
    mapping = cast(Mapping[str, object], payload)
    known = set(_INTENT_FIELD_NAMES) | set(COMMIT_ONLY_FIELDS)
    return tuple(sorted(name for name in mapping if name not in known))


def build_delta(
    intent: CheckpointIntent,
    current: WheypointRecord | None,
    *,
    now: Callable[[], str] | None = None,
) -> WheypointDelta:
    """The delta `commit` is given, bound to the record as it reads right now."""
    clock = _utc_now if now is None else now
    next_action = _next_action(intent, current)
    try:
        return WheypointDelta(
            work_id=intent.work_id,
            expected_revision_id=_parent(intent.base_revision_id, current),
            orientation=intent.orientation,
            working_context=intent.working_context,
            next_action=next_action,
            decision_dossier=intent.decision_dossier,
            add_decisions=intent.add_decisions,
            add_questions=intent.add_questions,
            add_blockers=intent.add_blockers,
            add_artifact_links=intent.add_artifact_links,
            transitions=intent.transitions,
            session_provenance=_provenance(
                intent, genesis=current is None, now=clock
            ),
        )
    except ValueError as exc:
        raise IntentError(
            f"the intent does not produce a legal delta: {exc}"
        ) from exc


def _parent(base: str | None, current: WheypointRecord | None) -> str:
    """The revision the delta declares, pinned by the caller or bound here.

    A pinned base is passed through untouched rather than compared here: the
    comparison that decides anything happens under the record lock, and making
    it twice would only mean answering it once in a place that cannot see a
    concurrent writer.
    """
    if base is not None:
        return base
    return commit_mod.GENESIS_PARENT if current is None else current.revision_id


def _next_action(
    intent: CheckpointIntent, current: WheypointRecord | None
) -> NextAction | None:
    """The next action, or None to carry the record's own forward.

    An omitted `next` is "unchanged", which is only a meaning an existing
    record has. `artifact` describes what the next move works on, so it is not
    a thing to set while leaving the move alone.
    """
    if intent.next is None:
        if current is None:
            raise IntentError(
                "a first checkpoint has no next action to carry forward, so it "
                + "must say what comes next"
            )
        if intent.artifact is not None:
            raise IntentError(
                "artifact belongs to the move it is worked on by, so it cannot "
                + "be set while next is omitted"
            )
        return None
    # The orientation the caller gave is what the whole checkpoint is about, so
    # it orients the next move too; without one, the record's standing
    # orientation for that move carries forward rather than being blanked.
    carried = "" if current is None else current.next_action.orientation
    try:
        return NextAction(
            move=intent.next,
            orientation=carried if intent.orientation is None else intent.orientation,
            artifact=intent.artifact,
        )
    except ValueError as exc:
        raise IntentError(f"the intent does not produce a legal next action: {exc}") from exc


def _provenance(
    intent: CheckpointIntent, *, genesis: bool, now: Callable[[], str]
) -> SessionProvenance | None:
    """Session provenance, with the clock read only where it has to be."""
    session = intent.session
    harness = None if session is None else session.harness
    session_id = None if session is None else session.session_id
    captured_at = None if session is None else session.captured_at
    if captured_at is None and (
        genesis or harness is not None or session_id is not None
    ):
        captured_at = now()
    if harness is None and session_id is None and captured_at is None:
        return None
    return SessionProvenance(
        harness=harness, session_id=session_id, captured_at=captured_at
    )
