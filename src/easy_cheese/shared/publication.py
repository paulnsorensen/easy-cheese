"""Publish canonical payloads through a private operation index."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from easy_cheese_schemas import (
    MAX_CONTRACT_BYTES,
    AcceptedArtifact,
    ArtifactRef,
    CanonicalArtifact,
    ContractValidationError,
    PublishedArtifact,
    canonical_bytes,
    supported_version_for,
    validate_contract,
)
from easy_cheese.shared.phase_routes import validate_route
from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_artifact,
    restrict_open_file,
)
from easy_cheese.shared.bounded_read import BoundedReadOverflow, read_bounded_file


_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")

__all__ = [
    "BoundedReadOverflow",
    "CorruptLeftoverError",
    "IdempotencyConflictError",
    "PayloadDigestMismatchError",
    "PointerNotFoundError",
    "PublicationError",
    "accept",
    "atomic_write",
    "pointer_path",
    "publish_canonical",
    "read_bounded",
    "request_digest",
]



class PublicationError(ValueError):
    """Base for every error the publication gateway itself raises.

    A caller across the Mold-to-Cook boundary can catch this one type to
    reject any publication-gateway failure as a diagnosed error, instead of
    letting an unlisted member of the family escape as a raw traceback.
    """


class IdempotencyConflictError(PublicationError):
    """``operation_id`` replayed with a request that does not match."""


class CorruptLeftoverError(PublicationError):
    """A prepared payload file does not match its content digest.

    Raised on retry after an interrupted publication when a leftover file was
    tampered with between the crash and the retry. Repair quarantines the
    file first. It removes a file that stays corrupt, and it retains a valid
    replacement that a racing writer put in place. The message names the
    outcome, and a further retry starts from a clean or valid file.
    """


class PointerNotFoundError(PublicationError):
    """``pointer_path`` does not reference an existing pointer file."""


class PayloadDigestMismatchError(PublicationError):
    """A previously revealed pointer's payload no longer matches its digest."""


@dataclass(frozen=True)
class _PublicationRequest:
    operation_id: str
    request_digest: str
    source_phase: str
    destination_phase: str
    payload_schema_uri: str


@dataclass(frozen=True)
class _StoredPublication:
    request: _PublicationRequest
    payload: ArtifactRef


def _digest_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _digest_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def request_digest(
    raw_text: str,
    invocation: Mapping[str, object],
    *,
    source_phase: str,
    destination_phase: str,
    payload_schema_uri: str,
) -> str:
    """Digest the request text, invocation, route, and payload schema."""
    envelope = json.dumps(
        {
            "destination_phase": destination_phase,
            "invocation": invocation,
            "payload_schema_uri": payload_schema_uri,
            "raw_text": raw_text,
            "source_phase": source_phase,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _digest_text(envelope)


def _fsync_dir(directory: Path) -> None:
    """Flush ``directory`` metadata where the platform supports it.

    Windows and some network filesystems refuse a directory handle or a
    directory ``fsync``. Durability is best effort there; the caller has
    already flushed the file itself, so the publication still proceeds.
    """
    try:
        descriptor = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        return
    finally:
        os.close(descriptor)


def atomic_write(path: Path, content: bytes) -> None:
    """Write `content` to `path` as one private, durable, atomic replacement.

    This is the single copy of the mkstemp/restrict/fsync/replace/dir-fsync
    sequence every host-side artifact writer in the runtime uses.
    """

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            restrict_open_file(handle.fileno(), Path(temp_name))
            _ = handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        _fsync_dir(path.parent)
    except BaseException:
        with suppress(OSError):
            os.unlink(temp_name)
        raise


def _exclusive_reveal(temp_name: str, path: Path, _content: bytes) -> None:
    """Reveal one complete pointer or fail before creating its public path.

    A hard link is the primitive that fails loudly on a racing reveal. A
    filesystem without hard links has no safe exclusive reveal primitive.
    """
    try:
        os.link(temp_name, path)
        return
    except FileExistsError:
        raise
    except OSError as exc:
        raise PublicationError(
            "filesystem lacks an exclusive atomic reveal primitive"
        ) from exc


def _atomic_reveal(path: Path, content: bytes) -> None:
    """Create ``path`` exclusively, raising ``FileExistsError`` if it is
    already there -- a racing reveal for the same ``operation_id`` can never
    overwrite a pointer another caller already published."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            _ = handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _exclusive_reveal(temp_name, path, content)
        _fsync_dir(path.parent)
    finally:
        with suppress(OSError):
            os.unlink(temp_name)


def _content_path(directory: Path, digest: str) -> Path:
    return directory / f"{digest.replace(':', '-')}.json"


@contextmanager
def _digest_lock(directory: Path, digest: str) -> Generator[None, None, None]:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = directory / f".{digest.replace(':', '-')}.lock"
    descriptor = os.open(
        str(lock_path),
        os.O_CREAT | os.O_RDWR,
        0o600,
    )
    locked = False
    try:
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
        yield
    finally:
        if fcntl is not None and locked:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _retain_content(directory: Path, digest: str, content: bytes) -> Path:
    """Write ``content`` at its digest-addressed path, revalidating a leftover.

    The lock serializes cooperating writers. Atomic quarantine also prevents a
    lockless writer from losing a valid replacement during corrupt-file repair.
    """
    path = _content_path(directory, digest)
    with _digest_lock(directory, digest):
        if path.exists():
            try:
                existing = path.read_bytes()
            except FileNotFoundError as exc:
                raise CorruptLeftoverError(
                    f"prepared content at {path} changed during repair"
                ) from exc
            if _digest_bytes(existing) == digest:
                return path

            descriptor, quarantine_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".corrupt", dir=str(directory)
            )
            os.close(descriptor)
            quarantine = Path(quarantine_name)
            try:
                try:
                    os.replace(path, quarantine)
                except FileNotFoundError as exc:
                    raise CorruptLeftoverError(
                        f"prepared content at {path} changed during repair"
                    ) from exc
                quarantined = quarantine.read_bytes()
                if _digest_bytes(quarantined) == digest:
                    atomic_write(path, quarantined)
                    raise CorruptLeftoverError(
                        f"prepared content at {path} changed during repair; retained"
                    )
            finally:
                quarantine.unlink(missing_ok=True)
            raise CorruptLeftoverError(
                f"prepared content at {path} does not match digest {digest}; removed"
            )
        atomic_write(path, content)
    return path


def read_bounded(path: Path, max_bytes: int) -> bytes:
    """Read at most ``max_bytes`` of ``path``, rejecting a larger file unread.

    A caller-supplied path never causes the gateway to allocate more than
    ``max_bytes`` for it before validation runs. The shared reader also
    refuses a final symlink and any path that is not a regular file, so a
    caller-supplied pointer path cannot redirect the gateway.
    """
    return read_bounded_file(path, limit=max_bytes)


def _read_bounded(path: Path) -> bytes:
    """Read at most one contract-sized file, rejecting a larger one unread.

    A pointer path is caller-supplied, so the gateway never allocates more
    than ``MAX_CONTRACT_BYTES`` for it before schema validation runs.
    """
    try:
        return read_bounded(path, MAX_CONTRACT_BYTES)
    except BoundedReadOverflow as exc:
        raise ContractValidationError(
            f"pointer at {path} exceeds MAX_CONTRACT_BYTES ({MAX_CONTRACT_BYTES} bytes)"
        ) from exc


def _read_pointer(path: Path) -> _StoredPublication:
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ContractValidationError(f"duplicate field {key!r}")
            value[key] = item
        return value

    try:
        decoded = cast("object", json.loads(_read_bounded(path), object_pairs_hook=unique_pairs))
        if not isinstance(decoded, dict):
            raise ValueError("invalid publication index")
        data = cast("dict[str, object]", decoded)
        if set(data) != {"request", "payload"}:
            if "request" not in data and {"operation_id", "request_digest"} <= set(data):
                raise ValueError(
                    "legacy handoff pointer format; re-run finalization to republish it"
                )
            raise ValueError("invalid publication index")
        raw_request = data["request"]
        raw_payload = data["payload"]
        if not isinstance(raw_request, dict) or not isinstance(raw_payload, dict):
            raise ValueError("invalid publication index")
        request_data = cast("dict[str, object]", raw_request)
        payload_data = cast("dict[str, object]", raw_payload)
        if set(request_data) != {
            "operation_id", "request_digest", "source_phase",
            "destination_phase", "payload_schema_uri",
        } or not all(isinstance(value, str) for value in request_data.values()):
            raise ValueError("invalid publication request")
        request = _PublicationRequest(
            operation_id=cast("str", request_data["operation_id"]),
            request_digest=cast("str", request_data["request_digest"]),
            source_phase=cast("str", request_data["source_phase"]),
            destination_phase=cast("str", request_data["destination_phase"]),
            payload_schema_uri=cast("str", request_data["payload_schema_uri"]),
        )
        if _pointer_path(path.resolve().parent.parent, request.operation_id).resolve() != path.resolve():
            raise ValueError("operation index path does not match operation_id")
        if _DIGEST_RE.fullmatch(request.request_digest) is None:
            raise ValueError("invalid request digest")
        if set(payload_data) != {
            "artifact_id", "role", "uri", "digest", "size_bytes",
            "media_type", "schema_uri",
        }:
            raise ValueError("invalid publication payload reference")
        payload = ArtifactRef(
            artifact_id=cast("str", payload_data["artifact_id"]),
            role=cast("str", payload_data["role"]),
            uri=cast("str", payload_data["uri"]),
            digest=cast("str", payload_data["digest"]),
            size_bytes=cast("int", payload_data["size_bytes"]),
            media_type=cast("str", payload_data["media_type"]),
            schema_uri=cast("str | None", payload_data["schema_uri"]),
        )
        if payload.schema_uri != request.payload_schema_uri:
            raise ValueError("payload schema does not match publication request")
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ContractValidationError(f"invalid publication index at {path}: {exc}") from exc
    return _StoredPublication(request, payload)


def _resolve_pointer_artifact(
    ref: ArtifactRef,
    artifact_root: Path,
    *,
    digest_error: Callable[[str], Exception] | None = None,
) -> bytes:
    try:
        scheme = urlsplit(ref.uri).scheme
    except ValueError as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} has an invalid uri"
        ) from exc
    if scheme != "file":
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} is not a file:// uri"
        )
    try:
        resolved = resolve_artifact(
            ref,
            repository_root=artifact_root,
            artifact_directory=artifact_root,
            allowed_local_root=artifact_root,
        )
    except ArtifactDigestMismatchError as exc:
        error = (
            digest_error(str(exc))
            if digest_error is not None
            else ContractValidationError(str(exc))
        )
        raise error from exc
    except ArtifactResolutionError as exc:
        raise ContractValidationError(str(exc)) from exc
    return resolved.content


def _resolve_pointer(
    pointer: _StoredPublication,
    request: _PublicationRequest,
    artifact_root: Path,
) -> CanonicalArtifact:
    if pointer.request.payload_schema_uri != request.payload_schema_uri:
        raise ContractValidationError(
            "unsupported-pointer-schema: pointer schema "
            + f"{pointer.request.payload_schema_uri!r} does not match consumer "
            + f"{request.payload_schema_uri!r}"
        )
    if pointer.request.destination_phase != request.destination_phase:
        raise ContractValidationError(
            f"pointer destination {pointer.request.destination_phase!r} does not match "
            + f"consumer {request.destination_phase!r}"
        )
    validate_route(
        pointer.request.source_phase, pointer.request.destination_phase, request.payload_schema_uri
    )
    payload_bytes = _resolve_pointer_artifact(
        pointer.payload,
        artifact_root,
        digest_error=PayloadDigestMismatchError,
    )
    canonical = validate_contract(
        payload_bytes,
        request.payload_schema_uri,
        supported_version_for(request.payload_schema_uri),
    )
    return canonical


def _rehydrate(
    pointer: _StoredPublication, request: _PublicationRequest, artifact_root: Path,
    path: Path,
) -> PublishedArtifact:
    canonical = _resolve_pointer(pointer, request, artifact_root)
    return PublishedArtifact(pointer_path=path, canonical=canonical)


def _pointer_path(root: Path, operation_id: str) -> Path:
    if (
        not isinstance(operation_id, str)  # pyright: ignore[reportUnnecessaryIsInstance]
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", operation_id) is None
    ):
        raise PublicationError("invalid operation_id")
    pointer_dir = (root / "pointers").resolve()
    pointer_path = pointer_dir / f"{operation_id}.json"
    if pointer_path.parent != pointer_dir:
        raise PublicationError("invalid operation_id")
    return pointer_path


def pointer_path(root: Path, operation_id: str) -> Path:
    """Return the pointer path this gateway reveals for one operation.

    A consumer that must name a published pointer asks the gateway instead of
    joining the path itself, so the identifier check and the containment check
    apply to every caller.
    """

    return _pointer_path(root, operation_id)


def _validate_replay(pointer: _StoredPublication, request: _PublicationRequest) -> None:
    if pointer.request != request:
        raise IdempotencyConflictError(
            f"operation {pointer.request.operation_id!r} was already published with a different request"
        )


def publish_canonical(
    *,
    request_digest: str,
    source_phase: str,
    destination_phase: str,
    payload_schema_uri: str,
    operation_id: str,
    artifact_root: str | Path,
    prepare: Callable[[], CanonicalArtifact],
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    """Validate, persist, and reveal one canonical publication."""
    request = _PublicationRequest(
        operation_id=operation_id,
        request_digest=request_digest,
        source_phase=source_phase,
        destination_phase=destination_phase,
        payload_schema_uri=payload_schema_uri,
    )
    if _DIGEST_RE.fullmatch(request.request_digest) is None:
        raise PublicationError("invalid request_digest")
    return _publish_canonical(
        request=request,
        artifact_root=artifact_root,
        prepare=prepare,
        _before_reveal=_before_reveal,
    )


def _publish_canonical(
    *,
    request: _PublicationRequest,
    artifact_root: str | Path,
    prepare: Callable[[], CanonicalArtifact],
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    """Persist a prepared canonical payload and reveal its pointer."""
    root = Path(artifact_root)
    pointer_path = _pointer_path(root, request.operation_id)
    validate_route(
        request.source_phase, request.destination_phase, request.payload_schema_uri
    )
    if pointer_path.exists():
        existing = _read_pointer(pointer_path)
        _validate_replay(existing, request)
        return _rehydrate(existing, request, root, pointer_path)

    validated = prepare()
    payload_bytes = validated.canonical_bytes
    payload_digest = _digest_bytes(payload_bytes)
    payload_path = _retain_content(root / "payloads", payload_digest, payload_bytes)
    payload_ref = ArtifactRef(
        artifact_id=f"payload-{request.operation_id}",
        role="payload",
        uri=payload_path.resolve().as_uri(),
        digest=payload_digest,
        size_bytes=len(payload_bytes),
        media_type="application/json",
        schema_uri=request.payload_schema_uri,
    )
    pointer = _StoredPublication(request, payload_ref)
    pointer_bytes = canonical_bytes({"request": request.__dict__, "payload": payload_ref})
    if _before_reveal is not None:
        _before_reveal()
    _ = _resolve_pointer(pointer, request, root)
    try:
        _atomic_reveal(pointer_path, pointer_bytes)
    except FileExistsError:
        existing = _read_pointer(pointer_path)
        _validate_replay(existing, request)
        return _rehydrate(existing, request, root, pointer_path)
    return PublishedArtifact(pointer_path=pointer_path, canonical=validated)


def accept(
    pointer_path: str | Path,
    *,
    destination_phase: str,
    payload_schema_uri: str,
    artifact_root: str | Path | None = None,
) -> AcceptedArtifact:
    """Validate a private operation index and its canonical payload."""
    path = Path(pointer_path)
    if not path.is_file():
        raise PointerNotFoundError(f"pointer not found at {path}")
    root = (
        Path(artifact_root)
        if artifact_root is not None
        else path.resolve().parent.parent
    )
    pointer = _read_pointer(path)
    request = _PublicationRequest(
        operation_id=pointer.request.operation_id,
        request_digest=pointer.request.request_digest,
        source_phase=pointer.request.source_phase,
        destination_phase=destination_phase,
        payload_schema_uri=payload_schema_uri,
    )
    canonical = _resolve_pointer(pointer, request, root)
    return AcceptedArtifact(canonical=canonical)
