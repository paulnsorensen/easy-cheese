"""Shared path and artifact-ref helpers for fan remediation state.

Every remediation component derives on-disk paths from opaque identifiers the
same way, and builds an `ArtifactRef` over the same digest. This module is the
one place that derivation lives, so the on-disk layout stays identical across
`run_fan`, `remediation_store`, and `remediation_decision`.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from easy_cheese_schemas import ArtifactRef

from easy_cheese.shared.artifacts import ArtifactResolutionError, restrict_local_path
from easy_cheese.shared.wheypoint.canonical import digest_bytes

REMEDIATION_STATE_ROLE = "remediation_state"


class RemediationPathError(ValueError):
    """A remediation artifact path escaped its allowed root."""


def path_component(value: str) -> str:
    """Encode an opaque identifier before it is used as a path component."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def contained_path(root: Path, target: Path) -> Path:
    """Return `target` resolved, refusing a path that escapes `root`."""
    try:
        return restrict_local_path(target, root)
    except ArtifactResolutionError as error:
        raise RemediationPathError(
            f"remediation path escapes artifact root: {target}"
        ) from error


def bytes_digest(content: bytes) -> str:
    """Return the `sha256:<hex>` digest of `content`."""
    return digest_bytes(content)


def build_artifact_ref(
    path: Path,
    raw: bytes,
    *,
    artifact_id: str,
    role: str,
    media_type: str = "application/json",
) -> ArtifactRef:
    """Build a host-owned reference to `raw`, already persisted at `path`."""
    return ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=path.resolve().as_uri(),
        digest=bytes_digest(raw),
        size_bytes=len(raw),
        media_type=media_type,
    )
