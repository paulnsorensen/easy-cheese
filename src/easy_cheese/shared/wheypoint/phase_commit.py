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

from attrs import define, evolve

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
from easy_cheese.shared.wheypoint.grounded import validate_grounded

# Exit codes a caller branches on. Plain integers, identical on every host: a
# chain driver distinguishes "nothing was written" from "the artifact is on disk
# without a revision" without parsing prose.
EXIT_WHEYPOINT = 4
EXIT_ARTIFACT_ORPHANED = 5

# A writer normally runs with no session metadata. These names are deliberately
# optional and harness-agnostic: the checkpoint kernel supplies the genesis
# timestamp when absent.
_SESSION_ENV = {
    "harness": ("EASY_CHEESE_HARNESS", "CHEESE_HARNESS"),
    "session_id": ("EASY_CHEESE_SESSION_ID", "CHEESE_SESSION_ID"),
    "captured_at": ("EASY_CHEESE_CAPTURED_AT", "CHEESE_CAPTURED_AT"),
}
# The shape `captured_at` takes everywhere else in the record: the format the
# checkpoint kernel's own clock emits.
_CAPTURED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@define(frozen=True)
class CommitOutcome:
    """A phase commit's result, plus whether the stale-parent retry fired."""

    result: commit.CommitResult
    retried: bool


def _warn(text: str) -> None:
    print(f"wheypoint: {text}", file=sys.stderr)


def _env_value(names: tuple[str, ...]) -> tuple[str, str] | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return name, value
    return None


def _session_provenance_from_environment() -> SessionProvenance | None:
    """Build optional session provenance, dropping values the schema refuses.

    Session metadata is evidence, never authority, so a malformed value must
    not fail a write: each one is validated here, at the environment boundary,
    and dropped with one operator line when it does not parse.
    """
    values: dict[str, str] = {}
    for field, names in _SESSION_ENV.items():
        found = _env_value(names)
        if found is None:
            continue
        name, value = found
        if field == "session_id" and LOWER_IDENTIFIER_RE.fullmatch(value) is None:
            _warn(f"ignoring {name}: not a lowercase identifier")
            continue
        if field == "captured_at" and not _is_timestamp(value):
            _warn(f"ignoring {name}: not a {_CAPTURED_AT_FORMAT} timestamp")
            continue
        values[field] = value
    if not values:
        return None
    try:
        return SessionProvenance(
            harness=values.get("harness"),
            session_id=values.get("session_id"),
            captured_at=values.get("captured_at"),
        )
    except ValueError as exc:
        _warn(f"ignoring session provenance from the environment: {exc}")
        return None


def _is_timestamp(value: str) -> bool:
    try:
        _ = _dt.datetime.strptime(value, _CAPTURED_AT_FORMAT)
    except ValueError:
        return False
    return True


def _base_revision_id(current: WheypointRecord | None) -> str:
    return commit.GENESIS_PARENT if current is None else current.revision_id


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


def _retry_intent(
    intent: CheckpointIntent,
    *,
    base_revision_id: str,
    grounded: Sequence[str],
    artifact_links: list[ArtifactLink],
    current: WheypointRecord | None,
) -> CheckpointIntent:
    return evolve(
        intent,
        base_revision_id=base_revision_id,
        working_context=list(grounded) if grounded else None,
        notes=None if current is not None else intent.notes,
        artifact_links=artifact_links,
    )


def _retry(
    intent: CheckpointIntent,
    *,
    work_id: str,
    phase: str,
    grounded: Sequence[str],
    links: list[ArtifactLink],
    store: storage.WorkStore,
    root_path: Path,
) -> CommitOutcome:
    """Rebuild the intent against the record that landed first, and re-commit."""
    refreshed = store.read_record()
    refreshed_base = _base_revision_id(refreshed)
    _warn(
        f"retry work_id={work_id} phase={phase}"
        + f" stale_parent={intent.base_revision_id} refreshed_parent={refreshed_base}"
    )
    _require_genesis_grounding(refreshed, grounded)
    retry_delta = _build_delta(
        _retry_intent(
            intent,
            base_revision_id=refreshed_base,
            grounded=grounded,
            artifact_links=links,
            current=refreshed,
        ),
        refreshed,
    )
    try:
        result = commit.commit(retry_delta, store=store, artifact_root=root_path)
    except commit.CommitError as exc:
        _warn(f"retry outcome=failed work_id={work_id} phase={phase} error={exc}")
        raise
    _warn(
        f"retry outcome=committed work_id={work_id} phase={phase}"
        + f" revision_id={result.revision.revision_id}"
    )
    return CommitOutcome(result=result, retried=True)


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
) -> CommitOutcome:
    """Validate, write the artifact, then commit one chain-phase revision.

    Everything before `write_contents()` is a refusal the caller can still act
    on with nothing on disk; everything after it leaves the artifact written.
    One stale-parent conflict is retried against the record that landed first.
    """
    root_path = paths.resolve_repo_root(root)
    artifact_path, _ = _relative_artifact(artifact, root=root_path)
    grounded_entries = validate_grounded(grounded, root=root_path)
    current = store.read_record()
    _require_genesis_grounding(current, grounded_entries)
    session = (
        provenance if provenance is not None else _session_provenance_from_environment()
    )

    write_contents()

    links = _phase_links(root=root_path, work_id=work_id, phase=phase)
    if not any(link.path == artifact_path for link in links):
        raise commit.CommitError(
            f"the written phase artifact is not present: {artifact_path!r}"
        )
    intent = CheckpointIntent(
        work_id=work_id,
        orientation=orientation,
        working_context=list(grounded_entries) if grounded_entries else None,
        notes=None if current is not None else f"{phase} phase handoff",
        next=NextMove(next_skill),
        artifact=artifact_path,
        artifact_links=links,
        base_revision_id=_base_revision_id(current),
        session=session,
    )
    delta = _build_delta(intent, current)
    try:
        return CommitOutcome(
            result=commit.commit(delta, store=store, artifact_root=root_path),
            retried=False,
        )
    except (commit.StaleParentError, commit.GenesisConflictError):
        return _retry(
            intent,
            work_id=work_id,
            phase=phase,
            grounded=grounded_entries,
            links=links,
            store=store,
            root_path=root_path,
        )


__all__ = [
    "EXIT_ARTIFACT_ORPHANED",
    "EXIT_WHEYPOINT",
    "CommitOutcome",
    "commit_phase_revision",
]
