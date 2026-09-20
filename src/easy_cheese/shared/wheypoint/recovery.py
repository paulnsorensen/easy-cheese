"""Public persistence operation for nonterminal writer recovery."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import stat
import uuid
from pathlib import Path

import attrs

from easy_cheese_schemas.contracts import (
    CheckpointIntent,
    WheypointDelta,
    WheypointRecord,
)

from . import checkpoint, commit, resolve, storage

__all__ = ["RecoveryError", "RecoveryResult", "persist_checkpoint"]

_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_BINARY", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_DIRECTORY", 0)
)
_FILE_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_BINARY", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)


class RecoveryError(RuntimeError):
    """A recovery persistence operation was refused or could not complete."""


@attrs.define(frozen=True)
class RecoveryResult:
    """The authoritative recovery record and context returned to a writer."""

    work_id: str
    working_context: tuple[str, ...]
    revision_id: str


def _relative_parts(path: Path, root: Path) -> tuple[str, ...]:
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise RecoveryError(
            "checkpoint artifact path is outside the repository root"
        ) from exc
    parts = relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise RecoveryError(
            "checkpoint artifact path is not a safe repository-relative path"
        )
    return parts


@contextlib.contextmanager
def _opened_fd(
    path: Path | str, flags: int, *, dir_fd: int | None = None
):
    fd = os.open(path, flags, dir_fd=dir_fd)
    try:
        yield fd
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)


@contextlib.contextmanager
def _parent_directory(root: Path, parts: tuple[str, ...]):
    with contextlib.ExitStack() as stack:
        current_fd = -1
        try:
            current_fd = stack.enter_context(_opened_fd(root, _DIRECTORY_FLAGS))
            for part in parts[:-1]:
                try:
                    next_fd = stack.enter_context(
                        _opened_fd(part, _DIRECTORY_FLAGS, dir_fd=current_fd)
                    )
                except FileNotFoundError:
                    try:
                        os.mkdir(part, 0o755, dir_fd=current_fd)
                    except FileExistsError:
                        # Another writer created the directory after the lookup.
                        pass
                    next_fd = stack.enter_context(
                        _opened_fd(part, _DIRECTORY_FLAGS, dir_fd=current_fd)
                    )
                current_fd = next_fd
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise RecoveryError(
                    "checkpoint artifact path follows a symlink"
                ) from exc
            raise RecoveryError(
                "checkpoint artifact directory is not writable"
            ) from exc
        yield current_fd, parts[-1]


def _read_existing(root: Path, parts: tuple[str, ...]) -> bytes | None:
    try:
        with _parent_directory(root, parts) as (parent_fd, name):
            fd = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise RecoveryError("checkpoint artifact is not a regular file")
                chunks: list[bytes] = []
                while chunk := os.read(fd, 64 * 1024):
                    chunks.append(chunk)
                return b"".join(chunks)
            finally:
                os.close(fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise RecoveryError("checkpoint artifact path follows a symlink") from exc
        raise RecoveryError("checkpoint artifact cannot be read") from exc


def _write_at(root: Path, parts: tuple[str, ...], payload: bytes) -> None:
    with _parent_directory(root, parts) as (parent_fd, name):
        temp_name = f".{name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        fd = os.open(temp_name, flags, 0o600, dir_fd=parent_fd)
        try:
            with os.fdopen(fd, "wb") as stream:
                _ = stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.rename(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            os.fsync(parent_fd)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(temp_name, dir_fd=parent_fd)
            raise


def _unlink_at(root: Path, parts: tuple[str, ...]) -> None:
    with _parent_directory(root, parts) as (parent_fd, name):
        try:
            os.unlink(name, dir_fd=parent_fd)
        except FileNotFoundError:
            return
        os.fsync(parent_fd)


@contextlib.contextmanager
def _artifact_lock(root: Path, parts: tuple[str, ...]):
    with _parent_directory(root, parts) as (parent_fd, _):
        storage._lock(parent_fd, exclusive=True)  # pyright: ignore[reportPrivateUsage]
        try:
            yield
        finally:
            storage._lock(parent_fd, exclusive=False)  # pyright: ignore[reportPrivateUsage]


def _publish(root: Path, path: Path, payload: bytes) -> bytes | None:
    parts = _relative_parts(path, root)
    previous = _read_existing(root, parts)
    _write_at(root, parts, payload)
    return previous


def _rollback(root: Path, path: Path, previous: bytes | None) -> None:
    parts = _relative_parts(path, root)
    if previous is None:
        _unlink_at(root, parts)
    else:
        _write_at(root, parts, previous)


def _record_references_artifact(
    record: WheypointRecord | None, artifact_ref: str
) -> bool:
    return record is not None and any(
        link.path == artifact_ref for link in record.artifact_links
    )


def _artifact_digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _same_intent(
    delta: WheypointDelta,
    current: WheypointRecord,
    *,
    artifact_ref: str,
    artifact_payload: bytes,
    artifact_existing: bytes | None,
) -> bool:
    if delta.orientation is not None and delta.orientation != current.orientation:
        return False
    if delta.working_context is not None and list(delta.working_context) != list(
        current.working_context
    ):
        return False
    if delta.notes is not None and delta.notes != current.notes:
        return False
    if delta.next_action is not None and delta.next_action != current.next_action:
        return False
    links = delta.add_artifact_links or []
    current_links = {link.path: link for link in current.artifact_links}
    if links and not all(link.path in current_links for link in links):
        return False
    if links:
        existing = current_links.get(artifact_ref)
        if (
            existing is None
            or existing.digest != _artifact_digest(artifact_payload)
            or artifact_existing != artifact_payload
        ):
            return False
    if any(
        (
            delta.add_decisions,
            delta.add_questions,
            delta.add_blockers,
            delta.add_directives,
            delta.transitions,
            delta.decision_dossier,
            delta.remove_artifact_links,
        )
    ):
        return False
    return True


def persist_checkpoint(
    intent: CheckpointIntent,
    *,
    artifact_path: Path,
    artifact_payload: bytes,
    repository_root: Path,
    corpus_root: Path,
    project_key: str,
) -> RecoveryResult:
    """Persist one validated recovery intent and resolve its authoritative record."""

    secret_paths = checkpoint.secret_fields(intent)
    if secret_paths:
        raise RecoveryError(
            "checkpoint contains credential-like text in " + ", ".join(secret_paths)
        )
    root = Path(repository_root).absolute()
    work_id = intent.work_id
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    artifact_parts = _relative_parts(artifact_path, root)
    artifact_ref = Path(*artifact_parts).as_posix()
    with _artifact_lock(root, artifact_parts):
        try:
            current = store.read_record()
        except (ValueError, OSError) as exc:
            raise RecoveryError("current checkpoint record cannot be read") from exc
        try:
            delta = checkpoint.build_delta(intent, current)
        except checkpoint.IntentError as exc:
            raise RecoveryError(str(exc)) from exc
        existing = _read_existing(root, artifact_parts)
        if current is not None and _same_intent(
            delta,
            current,
            artifact_ref=artifact_ref,
            artifact_payload=artifact_payload,
            artifact_existing=existing,
        ):
            should_publish = False
        else:
            if (
                current is not None
                and artifact_ref in {link.path for link in current.artifact_links}
                and existing is not None
                and existing != artifact_payload
            ):
                raise RecoveryError("checkpoint artifact is already referenced")
            should_publish = True
        if should_publish:
            previous = _publish(root, artifact_path, artifact_payload)
            try:
                try:
                    _ = commit.commit(delta, store=store, artifact_root=root)
                except (commit.StaleParentError, commit.GenesisConflictError):
                    refreshed = store.read_record()
                    if refreshed is None:
                        raise RecoveryError("checkpoint retry found no current record")
                    retry_intent = attrs.evolve(
                        intent, base_revision_id=refreshed.revision_id
                    )
                    retry_delta = checkpoint.build_delta(retry_intent, refreshed)
                    _ = commit.commit(retry_delta, store=store, artifact_root=root)
            except BaseException:
                try:
                    current_after = store.read_record()
                except (ValueError, OSError) as read_error:
                    raise RecoveryError(
                        "checkpoint commit failed; artifact preserved because "
                        + "authority could not be read"
                    ) from read_error
                if not _record_references_artifact(current_after, artifact_ref):
                    try:
                        _rollback(root, artifact_path, previous)
                    except BaseException as rollback_error:
                        raise RecoveryError(
                            "checkpoint commit failed and artifact rollback failed"
                        ) from rollback_error
                raise
    resolution = resolve.resolve(
        work_id,
        corpus_root=corpus_root,
        project_key=project_key,
        workspace_root=root,
    )
    if not resolution.dispatchable or resolution.record is None:
        detail = resolution.detail or resolution.outcome.value
        raise RecoveryError(f"wheypoint is not authoritative: {detail}")
    working_context = tuple(resolution.record.working_context)
    if not working_context:
        raise RecoveryError("authoritative wheypoint has empty working context")
    return RecoveryResult(work_id, working_context, resolution.record.revision_id)
