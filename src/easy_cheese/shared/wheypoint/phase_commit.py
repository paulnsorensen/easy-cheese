"""Commit a chain-phase handoff into the shared wheypoint store."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from attrs import define, evolve

from easy_cheese_schemas.contracts import (
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
    MAX_GROUNDED_ENTRIES,
    GroundedEntryError,
    parse_grounded_entry,
    validate_grounded,
)

_CURRENT_UNSET = object()

# A writer normally runs with no session metadata. These names are deliberately
# optional: the checkpoint kernel supplies the genesis timestamp when absent.
_SESSION_ENV = {
    "harness": ("EASY_CHEESE_HARNESS", "CHEESE_HARNESS"),
    "session_id": ("EASY_CHEESE_SESSION_ID", "CHEESE_SESSION_ID"),
    "captured_at": ("EASY_CHEESE_CAPTURED_AT", "CHEESE_CAPTURED_AT"),
}


@define(frozen=True)
class CommitOutcome:
    """A phase commit's result, plus whether the stale-parent retry fired."""

    result: commit.CommitResult
    retried: bool


def read_current_record(
    work_id: str,
    *,
    corpus_root: Path | str | None = None,
    store: storage.WorkStore | None = None,
) -> WheypointRecord | None:
    """Read the current record before a chain artifact is replaced."""
    opened = (
        store
        if store is not None
        else storage.WorkStore.open(work_id, corpus_root=corpus_root)
    )
    return opened.read_record()


def session_provenance_from_environment() -> SessionProvenance | None:
    """Build optional session provenance from harness-provided environment."""
    values: dict[str, str] = {}
    for field, names in _SESSION_ENV.items():
        for name in names:
            value = os.environ.get(name, "").strip()
            if value:
                values[field] = value
                break
    if not values:
        return None
    return SessionProvenance(
        harness=values.get("harness"),
        session_id=values.get("session_id"),
        captured_at=values.get("captured_at"),
    )


def _base_revision_id(current: WheypointRecord | None) -> str:
    return commit.GENESIS_PARENT if current is None else current.revision_id


def require_genesis_grounding(
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


def _phase_links(*, root: Path, work_id: str) -> list[ArtifactLink]:
    found = paths.existing_artifacts(
        work_id, root=root / ".cheese", phases=tuple(reversed(paths.CHAIN_PHASES))
    )
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


def commit_phase_revision(
    *,
    work_id: str,
    phase: str,
    next_skill: str,
    artifact: str,
    orientation: str,
    grounded: Sequence[str],
    provenance: SessionProvenance | None = None,
    root: Path | str | None = None,
    corpus_root: Path | str | None = None,
    current_record: WheypointRecord | None | object = _CURRENT_UNSET,
    store: storage.WorkStore | None = None,
) -> CommitOutcome:
    """Commit one chain-phase revision, retrying one stale-parent conflict."""
    root_path = paths.resolve_repo_root(root)
    artifact_path, _ = _relative_artifact(artifact, root=root_path)
    store = (
        store
        if store is not None
        else storage.WorkStore.open(work_id, corpus_root=corpus_root)
    )
    current = (
        store.read_record()
        if current_record is _CURRENT_UNSET
        else cast(WheypointRecord | None, current_record)
    )
    require_genesis_grounding(current, grounded)

    session = (
        provenance if provenance is not None else session_provenance_from_environment()
    )
    links = _phase_links(root=root_path, work_id=work_id)
    if not any(link.path == artifact_path for link in links):
        raise commit.CommitError(
            f"the written phase artifact is not present: {artifact_path!r}"
        )
    intent = CheckpointIntent(
        work_id=work_id,
        orientation=orientation,
        working_context=list(grounded) if grounded else None,
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
        refreshed = store.read_record()
        refreshed_base = _base_revision_id(refreshed)
        print(
            f"wheypoint: stale parent conflict; retrying against revision {refreshed_base}",
            file=sys.stderr,
        )
        retry_links = _phase_links(root=root_path, work_id=work_id)
        retry_intent = _retry_intent(
            intent,
            base_revision_id=refreshed_base,
            grounded=grounded,
            artifact_links=retry_links,
            current=refreshed,
        )
        retry_delta = _build_delta(retry_intent, refreshed)
        return CommitOutcome(
            result=commit.commit(retry_delta, store=store, artifact_root=root_path),
            retried=True,
        )


__all__ = [
    "CommitOutcome",
    "GroundedEntryError",
    "MAX_GROUNDED_ENTRIES",
    "commit_phase_revision",
    "parse_grounded_entry",
    "read_current_record",
    "require_genesis_grounding",
    "session_provenance_from_environment",
    "validate_grounded",
]
