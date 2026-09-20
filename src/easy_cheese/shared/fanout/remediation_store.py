"""Durable per-scope RemediationState storage for fan remediation.

Each remediation scope -- one curd or the post-merge result -- owns one
immutable state artifact on disk. The store creates the initial
``awaiting_review`` state, publishes each transition atomically, and reloads and
validates the published bytes before the caller trusts them. Publication uses
the shared ``atomic_write`` primitive (temp file, fsync, atomic rename, parent
fsync). If publication or reload fails, the store raises and the caller stops
closed -- it never dispatches a next phase against unpublished state.

The state path is derived only from the scope key, so a resume reloads the exact
same artifact the previous run published. Every publish and load re-checks that
the path stays inside its root, and every read stops at ``MAX_STATE_BYTES``.

One exclusive lock file per run stops two ``run_fan`` processes from publishing
to the same run.
"""
from __future__ import annotations

import contextlib
import errno
from collections.abc import Generator
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    MAX_CONTRACT_BYTES,
    ContractVersion,
    RemediationCursor,
    RemediationDisposition,
    RemediationScopeKey,
    RemediationState,
    canonical_bytes,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError

from easy_cheese.shared.bounded_read import read_bounded_file
from easy_cheese.shared.advisory_lock import advisory_lock
from easy_cheese.shared.publication import PublicationError, atomic_write
from easy_cheese.shared.remediation_artifacts import (
    RemediationPathError,
    contained_path,
    path_component,
)

MAX_STATE_BYTES = MAX_CONTRACT_BYTES

class StateStoreError(Exception):
    """A remediation state failed to publish, reload, or validate."""


def _state_version() -> ContractVersion:
    version = supported_version_for(RemediationState)
    if version is None:
        raise TypeError("RemediationState does not carry a contract version")
    return version


def _contained(root: Path, target: Path) -> Path:
    try:
        return contained_path(root, target)
    except RemediationPathError as error:
        raise StateStoreError(str(error)) from error


def scope_state_path(root: str | Path, scope: RemediationScopeKey) -> Path:
    """Return a deterministic, root-contained path for one scope state artifact."""
    base = Path(root).resolve()
    target = base / "remediation" / path_component(scope.run_id) / (
        f"{path_component(scope.scope_kind.value)}-"
        f"{path_component(scope.scope_id)}.json"
    )
    return _contained(base, target)


def initial_state(scope: RemediationScopeKey, *, state_id: str) -> RemediationState:
    """Build the initial ``awaiting_review`` state for a fresh scope."""
    return RemediationState(
        contract_version=_state_version(),
        state_id=state_id,
        scope=scope,
        cursor=RemediationCursor.AWAITING_REVIEW,
        disposition=RemediationDisposition.ACTIVE,
        locked_selection=(),
    )


def publish_state(
    root: str | Path, path: str | Path, state: RemediationState
) -> RemediationState:
    """Publish `state` atomically under `root`, reload it, and validate it.

    Returns the reloaded, validated state so the caller trusts durable bytes,
    not the in-memory object. A path outside `root` fails closed.
    """
    target = _contained(Path(root).resolve(), Path(path))
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, canonical_bytes(state))
    except (PublicationError, OSError) as exc:
        raise StateStoreError(
            f"state publish failed for {target}; no next phase dispatched: {exc}"
        ) from exc
    return _read_state(target)


def load_state(root: str | Path, path: str | Path) -> RemediationState:
    """Reload and validate a published state artifact under `root`. Fail closed."""
    return _read_state(_contained(Path(root).resolve(), Path(path)))


def _read_state(target: Path) -> RemediationState:
    try:
        raw = read_bounded_file(target, limit=MAX_STATE_BYTES)
        result = validate_contract(
            raw, RemediationState, supported_version_for(RemediationState)
        )
    except (OSError, ContractValidationError) as exc:
        raise StateStoreError(
            f"cannot load remediation state {target}; no next phase dispatched: {exc}"
        ) from exc
    return cast(RemediationState, result.value)


def run_lock_path(root: str | Path, run_id: str) -> Path:
    """Return the root-contained lock path for one run."""
    base = Path(root).resolve()
    return _contained(base, base / "remediation" / path_component(run_id) / "run.lock")


@contextlib.contextmanager
def run_lock(root: str | Path, run_id: str) -> Generator[Path, None, None]:
    """Hold the nonblocking OS lock for one run."""
    lock = run_lock_path(root, run_id)
    acquired = False
    try:
        with advisory_lock(lock, blocking=False):
            acquired = True
            yield lock
    except BlockingIOError as exc:
        if acquired:
            raise
        raise StateStoreError(
            f"run {run_id} is locked by another run_fan process; lock file: {lock}"
        ) from exc
    except OSError as exc:
        if acquired:
            raise
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            raise StateStoreError(
                f"run {run_id} is locked by another run_fan process; lock file: {lock}"
            ) from exc
        raise StateStoreError(f"cannot create run lock {lock}: {exc}") from exc