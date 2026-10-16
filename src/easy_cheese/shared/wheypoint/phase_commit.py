"""Commit a chain-phase handoff into the shared wheypoint store.

`commit_phase_revision` owns the whole phase write: it validates the grounded
manifest, reads the current record, refuses an ungrounded genesis write,
collects optional session provenance, writes the artifact through the caller's
`write_contents` callback, and only then commits. The artifact lands *before*
the commit deliberately -- an artifact on disk without a revision is visible to
the next resolve, which gates on `stale-artifact-link`, while a revision that
pins an artifact nobody wrote is a lie no reader can detect.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from attrs import define

from easy_cheese_schemas.contracts import (
    LOWER_IDENTIFIER_RE,
    ArtifactLink,
    CheckpointIntent,
    NextMove,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import checkpoint, commit, storage
from easy_cheese.shared.wheypoint.grounded import (
    GroundedEntryError,
    validate_grounded,
)


class PhaseCommitRefusal(Exception):
    """Caller usage this phase write refuses with nothing on disk.

    Every pre-write refusal -- a bad work id, an unusable `--grounded` entry, a
    field the record schema will not hold, a genesis without grounding --
    reaches the caller as this one type, so the adapter needs no knowledge of
    the kernel's own exception hierarchy.
    """


class ArtifactOrphaned(Exception):
    """The artifact landed on disk but its revision did not.

    Raised for anything that fails after `write_contents()` returned. `expected`
    says whether the underlying failure is one the kernel raises on purpose, so
    a caller prints a stack only for the ones that carry no message of their own.
    """

    cause: BaseException
    path: Path
    expected: bool

    def __init__(self, cause: BaseException, path: Path, *, expected: bool) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.cause = cause
        self.path = path
        self.expected = expected


@define(frozen=True)
class CommitOutcome:
    """A phase commit's result."""

    result: commit.CommitResult


def _warn(text: str) -> None:
    print(f"wheypoint: {text}", file=sys.stderr)


def _orphan(exc: Exception, path: Path) -> ArtifactOrphaned:
    """Classify a post-write failure; only a deliberate refusal is expected."""
    return ArtifactOrphaned(
        exc,
        path,
        expected=isinstance(
            exc, (PhaseCommitRefusal, commit.CommitError, storage.StorageError)
        ),
    )


def _is_identifier(value: str) -> bool:
    return LOWER_IDENTIFIER_RE.fullmatch(value) is not None


def _is_timestamp(value: str) -> bool:
    try:
        _ = _dt.datetime.strptime(value, checkpoint.TIMESTAMP_FORMAT)
    except ValueError:
        return False
    return True


def _is_single_line(value: str) -> bool:
    return "\n" not in value and "\r" not in value


# A writer normally runs with no session metadata. These names are deliberately
# optional and harness-agnostic: the checkpoint kernel supplies the genesis
# timestamp when absent. Each field carries the predicate its value must pass,
# so an unparseable primary falls through to its alias instead of shadowing it.
_SESSION_ENV: dict[str, tuple[tuple[str, ...], Callable[[str], bool], str]] = {
    "harness": (
        ("EASY_CHEESE_HARNESS", "CHEESE_HARNESS"),
        _is_single_line,
        "not a single line",
    ),
    "session_id": (
        ("EASY_CHEESE_SESSION_ID", "CHEESE_SESSION_ID"),
        _is_identifier,
        "not a lowercase identifier",
    ),
    "captured_at": (
        ("EASY_CHEESE_CAPTURED_AT", "CHEESE_CAPTURED_AT"),
        _is_timestamp,
        f"not a {checkpoint.TIMESTAMP_FORMAT} timestamp",
    ),
}


def _env_value(
    names: tuple[str, ...], *, valid: Callable[[str], bool], requirement: str
) -> tuple[str, str] | None:
    """First alias whose value the schema accepts; warn only when none does."""
    present = [
        (name, value) for name in names if (value := os.environ.get(name, "").strip())
    ]
    for name, value in present:
        if valid(value):
            return name, value
    for name, _value in present:
        _warn(f"ignoring {name}: {requirement}")
    return None


def _session_provenance_from_environment() -> SessionProvenance | None:
    """Build optional session provenance, dropping values the schema refuses.

    Session metadata is evidence, never authority, so a malformed value must
    not fail a write: each one is validated here, at the environment boundary,
    and dropped with one operator line naming the variable it came from.
    """
    sources: dict[str, str] = {}
    values: dict[str, str] = {}
    for field, (names, valid, requirement) in _SESSION_ENV.items():
        found = _env_value(names, valid=valid, requirement=requirement)
        if found is None:
            continue
        sources[field], values[field] = found
    if not values:
        return None
    try:
        return SessionProvenance(
            harness=values.get("harness"),
            session_id=values.get("session_id"),
            captured_at=values.get("captured_at"),
        )
    except ValueError as exc:
        named = ", ".join(sorted(sources.values()))
        _warn(f"ignoring session provenance from {named}: {exc}")
        return None


def _base_revision_id(current: WheypointRecord | None) -> str:
    return commit.GENESIS_PARENT if current is None else current.revision_id


def _require_read_base(
    current: WheypointRecord | None, base_revision_id: str | None
) -> None:
    """Refuse a phase write over an existing record the writer has not read.

    The writer names the revision it read; a missing or superseded base is
    refused before the artifact lands, because a retry that re-bound the
    parent would write over state the writer never re-read.
    """
    if current is None:
        if base_revision_id is not None:
            raise PhaseCommitRefusal(
                f"stale-parent: --base {base_revision_id!r} names a revision, but "
                + "no record exists: re-read the record, then write again"
            )
        return
    if base_revision_id is None:
        raise PhaseCommitRefusal(
            "base-revision-required: the record already exists, so pass the revision "
            + f"you read as --base; the current revision is {current.revision_id!r}: "
            + "re-read the record, then write again"
        )
    if base_revision_id != current.revision_id:
        raise PhaseCommitRefusal(
            f"stale-parent: --base {base_revision_id!r} is not the current revision "
            + f"{current.revision_id!r}: re-read the record, re-apply, then write again"
        )


def _require_genesis_grounding(
    current: WheypointRecord | None, grounded: Sequence[str]
) -> None:
    """Refuse a genesis phase write that carries no grounded manifest."""
    if current is None and not grounded:
        raise commit.CommitError(
            "a genesis phase write requires at least one --grounded entry"
        )


def _relative_artifact(artifact: str, *, root: Path) -> tuple[str, Path]:
    candidate = Path(artifact)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise commit.CommitError(
            f"artifact path is outside the repository root: {artifact!r}"
        ) from exc
    return relative.as_posix(), resolved


def _phase_links(*, root: Path, work_id: str, phase: str) -> list[ArtifactLink]:
    """Link only *this* phase's artifact.

    A sibling phase's link is carried forward by the commit kernel with the
    digest and revision its own phase pinned; re-adding it here would re-pin it
    to this revision and launder any drift since that phase committed.
    """
    found = paths.existing_artifacts(work_id, root=root / ".cheese", phases=(phase,))
    return [
        ArtifactLink(path=path.relative_to(root).as_posix()) for path in found.values()
    ]


def _build_delta(
    intent: CheckpointIntent, current: WheypointRecord | None
) -> WheypointDelta:
    try:
        return checkpoint.build_delta(intent, current)
    except checkpoint.IntentError as exc:
        raise commit.CommitError(str(exc)) from exc

def _require_kebab_work_id(work_id: str) -> None:
    """Refuse a work id no `.cheese/` reader can resolve, before any write.

    The record schema admits any lowercase identifier, but the artifact path
    this phase pins is resolved through `paths`, which admits only kebab-case.
    """
    problem = paths.validate_slug(work_id)
    if problem is not None:
        raise PhaseCommitRefusal(f"phase {problem}")


def _refuse_unbindable_intent(
    *,
    work_id: str,
    phase: str,
    next_skill: str,
    artifact_path: str,
    orientation: str,
    grounded: Sequence[str],
) -> None:
    """Run the record schema's own field validators before anything is written.

    The intent this phase commits is rebuilt after the artifact lands; bounding
    its fields here means an over-long orientation or an unknown next move is a
    refusal with nothing on disk instead of an orphaned artifact.
    """
    try:
        _ = CheckpointIntent(
            work_id=work_id,
            orientation=orientation,
            working_context=list(grounded) if grounded else None,
            notes=f"{phase} phase handoff",
            next=NextMove(next_skill),
            artifact=artifact_path,
        )
    except ValueError as exc:
        raise PhaseCommitRefusal(str(exc)) from exc


def _phase_intent(
    *,
    work_id: str,
    phase: str,
    next_skill: str,
    artifact_path: str,
    orientation: str,
    grounded: Sequence[str],
    links: list[ArtifactLink],
    parent: str,
    genesis: bool,
    session: SessionProvenance | None,
) -> CheckpointIntent:
    return CheckpointIntent(
        work_id=work_id,
        orientation=orientation,
        working_context=list(grounded) if grounded else None,
        notes=f"{phase} phase handoff" if genesis else None,
        next=NextMove(next_skill),
        artifact=artifact_path,
        artifact_links=links,
        base_revision_id=parent,
        session=session,
    )


def _is_lost_response_retry(
    *,
    work_id: str,
    phase: str,
    next_skill: str,
    artifact_path: str,
    orientation: str,
    grounded: Sequence[str],
    current: WheypointRecord | None,
    base_revision_id: str | None,
    contents_digest: str | None,
    session: SessionProvenance | None,
    store: storage.WorkStore,
    root_path: Path,
) -> bool:
    """Whether a stale base is this same write retried after its response was lost.

    The kernel already holds a receipt for the identical request against the
    caller's base, and the record still pins this artifact to that receipt with
    the bytes this call writes. Any other stale base stays a refusal.
    """
    if current is None or base_revision_id is None or contents_digest is None:
        return False
    if base_revision_id == current.revision_id:
        return False
    intent = _phase_intent(
        work_id=work_id,
        phase=phase,
        next_skill=next_skill,
        artifact_path=artifact_path,
        orientation=orientation,
        grounded=grounded,
        links=_phase_links(root=root_path, work_id=work_id, phase=phase),
        parent=base_revision_id,
        genesis=False,
        session=session,
    )
    replay = commit.find_replay(store, _build_delta(intent, current))
    if replay is None:
        return False
    return any(
        link.path == artifact_path
        and link.revision_id == replay.revision_id
        and link.digest == contents_digest
        for link in current.artifact_links
    )


def _commit_written(
    *,
    work_id: str,
    phase: str,
    next_skill: str,
    artifact_path: str,
    orientation: str,
    grounded: Sequence[str],
    current: WheypointRecord | None,
    parent: str,
    session: SessionProvenance | None,
    store: storage.WorkStore,
    root_path: Path,
) -> CommitOutcome:
    """Link the artifact that just landed and commit its revision."""
    links = _phase_links(root=root_path, work_id=work_id, phase=phase)
    if not any(link.path == artifact_path for link in links):
        raise commit.CommitError(
            f"the written phase artifact is not present: {artifact_path!r}"
        )
    intent = _phase_intent(
        work_id=work_id,
        phase=phase,
        next_skill=next_skill,
        artifact_path=artifact_path,
        orientation=orientation,
        grounded=grounded,
        links=links,
        parent=parent,
        genesis=current is None,
        session=session,
    )
    delta = _build_delta(intent, current)
    return CommitOutcome(
        result=commit.commit(delta, store=store, artifact_root=root_path)
    )


def commit_phase_revision(
    *,
    work_id: str,
    phase: str,
    next_skill: str,
    artifact: str,
    orientation: str,
    grounded: Sequence[str],
    store: storage.WorkStore,
    write_contents: Callable[[], None],
    root: Path | str | None = None,
    provenance: SessionProvenance | None = None,
    base_revision_id: str | None = None,
    contents_digest: str | None = None,
) -> CommitOutcome:
    """Validate, write the artifact, then commit one chain-phase revision.

    Failure classification belongs to this producer, not its caller: everything
    before `write_contents()` raises `PhaseCommitRefusal` (caller usage, nothing
    on disk) or the kernel's own error for an environment failure, and anything
    after it raises `ArtifactOrphaned`. An existing record needs the revision
    the writer read as `base_revision_id`; a missing or stale base is a
    refusal, and a conflict under the lock is not retried.

    `contents_digest` is the digest of the bytes `write_contents()` writes. With
    it, a stale base that is this same write retried after a lost response
    returns the original revision as a replay instead of `stale-parent`.
    """
    try:
        root_path = paths.resolve_repo_root(root)
        artifact_path, artifact_target = _relative_artifact(artifact, root=root_path)
        _require_kebab_work_id(work_id)
        grounded_entries = validate_grounded(grounded, root=root_path)
        _refuse_unbindable_intent(
            work_id=work_id,
            phase=phase,
            next_skill=next_skill,
            artifact_path=artifact_path,
            orientation=orientation,
            grounded=grounded_entries,
        )
        session = (
            provenance
            if provenance is not None
            else _session_provenance_from_environment()
        )
        current = store.read_record()
        retry = _is_lost_response_retry(
            work_id=work_id,
            phase=phase,
            next_skill=next_skill,
            artifact_path=artifact_path,
            orientation=orientation,
            grounded=grounded_entries,
            current=current,
            base_revision_id=base_revision_id,
            contents_digest=contents_digest,
            session=session,
            store=store,
            root_path=root_path,
        )
        if not retry:
            _require_read_base(current, base_revision_id)
        _require_genesis_grounding(current, grounded_entries)
    except (commit.CommitError, GroundedEntryError) as exc:
        raise PhaseCommitRefusal(str(exc)) from exc

    write_contents()

    try:
        return _commit_written(
            work_id=work_id,
            phase=phase,
            next_skill=next_skill,
            artifact_path=artifact_path,
            orientation=orientation,
            grounded=grounded_entries,
            current=current,
            parent=_base_revision_id(current) if base_revision_id is None else base_revision_id,
            session=session,
            store=store,
            root_path=root_path,
        )
    except Exception as exc:
        raise _orphan(exc, artifact_target) from exc

__all__ = [
    "ArtifactOrphaned",
    "CommitOutcome",
    "PhaseCommitRefusal",
    "commit_phase_revision",
]
