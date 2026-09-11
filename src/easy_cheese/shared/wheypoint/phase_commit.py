"""Commit a chain-phase handoff into the shared wheypoint store."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

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

MAX_GROUNDED_ENTRIES = 16
_GROUNDED_RE = re.compile(
    r"^(?P<path>[^#]+?)(?:#(?P<start>[1-9][0-9]*)-(?P<end>[1-9][0-9]*))?$"
)
_CURRENT_UNSET = object()

# A writer normally runs with no session metadata. These names are deliberately
# optional: the checkpoint kernel supplies the genesis timestamp when absent.
_SESSION_ENV = {
    "harness": ("EASY_CHEESE_HARNESS", "CHEESE_HARNESS"),
    "session_id": ("EASY_CHEESE_SESSION_ID", "CHEESE_SESSION_ID"),
    "captured_at": ("EASY_CHEESE_CAPTURED_AT", "CHEESE_CAPTURED_AT"),
}

CommitOutcome = commit.CommitResult


class GroundedEntryError(ValueError):
    """A --grounded entry does not satisfy the path-and-range contract."""


def validate_grounded(entries: Sequence[str], *, root: Path | str) -> tuple[str, ...]:
    """Validate and preserve the grounded manifest exactly as supplied."""
    if len(entries) > MAX_GROUNDED_ENTRIES:
        raise GroundedEntryError(
            f"--grounded accepts at most {MAX_GROUNDED_ENTRIES} entries"
        )
    resolved_root = Path(root).resolve()
    validated: list[str] = []
    for entry in entries:
        match = _GROUNDED_RE.fullmatch(entry)
        if match is None:
            raise GroundedEntryError(
                f"--grounded entry must be path[#start-end]: {entry!r}"
            )
        path_text = match.group("path")
        candidate = Path(path_text)
        if candidate.is_absolute():
            raise GroundedEntryError(
                f"--grounded path must be under root: {path_text!r}"
            )
        try:
            resolved = (resolved_root / candidate).resolve()
            under_root = resolved.is_relative_to(resolved_root)
        except (OSError, RuntimeError):
            resolved = resolved_root
            under_root = False
        if not under_root or not resolved.is_file():
            raise GroundedEntryError(f"--grounded path not found: {path_text!r}")

        start_text = match.group("start")
        end_text = match.group("end")
        if start_text is not None and end_text is not None:
            if int(start_text) > int(end_text):
                raise GroundedEntryError(
                    f"--grounded range must ascend: {entry!r}"
                )
        validated.append(entry)
    return tuple(validated)


def read_current_record(
    work_id: str, *, corpus_root: Path | str | None = None
) -> WheypointRecord | None:
    """Read the current record before a chain artifact is replaced."""
    return storage.WorkStore.open(work_id, corpus_root=corpus_root).read_record()


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


def _relative_artifact(
    artifact: str, *, root: Path
) -> tuple[str, Path]:
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
    links: list[ArtifactLink] = []
    for phase in reversed(paths.CHAIN_PHASES):
        absolute = root / ".cheese" / phase / f"{work_id}.md"
        if not absolute.is_file():
            continue
        digest = storage.file_digest(absolute)
        if digest is None:
            raise commit.CommitError(
                f"cannot digest existing phase artifact: {absolute}"
            )
        relative = absolute.relative_to(root).as_posix()
        links.append(ArtifactLink(path=relative, digest=digest))
    return links


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
    return CheckpointIntent(
        work_id=intent.work_id,
        orientation=intent.orientation,
        working_context=list(grounded) if grounded else None,
        notes=None if current is not None else intent.notes,
        next=intent.next,
        artifact=intent.artifact,
        tasks=intent.tasks,
        parallel=intent.parallel,
        entries=intent.entries,
        artifact_links=artifact_links,
        remove_artifact_links=intent.remove_artifact_links,
        decision_dossier=intent.decision_dossier,
        transitions=intent.transitions,
        base_revision_id=base_revision_id,
        session=intent.session,
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
) -> CommitOutcome:
    """Commit one chain-phase revision, retrying one stale-parent conflict."""
    root_path = Path.cwd().resolve() if root is None else Path(root).resolve()
    artifact_path, _ = _relative_artifact(artifact, root=root_path)
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    current = (
        store.read_record()
        if current_record is _CURRENT_UNSET
        else cast(WheypointRecord | None, current_record)
    )
    if current is None and not grounded:
        raise commit.CommitError(
            "a genesis phase write requires at least one --grounded entry"
        )

    session = provenance if provenance is not None else session_provenance_from_environment()
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
        return commit.commit(delta, store=store, artifact_root=root_path)
    except (commit.StaleParentError, commit.GenesisConflictError):
        refreshed = store.read_record()
        retry_links = _phase_links(root=root_path, work_id=work_id)
        retry_intent = _retry_intent(
            intent,
            base_revision_id=_base_revision_id(refreshed),
            grounded=grounded,
            artifact_links=retry_links,
            current=refreshed,
        )
        retry_delta = _build_delta(retry_intent, refreshed)
        return commit.commit(retry_delta, store=store, artifact_root=root_path)


__all__ = [
    "CommitOutcome",
    "GroundedEntryError",
    "MAX_GROUNDED_ENTRIES",
    "commit_phase_revision",
    "read_current_record",
    "session_provenance_from_environment",
    "validate_grounded",
]
