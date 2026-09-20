"""Durable per-scope RemediationState storage for fan remediation.

Each remediation scope -- one curd or the post-merge result -- owns one
immutable state artifact on disk. The store creates the initial
``awaiting_review`` state, publishes each transition atomically, and reloads and
validates the published bytes before the caller trusts them. Publication uses
the shared ``atomic_write`` primitive (temp file, fsync, atomic rename, parent
fsync). If publication or reload fails, the store raises and the caller stops
closed -- it never dispatches a next phase against unpublished state.

The state path is derived only from the scope key, so a resume reloads the exact
same artifact the previous run published.
"""
from __future__ import annotations

from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
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

from easy_cheese.shared.publication import PublicationError, atomic_write


class StateStoreError(Exception):
    """A remediation state failed to publish, reload, or validate."""


def _state_version() -> ContractVersion:
    version = supported_version_for(RemediationState)
    if version is None:
        raise TypeError("RemediationState does not carry a contract version")
    return version


def scope_state_path(root: str | Path, scope: RemediationScopeKey) -> Path:
    """Return the canonical on-disk path for one scope's state artifact."""
    return (
        Path(root)
        / "remediation"
        / scope.run_id
        / f"{scope.scope_kind.value}-{scope.scope_id}.json"
    )


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


def publish_state(path: str | Path, state: RemediationState) -> RemediationState:
    """Publish `state` atomically, reload it, and validate it. Fail closed.

    Returns the reloaded, validated state so the caller trusts durable bytes,
    not the in-memory object.
    """
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, canonical_bytes(state))
        reread = target.read_bytes()
        result = validate_contract(
            reread, RemediationState, supported_version_for(RemediationState)
        )
    except (PublicationError, OSError, ContractValidationError) as exc:
        raise StateStoreError(
            f"state publish/reload failed for {target}; no next phase dispatched: {exc}"
        ) from exc
    return cast(RemediationState, result.value)


def load_state(path: str | Path) -> RemediationState:
    """Reload and validate a published state artifact. Fail closed."""
    target = Path(path)
    try:
        raw = target.read_bytes()
        result = validate_contract(
            raw, RemediationState, supported_version_for(RemediationState)
        )
    except (OSError, ContractValidationError) as exc:
        raise StateStoreError(
            f"cannot load remediation state {target}: {exc}"
        ) from exc
    return cast(RemediationState, result.value)
