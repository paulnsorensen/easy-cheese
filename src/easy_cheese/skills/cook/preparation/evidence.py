"""Bounded host ingress and durable artifact retention for preparation.

Every byte Cook reads from the host crosses this module, so the hardened
ingress stays on one path.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import attrs

from easy_cheese_schemas import (
    MAX_ARTIFACT_BYTES,
    ArtifactRef,
    canonical_bytes,
)
from easy_cheese_schemas.mold_cook import MoldCookInputKind
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese_schemas.validate import require_exact_keys, require_mapping
from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_artifact,
    resolve_file_path,
    resolve_verified_bytes,
    restrict_local_path,
)
from easy_cheese.shared.bounded_read import (
    BoundedReadOverflow,
    NotRegularFileError,
    read_bounded_file,
)
from easy_cheese.shared.mold_cook_handoff import resolve_contract
from easy_cheese.shared.wheypoint.canonical import digest_bytes

from ._types import (
    ClassifiedCookInput,
    CookEvidenceError,
    CookInputError,
    CookPreparationRequest,
)


def local_path_for(uri: str, allowed_root: str | Path | None = None) -> Path:
    """Resolve one `file:` artifact URI through the shared artifact seam.

    A caller that already knows its trusted root passes it: the URI then names
    a path inside that root instead of widening it.
    """

    parsed = urlsplit(uri)
    path = resolve_file_path(parsed.netloc, parsed.path)
    if allowed_root is None:
        return path
    return restrict_local_path(path, allowed_root)


def as_path(source: str | Path) -> Path | None:
    try:
        return (
            source.expanduser()
            if isinstance(source, Path)
            else Path(source).expanduser()
        )
    except (OSError, ValueError):
        return None


def read_path(path: Path, *, limit: int = MAX_ARTIFACT_BYTES) -> bytes:
    """Read one regular file through the shared bounded, no-follow reader."""

    try:
        return read_bounded_file(path, limit=limit)
    except NotRegularFileError as exc:
        raise CookInputError(f"input is not a regular file: {path!r}") from exc
    except BoundedReadOverflow as exc:
        raise CookInputError(
            f"input {path!r} is larger than the {limit}-byte limit"
        ) from exc
    except OSError as exc:
        raise CookInputError(f"cannot read input {path!r}: {exc}") from exc


def is_regular_path(path: Path) -> bool:
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False


def persist_bytes(
    root: Path,
    *,
    content: bytes,
    artifact_id: str,
    role: str,
    media_type: str,
    schema_uri: str | None = None,
) -> ArtifactRef:
    digest = digest_bytes(content)
    reference = ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=root.resolve().as_uri(),
        digest=digest,
        size_bytes=len(content),
        media_type=media_type,
        schema_uri=schema_uri,
    )
    try:
        retained = resolve_verified_bytes(
            reference,
            content,
            media_type.split(";", 1)[0],
            root,
        )
    except (
        ArtifactDigestMismatchError,
        ArtifactResolutionError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise CookEvidenceError(f"cannot retain artifact {artifact_id!r}") from exc
    return attrs.evolve(reference, uri=Path(retained.path).as_uri())


def persist_value(
    root: Path,
    value: object,
    *,
    artifact_id: str,
    role: str,
    schema_uri: str | None,
) -> ArtifactRef:
    return persist_bytes(
        root,
        content=canonical_bytes(value),
        artifact_id=artifact_id,
        role=role,
        media_type="application/json",
        schema_uri=schema_uri,
    )


def resolve_ref(ref: ArtifactRef, root: Path) -> bytes:
    try:
        return resolve_artifact(
            attrs.evolve(ref, schema_uri=None),
            repository_root=root,
            artifact_directory=root,
            allowed_local_root=root,
        ).content
    except (ArtifactResolutionError, ArtifactDigestMismatchError) as exc:
        raise CookEvidenceError(
            f"artifact {ref.artifact_id!r} is unreadable: {exc}"
        ) from exc


def load_contract(ref: ArtifactRef, contract: type, root: Path) -> object:
    try:
        return resolve_contract(ref, contract, root).value
    except ContractValidationError as exc:
        raise CookEvidenceError(
            f"artifact {ref.artifact_id!r} is not a valid {contract.__name__}: {exc}"
        ) from exc


def _request_payload(request: CookPreparationRequest) -> dict[str, object]:
    source = request.source
    if not isinstance(source, ClassifiedCookInput):
        raise CookEvidenceError("preparation request source was not classified")
    path = None if source.path is None else str(source.path.resolve())
    source_digest = None if source.snapshot is None else digest_bytes(source.snapshot)
    return {
        "request_id": request.request_id,
        "kind": source.kind.value,
        "source": source.source,
        "path": path,
        "explicit": source.explicit,
        "declared_kind": (
            None if source.declared_kind is None else source.declared_kind.value
        ),
        "source_digest": source_digest,
        "repository_root": str(request.repository_root),
        "artifact_root": str(request.artifact_root),
        "mode": request.mode.value,
    }


def persist_request(request: CookPreparationRequest) -> ArtifactRef:
    return persist_bytes(
        request.artifact_root,
        content=canonical_bytes(_request_payload(request)),
        artifact_id=f"{request.request_id}/preparation-request",
        role="preparation_request",
        media_type="application/json",
    )


def request_metadata(ref: ArtifactRef, root: Path) -> Mapping[str, object]:
    raw = resolve_ref(ref, root)
    try:
        value = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CookEvidenceError(
            "preparation request reference is not valid JSON"
        ) from exc
    values = require_mapping(value, "preparation request")
    required = (
        "request_id",
        "kind",
        "source",
        "path",
        "explicit",
        "declared_kind",
        "source_digest",
        "repository_root",
        "artifact_root",
        "mode",
    )
    try:
        require_exact_keys(values, required, "preparation request")
    except ValueError as exc:
        raise CookEvidenceError(str(exc)) from exc
    return values


def source_ref(source: ClassifiedCookInput, root: Path, request_id: str) -> ArtifactRef:
    if source.path is not None:
        raw = source.snapshot if source.snapshot is not None else read_path(source.path)
        media_type = (
            "text/markdown"
            if source.path.suffix.casefold() in {".md", ".markdown"}
            else "application/octet-stream"
        )
        return persist_bytes(
            root,
            content=raw,
            artifact_id=f"{request_id}/input",
            role="spec" if source.kind is MoldCookInputKind.DIRECT_SPEC else "input",
            media_type=media_type,
        )
    return persist_bytes(
        root,
        content=source.source.encode("utf-8"),
        artifact_id=f"{request_id}/input",
        role="spec" if source.kind is MoldCookInputKind.TASK else "input",
        media_type="text/plain",
    )
