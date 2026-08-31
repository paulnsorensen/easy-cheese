from __future__ import annotations

import errno
import hashlib
import hmac
import json
import mimetypes
import os
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

__all__ = [
    "MAX_ARTIFACT_BYTES",
    "ArtifactResolutionError",
    "ResolvedAgentArtifact",
    "read_repository_artifact",
    "resolve_artifact",
    "resolve_verified_bytes",
]

SchemaValidator = Callable[[bytes, str], None]

_READ_CHUNK_BYTES = 64 * 1024

_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 5


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:  # pyright: ignore[reportImplicitOverride]
        return None


urlopen = build_opener(_NoRedirectHandler()).open


class ArtifactResolutionError(ValueError):
    pass


@define(frozen=True)
class ResolvedAgentArtifact:
    role: str
    path: str
    media_type: str

def resolve_artifact(
    artifact: ArtifactRef,
    *,
    repository_root: str | Path = ".",
    artifact_directory: str | Path,
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
        path = _resolve_file_path(parsed.netloc, parsed.path)
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
    )


def resolve_verified_bytes(
    artifact: ArtifactRef,
    content: bytes,
    detected_type: str,
    artifact_directory: str | Path,
) -> ResolvedAgentArtifact:
    _validate_integrity(artifact, content, detected_type)
    _validate_schema(artifact, content)
    path = _retain_verified_bytes(content, artifact_directory)
    return _agent_view(artifact, path)



def _agent_view(artifact: ArtifactRef, path: str) -> ResolvedAgentArtifact:
    return ResolvedAgentArtifact(
        role=artifact.role,
        path=path,
        media_type=artifact.media_type,
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
) -> tuple[bytes, str]:
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
            try:
                os.close(fd)
            except OSError:
                pass
        if root_fd is not None:
            try:
                os.close(root_fd)
            except OSError:
                pass

    detected_type, _encoding = mimetypes.guess_type(display_path.name)
    if detected_type is None:
        raise ArtifactResolutionError(
            f"artifact media type cannot be determined from path: {display_path}"
        )
    return content, detected_type


def _resolve_file_path(authority: str, uri_path: str) -> Path:
    if authority not in {"", "localhost"}:
        raise ArtifactResolutionError("local file URI must not name a remote host")
    path = Path(unquote(uri_path))
    if not path.is_absolute():
        raise ArtifactResolutionError("file URI must name an absolute path")
    return path


def _read_local(path: Path, expected_size: int) -> tuple[bytes, str]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    fd: int | None = None
    try:
        fd = os.open(path, flags)
        content = _read_descriptor(fd, expected_size, path)
    except ArtifactResolutionError:
        raise
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(f"artifact is not readable: {path}") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

    detected_type, _encoding = mimetypes.guess_type(path.name)
    if detected_type is None:
        raise ArtifactResolutionError(
            f"artifact media type cannot be determined from path: {path}"
        )
    return content, detected_type


def _read_descriptor(
    fd: int,
    expected_size: int | None,
    display_path: Path,
) -> bytes:
    if expected_size is not None:
        _require_artifact_size(expected_size)
    try:
        metadata = os.fstat(fd)
    except (OSError, ValueError) as exc:
        raise ArtifactResolutionError(
            f"artifact is not readable: {display_path}"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ArtifactResolutionError(
            f"artifact is not a regular file: {display_path}"
        )
    _require_artifact_size(metadata.st_size)
    if expected_size is not None:
        _require_size(expected_size, metadata.st_size)
    try:
        return _read_bounded(
            lambda amount: os.read(fd, amount),
            metadata.st_size,
            display_path,
        )
    except ArtifactResolutionError:
        raise
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            f"artifact is not readable: {display_path}"
        ) from exc


def _read_bounded(
    reader: Callable[[int], bytes],
    expected_size: int,
    display_path: Path,
) -> bytes:
    _require_artifact_size(expected_size)
    content = bytearray()
    while len(content) <= expected_size:
        amount = min(_READ_CHUNK_BYTES, expected_size - len(content) + 1)
        chunk = reader(amount)
        if not chunk:
            break
        if not isinstance(chunk, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ArtifactResolutionError(
                f"artifact reader returned invalid data: {display_path}"
            )
        content.extend(chunk)
        if len(content) > MAX_ARTIFACT_BYTES:
            raise ArtifactResolutionError(
                f"artifact exceeds maximum size of {MAX_ARTIFACT_BYTES} bytes"
            )
        if len(content) > expected_size:
            break
    _require_size(expected_size, len(content))
    return bytes(content)


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
                try:
                    exc.close()
                except OSError:
                    pass
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
        raise ArtifactResolutionError(
            "HTTPS artifact redirected outside URI policy"
        )
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
        raise ArtifactResolutionError(
            "HTTPS artifact URI has an invalid port"
        ) from exc
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
    artifact: ArtifactRef, content: bytes, detected_type: str
) -> None:
    _require_artifact_size(artifact.size_bytes)
    _require_artifact_size(len(content))
    _require_size(artifact.size_bytes, len(content))

    actual_digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
    if not hmac.compare_digest(actual_digest, artifact.digest):
        raise ArtifactResolutionError(
            f"artifact digest mismatch: expected {artifact.digest}, got {actual_digest}"
        )

    if _base_media_type(detected_type) != _base_media_type(artifact.media_type):
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
        raise ArtifactResolutionError(
            f"artifact size mismatch: expected {expected}, got {actual}"
        )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ArtifactResolutionError(f"schema artifact contains duplicate key {key!r}")
        document[key] = value
    return document


def _validate_schema(artifact: ArtifactRef, content: bytes) -> None:
    if artifact.schema_uri is None:
        return
    media_type = _base_media_type(artifact.media_type)
    if media_type != "application/json" and not media_type.endswith("+json"):
        raise ArtifactResolutionError(
            "schema validation requires a JSON artifact media type"
        )
    try:
        document = cast(object, json.loads(content, object_pairs_hook=_reject_duplicate_keys))
    except ArtifactResolutionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactResolutionError("schema artifact is not valid JSON") from exc
    if not isinstance(document, dict):
        raise ArtifactResolutionError("schema artifact must contain a JSON object")

    try:
        validator = schema_validator or _validate_registered_schema
        _validate_registered_schema(content, artifact.schema_uri)
    except ArtifactResolutionError:
        raise
    except ValueError as exc:
        raise ArtifactResolutionError(
            f"artifact schema mismatch: {artifact.schema_uri}"
        ) from exc


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
        if version is None:
            raise KeyError(schema_uri)
        _ = validate_contract(
            content,
            schema_uri,
            supported_version=version,
        )
    except (ContractValidationError, KeyError) as exc:
        raise ArtifactResolutionError(
            f"artifact schema mismatch: {schema_uri}"
        ) from exc


def _snapshot_matches(
    path: Path, content: bytes, expected_digest: bytes
) -> bool:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    fd: int | None = None
    try:
        fd = os.open(path, flags)
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            return False
        if metadata.st_size != len(content):
            return False
        observed = _read_bounded(
            lambda amount: os.read(fd, amount),
            len(content),
            path,
        )
        return hmac.compare_digest(hashlib.sha256(observed).digest(), expected_digest)
    except (ArtifactResolutionError, OSError, OverflowError, ValueError):
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


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


def _restrict_open_file(fd: int, _path: Path) -> None:
    fchmod = getattr(os, "fchmod", None)
    if not callable(fchmod):
        raise ArtifactResolutionError("private file permissions are unavailable")
    try:
        _ = fchmod(fd, 0o600)
        metadata = os.fstat(fd)
    except (NotImplementedError, OSError, TypeError, ValueError) as exc:
        raise ArtifactResolutionError(
            "could not enforce private permissions on retained artifact"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ArtifactResolutionError(
            "could not enforce private permissions on retained artifact"
        )


def _retain_verified_bytes(content: bytes, artifact_directory: str | Path) -> str:
    if artifact_directory is None:  # pyright: ignore[reportUnnecessaryComparison]
        raise ArtifactResolutionError("artifact_directory is required")  # pyright: ignore[reportUnreachable]
    _require_artifact_size(len(content))
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

    expected_digest = hashlib.sha256(content).digest()
    destination = directory / f"sha256-{expected_digest.hex()}"
    if _snapshot_matches(destination, content, expected_digest):
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
            _restrict_open_file(writer.fileno(), temp_path)
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
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def _base_media_type(media_type: str) -> str:
    return media_type.partition(";")[0].strip().lower()
