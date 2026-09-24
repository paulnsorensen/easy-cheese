"""The `checkpoint` command and its durable pending-mirror transaction.

A note-mirrored checkpoint spans two writes -- the canonical commit and the
readable mirror beside the repository -- so a crash between them must be
resumable rather than silently doubled or lost. `_PendingMirror` is the
ledger entry that makes the second write idempotent across a retry.
"""

from __future__ import annotations

import argparse
import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import TextIO, cast

from attrs import define, evolve

from easy_cheese_schemas import (
    CheckpointIntent,
    CompactionRecord,
    Durability,
    WheypointDelta,
)

from easy_cheese.cli.envelope import Refused
from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import canonical
from easy_cheese.shared.wheypoint import checkpoint as checkpoint_mod
from easy_cheese.shared.wheypoint import commit as commit_mod
from easy_cheese.shared.wheypoint import legacy as legacy_mod
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import storage


@define(frozen=True)
class _PendingMirror:
    """A durable identity for a revision whose mirror still needs finalization."""

    request_identity: str
    request_digest: str
    revision_id: str
    target: str


def _note_dir(args: argparse.Namespace) -> Path | None:
    """Where the readable mirror goes, or None when none is to be written.

    `--no-note` refuses one outright; an explicit `--note-dir` is taken as
    given; otherwise the mirror belongs beside the repository the checkpoint
    describes, and outside a repository there is nowhere for it to belong.
    """
    if cast(bool, args.no_note):
        return None
    given = cast(str | None, args.note_dir)
    if given is not None:
        return Path(given).expanduser()
    toplevel = paths.git_toplevel()
    if toplevel is None:
        return None
    return toplevel.joinpath(*legacy_mod.NOTES_DIR_PARTS)


def read_payload(stdin: TextIO) -> object:
    try:
        return cast(object, json.loads(stdin.read()))
    except ValueError as exc:
        raise Refused("invalid-json", f"stdin is not one JSON value: {exc}") from exc


def open_store(work_id: str, *, corpus_root: Path | None = None) -> storage.WorkStore:
    try:
        return storage.WorkStore.open(work_id, corpus_root=corpus_root)
    except storage.StorageError as exc:
        raise Refused("storage-error", str(exc)) from exc


def run_checkpoint(args: argparse.Namespace, stdin: TextIO) -> dict[str, object]:
    """A semantic intent, bound to the current record and committed.

    The binding is a read outside the lock, so it settles nothing: `commit`
    re-checks the parent under the lock and refuses a delta whose record has
    moved on. This command shortens the authoring, not the checking.
    """
    payload = read_payload(stdin)
    reserved = checkpoint_mod.commit_only_fields(payload)
    if reserved:
        raise Refused(
            "commit-only-field",
            f"checkpoint does not author {', '.join(reserved)}: the runtime binds "
            + "the parent automatically. Use base_revision_id to pin a read revision. "
            + "Use checkpoint --compacted <proof-path> for a compaction proof.",
        )
    try:
        intent = records.structure(payload, CheckpointIntent, forbid_unknown=True)
    except records.RecordError as exc:
        raise Refused("invalid-intent", str(exc)) from exc
    secret = checkpoint_mod.secret_field(intent)
    if secret is not None:
        raise Refused(
            "secret-pattern",
            f"{secret} looks like a credential: a checkpoint is durable, "
            + "digest-protected text, so it cannot carry one",
        )
    proof = _compaction_proof(args)
    # The proof is part of the request: an identical intent with and without a
    # proof must not share a pending-mirror ledger entry.
    request_identity = request_identity_for(intent, proof)
    store = open_store(intent.work_id)
    try:
        current = store.read_record()
    except ValueError as exc:
        raise Refused(
            "record-unreadable",
            f"work {intent.work_id!r} has a record that cannot be read, so no "
            + f"checkpoint can be bound to it: {exc}",
        ) from exc
    try:
        delta = checkpoint_mod.build_delta(intent, current)
    except checkpoint_mod.IntentError as exc:
        raise Refused("invalid-intent", str(exc)) from exc
    if proof is not None:
        delta = evolve(delta, compacted=True, compaction=proof)
    return _promote(
        delta,
        store,
        args,
        request_identity=request_identity,
    )


def request_identity_for(
    intent: CheckpointIntent, proof: CompactionRecord | None
) -> str:
    """The pending-mirror ledger key: the intent, plus the proof when one rides with it."""
    if proof is None:
        return canonical.digest_value(records.unstructure(intent))
    return canonical.digest_value(
        {
            "intent": records.unstructure(intent),
            "compaction": records.unstructure(proof),
        }
    )


def _compaction_proof(args: argparse.Namespace) -> CompactionRecord | None:
    """The `--compacted` proof, validated before it can touch a delta."""
    path_arg = cast("str | None", args.compacted)
    if path_arg is None:
        return None
    path = Path(path_arg)
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except OSError as exc:
        raise Refused("compaction-proof-unreadable", f"{path_arg}: {exc}") from exc
    except ValueError as exc:
        raise Refused(
            "compaction-proof-unreadable", f"{path_arg} is not one JSON value: {exc}"
        ) from exc
    try:
        return records.structure(raw, CompactionRecord, forbid_unknown=True)
    except records.RecordError as exc:
        raise Refused("invalid-compaction-proof", str(exc)) from exc


def _refusal_for(exc: Exception) -> Refused:
    """The one mapping from a kernel/storage error to a reply code, both paths."""
    if isinstance(exc, commit_mod.GenesisConflictError):
        return Refused("genesis-conflict", str(exc))
    if isinstance(exc, commit_mod.StaleParentError):
        return Refused("stale-parent", str(exc))
    if isinstance(exc, commit_mod.CommitError):
        return Refused("commit-refused", str(exc))
    return Refused("storage-error", str(exc))


def _promote(
    delta: WheypointDelta,
    store: storage.WorkStore,
    args: argparse.Namespace,
    *,
    request_identity: str,
) -> dict[str, object]:
    note_dir = _note_dir(args)
    if note_dir is None:
        try:
            result = commit_mod.commit(
                delta,
                store=store,
                durability=Durability.CANONICAL_LOCAL,
            )
        except (commit_mod.CommitError, storage.StorageError) as exc:
            raise _refusal_for(exc) from exc
        return _result_payload(result, None)

    try:
        note_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise Refused(
            "note-unwritable",
            f"note directory {note_dir} cannot be created: {exc}",
        ) from exc

    try:
        current = store.read_record()
    except ValueError as exc:
        raise Refused(
            "record-unreadable",
            f"work {store.work_id!r} has a record that cannot be read: {exc}",
        ) from exc
    target = note_dir / (f"{store.work_id if current is None else current.slug}.md")
    pending = _read_pending(store, request_identity)
    if pending is not None:
        revision = store.find_complete_revision(pending.revision_id)
        if revision is not None:
            if revision.request_digest != pending.request_digest:
                raise Refused(
                    "pending-corrupt",
                    f"request ledger for {request_identity!r} names a different "
                    + f"request than revision {pending.revision_id!r}",
                )
            resume_target = note_dir / pending.target
            result = _resume_mirror(store, revision.revision_id, resume_target, pending)
            return _result_payload(result, str(resume_target))
        try:
            store.remove_pending(request_identity)
        except OSError as exc:
            raise Refused(
                "storage-error",
                f"request ledger {store.pending_path(request_identity)} cannot be "
                + f"cleared: {exc}",
            ) from exc

    request_digest = records.request_fingerprint(delta)
    pending = _PendingMirror(
        request_identity=request_identity,
        request_digest=request_digest,
        revision_id=commit_mod.revision_id_for(delta),
        target=target.name,
    )
    _write_pending(store, pending)

    try:
        result = commit_mod.commit(
            delta,
            store=store,
            durability=Durability.REPO_SNAPSHOT,
            finalize=_mirror_finalizer(target),
        )
    except _MirrorError as exc:
        _drop_uncommitted_pending(store, pending)
        raise Refused("note-unwritable", str(exc)) from exc
    except (commit_mod.CommitError, storage.StorageError) as exc:
        _drop_uncommitted_pending(store, pending)
        raise _refusal_for(exc) from exc
    _clear_pending(store, request_identity)
    return _result_payload(result, str(target))


def _mirror_finalizer(
    target: Path,
) -> Callable[[commit_mod.PendingRevision], None]:
    """The mirror finalizer: the durability this projection claims lands
    before the record is promoted.
    """

    def finalize(pending_revision: commit_mod.PendingRevision) -> None:
        try:
            storage.write_atomic(target, pending_revision.markdown.encode("utf-8"))
        except OSError as exc:
            raise _MirrorError(f"mirror {target} cannot be finalized: {exc}") from exc

    return finalize


class _MirrorError(OSError):
    """Raised when the durability finalizer cannot publish the mirror."""


def _read_pending(
    store: storage.WorkStore, request_identity: str
) -> _PendingMirror | None:
    path = store.pending_path(request_identity)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Refused(
            "storage-error", f"request ledger {path} cannot be read: {exc}"
        ) from exc
    try:
        decoded = cast(object, json.loads(raw.decode("utf-8")))
        if not isinstance(decoded, dict):
            raise ValueError("request ledger is not an object")
        payload = cast(dict[str, object], decoded)
        pending = _PendingMirror(
            request_identity=cast(str, payload["request_identity"]),
            request_digest=cast(str, payload["request_digest"]),
            revision_id=cast(str, payload["revision_id"]),
            target=cast(str, payload["target"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise Refused(
            "pending-corrupt", f"request ledger {path} is invalid: {exc}"
        ) from exc
    if pending.request_identity != request_identity:
        raise Refused("pending-corrupt", f"request ledger {path} has invalid identity")
    return pending


def _write_pending(store: storage.WorkStore, pending: _PendingMirror) -> None:
    path = store.pending_path(pending.request_identity)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        storage.write_atomic(
            path,
            canonical.canonical_bytes(
                {
                    "request_identity": pending.request_identity,
                    "request_digest": pending.request_digest,
                    "revision_id": pending.revision_id,
                    "target": pending.target,
                }
            ),
        )
    except OSError as exc:
        raise Refused(
            "note-unwritable", f"request ledger {path} cannot be written: {exc}"
        ) from exc


def _drop_uncommitted_pending(
    store: storage.WorkStore, pending: _PendingMirror
) -> None:
    if store.find_complete_revision(pending.revision_id) is not None:
        return
    with contextlib.suppress(OSError):
        store.remove_pending(pending.request_identity)


def _clear_pending(store: storage.WorkStore, request_identity: str) -> None:
    try:
        store.remove_pending(request_identity)
    except OSError as exc:
        raise Refused(
            "storage-error",
            f"request ledger {store.pending_path(request_identity)} cannot be "
            + f"cleared: {exc}",
        ) from exc


def _resume_mirror(
    store: storage.WorkStore,
    revision_id: str,
    target: Path,
    pending: _PendingMirror,
) -> commit_mod.CommitResult:
    try:
        result = commit_mod.resume_revision(
            revision_id,
            store=store,
            finalize=_mirror_finalizer(target),
        )
    except _MirrorError as exc:
        raise Refused("note-unwritable", str(exc)) from exc
    except (commit_mod.CommitError, storage.StorageError) as exc:
        raise _refusal_for(exc) from exc
    _clear_pending(store, pending.request_identity)
    return result


def _result_payload(
    result: commit_mod.CommitResult, note_path: str | None
) -> dict[str, object]:
    return {
        "note_path": note_path,
        "replayed": result.replayed,
        "work_id": result.record.work_id,
        "revision_id": result.revision.revision_id,
        "revision_number": result.revision.revision_number,
        "parent_revision_id": result.revision.parent_revision_id,
        "status": result.record.status.value,
        "durability": result.projection.durability.value,
        "projection_path": result.revision.projection_path,
        "record": records.unstructure(result.record),
        "revision": records.unstructure(result.revision),
        "markdown": result.markdown,
    }
