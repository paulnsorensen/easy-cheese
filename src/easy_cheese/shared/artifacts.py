from __future__ import annotations

import contextlib
import errno
import hashlib
import hmac
import json
import mimetypes
import os
import re
import stat
import tempfile
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult, unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from attrs import define

from easy_cheese_schemas.contracts import ArtifactRef, MAX_ARTIFACT_BYTES

from easy_cheese.shared.bounded_read import (
    BoundedReadOverflow,
    NotRegularFileError,
    read_bounded_descriptor,
    read_bounded_file,
    read_bounded_stream,
)

__all__ = [
    "MAX_ARTIFACT_BYTES",
    "ArtifactDigestMismatchError",
    "ArtifactResolutionError",
    "ResolvedAgentArtifact",
    "read_repository_artifact",
    "resolve_artifact",
    "resolve_file_path",
    "resolve_verified_bytes",
    "restrict_local_path",
    "restrict_open_file",
]

SchemaValidator = Callable[[bytes, str], None]

# A retained artifact is named `sha256-<hex>` with no extension by design, so
# no extension-based reader can type it.
_RETAINED_ARTIFACT_NAME = re.compile(r"^sha256-[0-9a-f]{64}$")

_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 5


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:  # pyright: ignore[reportImplicitOverride]
        return None


urlopen = build_opener(_NoRedirectHandler()).open


class ArtifactResolutionError(ValueError):
    pass


class ArtifactDigestMismatchError(ArtifactResolutionError):
    """The resolved bytes do not match the artifact's declared digest."""


@define(frozen=True)
class ResolvedAgentArtifact:
    role: str
    path: str
    media_type: str
    content: bytes


def resolve_artifact(
    artifact: ArtifactRef,
    *,
    repository_root: str | Path = ".",
    artifact_directory: str | Path,
    schema_validator: SchemaValidator | None = None,
    allowed_local_root: str | Path | None = None,
) -> ResolvedAgentArtifact:

    if artifact_directory is None:  # pyright: ignore[reportUnnecessaryComparison]
        raise ArtifactResolutionError("artifact_directory is required")  # pyright: ignore[reportUnreachable]
    if not isinstance(artifact, ArtifactRef):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ArtifactResolutionError("artifact must be an ArtifactRef")  # pyright: ignore[reportUnreachable]
    _require_artifact_size(artifact.size_bytes)
    try:
        parsed = urlsplit(artifact.uri)
    except ValueError as exc:
        raise ArtifactResolutionError("artifact URI is invalid") from exc
    if parsed.query or parsed.fragment:
        raise ArtifactResolutionError(
            "artifact URI must not contain a query or fragment"
        )

    if parsed.scheme == "repo":
        content, detected_type = read_repository_artifact(
            parsed.netloc,
            parsed.path,
            repository_root,
            artifact.size_bytes,
        )
    elif parsed.scheme == "file":
        path = resolve_file_path(parsed.netloc, parsed.path)
        if allowed_local_root is not None:
            path = restrict_local_path(path, allowed_local_root)
        content, detected_type = _read_local(path, artifact.size_bytes)
    elif parsed.scheme == "https":
        content, detected_type = _read_https(artifact, parsed)
    else:
        raise ArtifactResolutionError(
            f"unsupported artifact URI scheme: {parsed.scheme}"
        )

    return resolve_verified_bytes(
        artifact,
        content,
        detected_type,
        artifact_directory,
        schema_validator,
    )


def resolve_verified_bytes(
    artifact: ArtifactRef,
    content: bytes,
    detected_type: str | None,
    artifact_directory: str | Path,
    schema_validator: SchemaValidator | None = None,
) -> ResolvedAgentArtifact:
    # The content digest is the integrity check, the retained file name, and
    # the snapshot identity, so it is derived once and threaded through.
    digest = hashlib.sha256(content).digest()
    _validate_integrity(artifact, content, detected_type, digest)
    _validate_schema(artifact, content, schema_validator)
    directory = _prepare_artifact_directory(artifact_directory)
    path = _retain_verified_bytes(content, directory, digest)
    return _agent_view(artifact, path, content)


def _agent_view(
    artifact: ArtifactRef, path: str, content: bytes
) -> ResolvedAgentArtifact:
    return ResolvedAgentArtifact(
        role=artifact.role,
        path=path,
        media_type=artifact.media_type,
        content=content,
    )


def _repository_components(authority: str, uri_path: str) -> tuple[str, ...]:
    relative = unquote(f"{authority}{uri_path}")
    if not relative or relative.startswith("/"):
        raise ArtifactResolutionError("repository URI must name a relative path")
    components = tuple(relative.split("/"))
    if any(component in {"", ".", ".."} for component in components):
        raise ArtifactResolutionError("repository artifact escapes repository root")
    return components


def read_repository_artifact(
    authority: str,
    uri_path: str,
    repository_root: str | Path,
    expected_size: int | None,
) -> tuple[bytes, str | None]:
    components = _repository_components(authority, uri_path)
    root_flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    root_fd: int | None = None
    current_fd: int | None = None
    opened_fds: list[int] = []
    display_path = Path(*components)
    try:
        root_fd = os.open(repository_root, root_flags)
        current_fd = root_fd
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise ArtifactResolutionError(
                f"repository root is not a directory: {repository_root}"
            )
        for component in components[:-1]:
            next_fd = os.open(
                component,
                root_flags,
                dir_fd=current_fd,
            )
            opened_fds.append(next_fd)
            current_fd = next_fd
        final_fd = os.open(
            components[-1],
            file_flags,
            dir_fd=current_fd,
        )
        opened_fds.append(final_fd)
        content = _read_descriptor(final_fd, expected_size, display_path)
    except ArtifactResolutionError:
        raise
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise ArtifactResolutionError(
                "repository artifact escapes repository root"
            ) from exc
        raise ArtifactResolutionError(
            f"repository artifact is not readable: {display_path}"
        ) from exc
    except (TypeError, ValueError, OverflowError) as exc:
        raise ArtifactResolutionError(
            f"repository artifact is not readable: {display_path}"
        ) from exc
    finally:
        for fd in reversed(opened_fds):
            with contextlib.suppress(OSError):
                os.close(fd)
        if root_fd is not None:
            with contextlib.suppress(OSError):
                os.close(root_fd)

    return content, _detected_media_type(display_path)


def resolve_file_path(authority: str, uri_path: str) -> Path:
    """Turn one `file:` URI authority and path into an absolute local path."""

    if authority not in {"", "localhost"}:
        raise ArtifactResolutionError("local file URI must not name a remote host")
    path = Path(unquote(uri_path))
    if not path.is_absolute():
        raise ArtifactResolutionError("file URI must name an absolute path")
    return path


def restrict_local_path(path: Path, allowed_root: str | Path) -> Path:
    """Refuse a local path that resolves outside `allowed_root`."""

    resolved_path = path.resolve()
    resolved_root = Path(allowed_root).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ArtifactResolutionError(
            f"local file artifact escapes allowed root: {resolved_root}"
        )
    return resolved_path


def _read_local(
    path: Path,
    expected_size: int,
) -> tuple[bytes, str | None]:
    _require_artifact_size(expected_size)
    try:
        content = read_bounded_file(path, limit=expected_size)
    except NotRegularFileError as exc:
        raise ArtifactResolutionError(
            f"artifact is not a regular file: {path}"
        ) from exc
    except BoundedReadOverflow as exc:
        raise ArtifactResolutionError(
            f"artifact size mismatch: expected {expected_size}"
        ) from exc
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(f"artifact is not readable: {path}") from exc
    _require_size(expected_size, len(content))

    return content, _detected_media_type(path)


def _detected_media_type(path: Path) -> str | None:
    """Derive the media type of `path`, or fail closed when it is unknown.

    `None` means "no independently derived type", never "equal to the
    declaration".  The retained-artifact name shape is the one declared
    exception: it carries no extension by design, so it returns `None` and
    `_validate_integrity` skips the comparison for it.  Every other
    undeterminable path is refused, on the `repo:` and `file:` ingresses
    alike, so the two admit exactly the same artifacts.
    """

    detected_type, _encoding = mimetypes.guess_type(path.name)
    if detected_type is None and _RETAINED_ARTIFACT_NAME.match(path.name) is None:
        raise ArtifactResolutionError(
            f"artifact media type cannot be determined from path: {path}"
        )
    return detected_type


def _read_descriptor(
    fd: int,
    expected_size: int | None,
    display_path: Path,
) -> bytes:
    if expected_size is not None:
        _require_artifact_size(expected_size)
    limit = MAX_ARTIFACT_BYTES if expected_size is None else expected_size
    try:
        content = read_bounded_descriptor(fd, display_path, limit=limit)
    except NotRegularFileError as exc:
        raise ArtifactResolutionError(
            f"artifact is not a regular file: {display_path}"
        ) from exc
    except BoundedReadOverflow as exc:
        raise ArtifactResolutionError(_overflow_message(expected_size)) from exc
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            f"artifact is not readable: {display_path}"
        ) from exc
    if expected_size is not None:
        _require_size(expected_size, len(content))
    return content


def _overflow_message(expected_size: int | None) -> str:
    if expected_size is None:
        return f"artifact exceeds maximum size of {MAX_ARTIFACT_BYTES} bytes"
    return f"artifact size mismatch: expected {expected_size}"


def _read_bounded(
    reader: Callable[[int], bytes],
    expected_size: int,
    display_path: Path,
) -> bytes:
    _require_artifact_size(expected_size)
    try:
        content = read_bounded_stream(reader, display_path, limit=expected_size)
    except BoundedReadOverflow as exc:
        raise ArtifactResolutionError(_overflow_message(expected_size)) from exc
    _require_size(expected_size, len(content))
    return content


class _HttpsResponse(Protocol):
    headers: Message

    def read(self, amt: int | None = ...) -> bytes: ...
    def __enter__(self) -> _HttpsResponse: ...
    def __exit__(self, *args: object) -> None: ...


def _read_https(artifact: ArtifactRef, parsed: SplitResult) -> tuple[bytes, str]:
    _require_artifact_size(artifact.size_bytes)
    _validate_https_location(parsed)
    current_uri = artifact.uri
    redirects = 0

    while True:
        request = Request(current_uri, headers={"User-Agent": "easy-cheese-schemas/1"})
        try:
            with cast(_HttpsResponse, urlopen(request, timeout=30)) as response:
                status = _response_status(response)
                if status in _REDIRECT_CODES:
                    current_uri = _redirect_uri(
                        current_uri, response.headers.get("Location")
                    )
                    if redirects >= _MAX_REDIRECTS:
                        raise ArtifactResolutionError(
                            "HTTPS artifact exceeded redirect limit"
                        )
                    redirects += 1
                    continue

                _ = _response_uri(response, current_uri)
                detected_type = _response_media_type(response.headers)
                _validate_content_length(
                    response.headers.get("Content-Length"),
                    artifact.size_bytes,
                )
                parsed_path = urlsplit(current_uri).path
                content = _read_bounded(
                    response.read,
                    artifact.size_bytes,
                    Path(parsed_path or "artifact"),
                )
        except HTTPError as exc:
            try:
                headers = exc.headers
                location = headers.get("Location") if headers is not None else None  # pyright: ignore[reportUnnecessaryComparison]
                if exc.code not in _REDIRECT_CODES:
                    raise ArtifactResolutionError(
                        f"HTTPS artifact could not be fetched: {artifact.uri}"
                    ) from exc
                current_uri = _redirect_uri(current_uri, location)
                if redirects >= _MAX_REDIRECTS:
                    raise ArtifactResolutionError(
                        "HTTPS artifact exceeded redirect limit"
                    ) from exc
                redirects += 1
            finally:
                with contextlib.suppress(OSError):
                    exc.close()
            continue
        except ArtifactResolutionError:
            raise
        except (OSError, URLError, ValueError, TypeError) as exc:
            raise ArtifactResolutionError(
                f"HTTPS artifact could not be fetched: {artifact.uri}"
            ) from exc

        return content, detected_type


def _validate_content_length(raw: str | None, expected_size: int) -> None:
    if raw is None:
        return
    try:
        declared = int(raw)
    except (TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            "HTTPS artifact response has an invalid Content-Length"
        ) from exc
    if declared < 0:
        raise ArtifactResolutionError(
            "HTTPS artifact response has an invalid Content-Length"
        )
    _require_artifact_size(declared)
    _require_size(expected_size, declared)


def _response_status(response: object) -> int | None:
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    getcode = getattr(response, "getcode", None)
    if callable(getcode):
        status = getcode()
    return status if isinstance(status, int) else None


def _response_uri(response: object, fallback: str) -> str:
    geturl = cast(Callable[[], str] | None, getattr(response, "geturl", None))
    uri = geturl() if callable(geturl) else fallback
    try:
        parsed = urlsplit(uri)
        _validate_https_location(parsed)
        if parsed.query or parsed.fragment:
            raise ArtifactResolutionError("URI contains a query or fragment")
    except (ArtifactResolutionError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            "HTTPS artifact redirected outside URI policy"
        ) from exc
    return uri


def _redirect_uri(current_uri: str, location: str | None) -> str:
    if not isinstance(location, str) or not location:
        raise ArtifactResolutionError("HTTPS artifact redirected outside URI policy")
    try:
        target = urljoin(current_uri, location)
        parsed = urlsplit(target)
        _validate_https_location(parsed)
        if parsed.query or parsed.fragment:
            raise ArtifactResolutionError("URI contains a query or fragment")
    except (ArtifactResolutionError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            "HTTPS artifact redirected outside URI policy"
        ) from exc
    return target


def _validate_https_location(parsed: SplitResult) -> None:
    try:
        parsed.port
    except ValueError as exc:
        raise ArtifactResolutionError("HTTPS artifact URI has an invalid port") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ArtifactResolutionError(
            "HTTPS artifact URI must name a host without credentials"
        )


def _response_media_type(headers: Message) -> str:
    raw_media_type = headers.get("Content-Type")
    if not isinstance(raw_media_type, str):
        raise ArtifactResolutionError(
            "HTTPS artifact response must declare a Content-Type"
        )
    detected_type = headers.get_content_type()
    if detected_type != _base_media_type(raw_media_type):
        raise ArtifactResolutionError(
            "HTTPS artifact response has an invalid Content-Type"
        )
    return detected_type


def _validate_integrity(
    artifact: ArtifactRef,
    content: bytes,
    detected_type: str | None,
    digest: bytes,
) -> None:
    _require_artifact_size(artifact.size_bytes)
    _require_artifact_size(len(content))
    _require_size(artifact.size_bytes, len(content))

    actual_digest = f"sha256:{digest.hex()}"
    if not hmac.compare_digest(actual_digest, artifact.digest):
        # The observed digest stays out of the message: the text is persisted
        # into caller-visible artifacts, so echoing it makes validation a hash
        # oracle for any file the root admits.
        raise ArtifactDigestMismatchError(
            f"artifact digest mismatch: expected {artifact.digest}"
        )

    # A detected type of `None` reaches here only for a retained `sha256-<hex>`
    # artifact, which is extensionless by design; every other undeterminable
    # path already failed closed in `_detected_media_type`.  An unknown type
    # cannot confirm the declaration, so the comparison is skipped instead of
    # made tautological.
    if detected_type is not None and _base_media_type(
        detected_type
    ) != _base_media_type(artifact.media_type):
        raise ArtifactResolutionError(
            f"artifact media type mismatch: expected {artifact.media_type}, "
            + f"got {detected_type}"
        )


def _require_artifact_size(size: int) -> None:
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ArtifactResolutionError("artifact size must be a non-negative integer")
    if size > MAX_ARTIFACT_BYTES:
        raise ArtifactResolutionError(
            f"artifact exceeds maximum size of {MAX_ARTIFACT_BYTES} bytes"
        )


def _require_size(expected: int, actual: int) -> None:
    if actual != expected:
        # The observed size stays out of the message for the same reason the
        # observed digest does: it leaks the length of any admitted file.
        raise ArtifactResolutionError(f"artifact size mismatch: expected {expected}")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ArtifactResolutionError(
                f"schema artifact contains duplicate key {key!r}"
            )
        document[key] = value
    return document


def _validate_schema(
    artifact: ArtifactRef,
    content: bytes,
    schema_validator: SchemaValidator | None,
) -> None:
    if artifact.schema_uri is None:
        return
    media_type = _base_media_type(artifact.media_type)
    if media_type != "application/json" and not media_type.endswith("+json"):
        raise ArtifactResolutionError(
            "schema validation requires a JSON artifact media type"
        )
    try:
        document = cast(
            object, json.loads(content, object_pairs_hook=_reject_duplicate_keys)
        )
    except ArtifactResolutionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactResolutionError("schema artifact is not valid JSON") from exc
    if _is_document_schema_uri(artifact.schema_uri):
        # A document URI labels a retained document that declares no contract
        # rules, not even a shape: the decision ledger is a bare JSON list.
        # Valid JSON with unique keys is every rule the label carries.
        return
    if not isinstance(document, dict):
        raise ArtifactResolutionError("schema artifact must contain a JSON object")

    try:
        validator = schema_validator or _validate_registered_schema
        validator(content, artifact.schema_uri)
    except ArtifactResolutionError:
        raise
    except ValueError as exc:
        raise ArtifactResolutionError(
            f"artifact schema mismatch: {artifact.schema_uri}"
        ) from exc


def _is_document_schema_uri(schema_uri: str) -> bool:
    from easy_cheese_schemas.schema_runtime import DOCUMENT_SCHEMA_URIS

    return schema_uri in DOCUMENT_SCHEMA_URIS


def _validate_registered_schema(content: bytes, schema_uri: str) -> None:
    from easy_cheese_schemas.schema_runtime import (
        ContractValidationError,
        REGISTERED_CONTRACT_SCHEMA_URIS,
        supported_version_for,
        validate_contract,
    )

    if schema_uri not in REGISTERED_CONTRACT_SCHEMA_URIS:
        raise ArtifactResolutionError(f"artifact schema mismatch: {schema_uri}")
    try:
        version = supported_version_for(schema_uri)
        _ = validate_contract(
            content,
            schema_uri,
            supported_version=version,
        )
    except ContractValidationError as exc:
        # Keep the reason. A bare "schema mismatch" hides which rule failed,
        # so a caller cannot tell a wrong schema from a rejected field.
        raise ArtifactResolutionError(
            f"artifact schema mismatch: {schema_uri}: {exc}"
        ) from exc


def _snapshot_matches(path: Path, expected_size: int, expected_digest: bytes) -> bool:
    """Report whether the retained copy at `path` already holds the bytes.

    The destination name is the content digest, but the name is not proof:
    a leftover of the same size under that name can hold other bytes. The
    shared reader refuses a symlink and anything that is not a regular
    file, stops at `expected_size`, and the digest read-back decides. A
    copy that fails any of those falls through to the atomic rewrite, so
    the returned path always holds the verified content.
    """

    try:
        retained = read_bounded_file(path, limit=expected_size)
    except (OSError, OverflowError, ValueError):
        return False
    return hmac.compare_digest(hashlib.sha256(retained).digest(), expected_digest)


def _restrict_permissions(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode, follow_symlinks=False)
        metadata = os.lstat(path)
    except (NotImplementedError, OSError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            f"could not enforce private permissions on {path}"
        ) from exc
    if stat.S_ISLNK(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != mode:
        raise ArtifactResolutionError(
            f"could not enforce private permissions on {path}"
        )


def restrict_open_file(fd: int, path: Path) -> None:
    """Force one open file to private `0600` permissions, or refuse.

    Every host-side writer that reveals a file it created shares this check,
    so it is public. The permission change is made on the descriptor, which
    no racing rename can redirect. A platform without `os.fchmod` falls back
    to `path`, which `mkstemp` already created private; the descriptor is
    still what the result is read back from.
    """

    fchmod = getattr(os, "fchmod", None)
    try:
        if callable(fchmod):
            _ = fchmod(fd, 0o600)
        else:
            os.chmod(path, 0o600, follow_symlinks=False)
        metadata = os.fstat(fd)
    except (NotImplementedError, OSError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            "could not enforce private permissions on retained artifact"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ArtifactResolutionError(
            "could not enforce private permissions on retained artifact"
        )


def _prepare_artifact_directory(artifact_directory: str | Path) -> Path:
    """Create, resolve, and lock down the retention root exactly once.

    The caller hoists this out of the retention itself, so one resolution
    chain prepares its root a single time instead of once per artifact.
    """

    if artifact_directory is None:  # pyright: ignore[reportUnnecessaryComparison]
        raise ArtifactResolutionError("artifact_directory is required")  # pyright: ignore[reportUnreachable]
    directory = Path(artifact_directory)
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = directory.resolve(strict=True)
        if not directory.is_dir():
            raise ArtifactResolutionError(
                f"artifact directory is not a directory: {directory}"
            )
        _restrict_permissions(directory, 0o700)
    except ArtifactResolutionError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            f"artifact directory is not writable: {directory}"
        ) from exc
    return directory


def _retain_verified_bytes(
    content: bytes, directory: Path, expected_digest: bytes
) -> str:
    _require_artifact_size(len(content))
    destination = directory / f"sha256-{expected_digest.hex()}"
    if _snapshot_matches(destination, len(content), expected_digest):
        _restrict_permissions(destination, 0o600)
        return str(destination)

    temp_fd: int | None = None
    temp_path: Path | None = None
    try:
        temp_fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=str(directory),
        )
        temp_path = Path(temp_name)
        with os.fdopen(temp_fd, "wb") as writer:
            temp_fd = None
            restrict_open_file(writer.fileno(), temp_path)
            _ = writer.write(content)
            writer.flush()
            os.fsync(writer.fileno())
        _restrict_permissions(temp_path, 0o600)
        os.replace(temp_path, destination)
        temp_path = None
        _restrict_permissions(destination, 0o600)
        return str(destination)
    except ArtifactResolutionError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            f"artifact could not be retained in {directory}"
        ) from exc
    finally:
        if temp_fd is not None:
            with contextlib.suppress(OSError):
                os.close(temp_fd)
        if temp_path is not None:
            with contextlib.suppress(OSError):
                temp_path.unlink()


def _base_media_type(media_type: str) -> str:
    return media_type.partition(";")[0].strip().lower()
