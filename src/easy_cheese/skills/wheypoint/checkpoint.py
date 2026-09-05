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
import re
from collections.abc import Callable, Mapping
from typing import cast

import attrs

from easy_cheese_schemas import (
    CheckpointIntent,
    NextAction,
    NextMove,
    ProposedEntry,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)

from easy_cheese.shared.handoff import PR_REFERENCE_RE, parse_skill_dispatch

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


__all__ = [
    "CheckpointIntent",
    "IntentError",
    "build_delta",
    "check_move_artifact",
    "commit_only_fields",
    "secret_field",
    "secret_fields",
    "task_command_problems",
]

# Moves whose artifact is not optional (the gates that used to be prose).
_ARTIFACT_REQUIRED = frozenset({NextMove.COOK, NextMove.CUT})

# A small, named set: a checkpoint is durable, digest-protected text, so a
# pasted credential can never be scrubbed later. Each pattern names what it is.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abps]-[A-Za-z0-9-]{10,}\b")),
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("JWT or bearer token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("URL with basic-auth credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
    (
        "credential assignment",
        re.compile(r"(?i)\b(?:api[_-]?key|password|passwd|secret[_-]?key|access[_-]?token)\s*[=:]\s*['\"]?[A-Za-z0-9_\-./+]{8,}"),
    ),
)


def _string_fields(value: object, path: str) -> list[tuple[str, str]]:
    """Every string in an unstructured intent, with the path that carries it."""
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, dict):
        out: list[tuple[str, str]] = []
        for key, item in cast(dict[str, object], value).items():
            out.extend(_string_fields(item, f"{path}.{key}" if path else key))
        return out
    if isinstance(value, list):
        out = []
        for index, item in enumerate(cast(list[object], value)):
            out.extend(_string_fields(item, f"{path}[{index}]"))
        return out
    return []


def secret_fields(intent: CheckpointIntent) -> list[str]:
    """Every text field of the intent that carries a secret pattern, named by path.

    Every string field is scanned -- task commands, dossier evidence, transition
    rationales, and artifact paths included -- because a checkpoint is durable,
    digest-protected text that can never be scrubbed afterwards (AC-20).
    """
    hits: list[str] = []
    for field_name, text in _string_fields(attrs.asdict(intent, recurse=True), ""):
        for label, pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{field_name} ({label})")
                break
    return hits


def secret_field(intent: CheckpointIntent) -> str | None:
    """The first secret-carrying field, or None (see `secret_fields`)."""
    hits = secret_fields(intent)
    return hits[0] if hits else None


def task_command_problems(intent: CheckpointIntent) -> list[str]:
    """Each `tasks[i].command` that is not a dispatchable skill invocation."""
    problems: list[str] = []
    for index, task in enumerate(intent.tasks or []):
        try:
            _ = parse_skill_dispatch(task.command)
        except ValueError as exc:
            problems.append(f"tasks[{index}].command is not a skill dispatch: {exc}")
    return problems


def commit_only_fields(payload: object) -> tuple[str, ...]:
    """The `commit`-only delta fields this payload tried to author.

    `expected_revision_id` is bound from the record, and the compaction pair is
    a proof that rides on `--compacted`; naming them here tells the author where
    they go instead of calling them unknown keys.
    """
    if not isinstance(payload, Mapping):
        return ()
    mapping = cast(Mapping[str, object], payload)
    return tuple(name for name in COMMIT_ONLY_FIELDS if name in mapping)


def build_delta(
    intent: CheckpointIntent,
    current: WheypointRecord | None,
    *,
    now: Callable[[], str] | None = None,
) -> WheypointDelta:
    """The delta `commit` is given, bound to the record as it reads right now."""
    clock = _utc_now if now is None else now
    command_problems = task_command_problems(intent)
    if command_problems:
        raise IntentError("; ".join(command_problems))
    next_action = _next_action(intent, current)
    grouped: dict[str, list[ProposedEntry]] = {}
    for entry in intent.entries or []:
        grouped.setdefault(commit_mod.ADDITION_FIELDS[entry.kind], []).append(entry)
    try:
        return WheypointDelta(
            work_id=intent.work_id,
            expected_revision_id=_parent(intent.base_revision_id, current),
            orientation=intent.orientation,
            working_context=intent.working_context,
            notes=intent.notes,
            next_action=next_action,
            decision_dossier=intent.decision_dossier,
            add_decisions=grouped.get("add_decisions"),
            add_questions=grouped.get("add_questions"),
            add_blockers=grouped.get("add_blockers"),
            add_directives=grouped.get("add_directives"),
            add_artifact_links=intent.artifact_links,
            remove_artifact_links=intent.remove_artifact_links,
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
    check_move_artifact(intent.next, intent.artifact)
    try:
        return NextAction(
            move=intent.next,
            orientation=carried if intent.orientation is None else intent.orientation,
            artifact=intent.artifact,
            tasks=intent.tasks,
            parallel=intent.parallel,
        )
    except ValueError as exc:
        raise IntentError(f"the intent does not produce a legal next action: {exc}") from exc


def check_move_artifact(move: NextMove, artifact: str | None) -> None:
    """The next/artifact coherence gate that used to be SKILL.md prose (AC-19)."""
    if move is NextMove.AFFINAGE:
        if artifact is None or not PR_REFERENCE_RE.search(artifact):
            raise IntentError(
                "artifact must name the pull request (PR#<n> or its GitHub URL) "
                + "when next is 'affinage', so the resume dispatches it explicitly"
            )
    elif move in _ARTIFACT_REQUIRED and artifact is None:
        raise IntentError(
            f"artifact is required when next is {move.value!r}: the phase needs "
            + "an existing spec or receipt to start from"
        )


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
