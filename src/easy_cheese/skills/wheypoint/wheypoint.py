"""The five commands the bundle exposes: checkpoint, commit, resolve, show, lint.

This module is a mouth, not a brain. Every decision it reports was made by
`commit`, `resolve`, or `lint`; nothing here parses a projection, compares a
revision, or decides what is dispatchable, because a second implementation of
any of those would be a second answer to a question the kernel already answers.

The contract with a caller is that *one line of JSON on stdout* is the whole
reply, success or failure. A refusal is an answer too, so it is emitted in the
same place and the same shape -- `{"ok": false, "command": ..., "error":
{"code": ..., "message": ...}}` -- and never as a traceback, which no caller
can parse. The exit code carries the same news for a shell:

| exit | meaning                                                          |
|------|------------------------------------------------------------------|
| 0    | the command answered; `ok` is true                                |
| 1    | the command refused; `error.code` says why                        |
| 2    | the invocation itself was wrong (unknown command, bad arguments)  |

A resolution that is gated, ambiguous, or not found is an *answer* about the
corpus, so it exits 0 with `ok: true` and the outcome in the payload; only a
reference that could not be interpreted at all is a refusal. Lint findings are
answers by the same rule.

All five commands live in this one module because the bundle dispatcher gives
each subcommand its own entry point and rewrites `sys.argv[0]` to the
subcommand name -- so the command is read from `argv[0]` first, and from
`argv[1]` when the module is run directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn, TextIO, cast, override

from attrs import define

from easy_cheese_schemas import Durability, WheypointDelta

from easy_cheese.shared import paths

from . import canonical
from . import checkpoint as checkpoint_mod
from . import commit as commit_mod
from . import legacy as legacy_mod
from . import lint as lint_mod
from . import records
from . import resolve as resolve_mod
from . import storage

COMMANDS = ("checkpoint", "commit", "resolve", "show", "lint")

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2


class _Refused(Exception):
    """A command that has an error shape to report rather than a payload."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code: str = code


@define(frozen=True)
class _PendingMirror:
    """A durable identity for a revision whose mirror still needs finalization."""

    request_identity: str
    request_digest: str
    revision_id: str
    target: str


class _BadUsage(Exception):
    """argparse's complaint, raised instead of printed so it can be JSON."""


class _Parser(argparse.ArgumentParser):
    @override
    def error(self, message: str) -> NoReturn:
        raise _BadUsage(message)


def _parser(command: str) -> _Parser:
    parser = _Parser(prog=f"wheypoint.pyz {command}")
    if command in ("checkpoint", "commit"):
        _ = parser.add_argument(
            "--note-dir",
            dest="note_dir",
            default=None,
            help=(
                "directory the readable projection is mirrored into "
                + f"(default: <git toplevel>/{'/'.join(legacy_mod.NOTES_DIR_PARTS)})"
            ),
        )
        _ = parser.add_argument(
            "--no-note",
            dest="no_note",
            action="store_true",
            help="write no mirror; the checkpoint stays canonical-local",
        )
    elif command == "resolve":
        _ = parser.add_argument(
            "--ref",
            required=True,
            help="an absolute projection path, a work id, or a slug",
        )
        _ = parser.add_argument(
            "--legacy",
            action="store_true",
            help="resolve a pre-kernel .cheese/notes/<slug>.md instead",
        )
    elif command == "show":
        _ = parser.add_argument("--work-id", required=True, dest="work_id")
    elif command == "lint":
        _ = parser.add_argument("path", help="path to a rendered projection document")
    return parser


def _findings(findings: tuple[lint_mod.LintFinding, ...]) -> list[dict[str, str]]:
    return [
        {"code": finding.code.value, "detail": finding.detail} for finding in findings
    ]


def _maybe(obj: object) -> dict[str, object] | None:
    return None if obj is None else records.unstructure(obj)


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


def _payload(stdin: TextIO) -> object:
    try:
        return cast(object, json.loads(stdin.read()))
    except ValueError as exc:
        raise _Refused("invalid-json", f"stdin is not one JSON value: {exc}") from exc


def _open(work_id: str) -> storage.WorkStore:
    try:
        return storage.WorkStore.open(work_id)
    except storage.StorageError as exc:
        raise _Refused("storage-error", str(exc)) from exc


def _run_commit(args: argparse.Namespace, stdin: TextIO) -> dict[str, object]:
    payload = _payload(stdin)
    try:
        delta = records.structure(payload, WheypointDelta)
    except records.RecordError as exc:
        raise _Refused("invalid-delta", str(exc)) from exc
    return _promote(
        delta,
        _open(delta.work_id),
        args,
        request_identity=records.request_fingerprint(delta),
    )


def _run_checkpoint(args: argparse.Namespace, stdin: TextIO) -> dict[str, object]:
    """A semantic intent, bound to the current record and committed.

    The binding is a read outside the lock, so it settles nothing: `commit`
    re-checks the parent under the lock and refuses a delta whose record has
    moved on. This command shortens the authoring, not the checking.
    """
    payload = _payload(stdin)
    reserved = checkpoint_mod.commit_only_fields(payload)
    if reserved:
        raise _Refused(
            "commit-only-field",
            f"checkpoint does not author {', '.join(reserved)}: the parent is "
            + "bound from the record, and a compaction record is a proof a "
            + "compacted session has to supply -- author those with commit",
        )
    unknown = checkpoint_mod.unknown_fields(payload)
    if unknown:
        raise _Refused(
            "invalid-intent",
            f"checkpoint does not accept {', '.join(unknown)}: the record has "
            + "no field for that data, so accepting the key would drop it",
        )
    try:
        intent = records.structure(payload, checkpoint_mod.CheckpointIntent)
    except records.RecordError as exc:
        raise _Refused("invalid-intent", str(exc)) from exc
    request_identity = canonical.digest_value(records.unstructure(intent))
    store = _open(intent.work_id)
    try:
        current = store.read_record()
    except ValueError as exc:
        raise _Refused(
            "record-unreadable",
            f"work {intent.work_id!r} has a record that cannot be read, so no "
            + f"checkpoint can be bound to it: {exc}",
        ) from exc
    try:
        delta = checkpoint_mod.build_delta(intent, current)
    except checkpoint_mod.IntentError as exc:
        raise _Refused("invalid-intent", str(exc)) from exc
    return _promote(
        delta,
        store,
        args,
        request_identity=request_identity,
    )


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
        except commit_mod.GenesisConflictError as exc:
            raise _Refused("genesis-conflict", str(exc)) from exc
        except commit_mod.StaleParentError as exc:
            raise _Refused("stale-parent", str(exc)) from exc
        except commit_mod.CommitError as exc:
            raise _Refused("commit-refused", str(exc)) from exc
        except storage.StorageError as exc:
            raise _Refused("storage-error", str(exc)) from exc
        return _result_payload(result, None)

    try:
        note_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _Refused(
            "note-unwritable",
            f"note directory {note_dir} cannot be created: {exc}",
        ) from exc

    try:
        current = store.read_record()
    except ValueError as exc:
        raise _Refused(
            "record-unreadable",
            f"work {store.work_id!r} has a record that cannot be read: {exc}",
        ) from exc
    target = note_dir / (f"{store.work_id if current is None else current.slug}.md")
    pending = _read_pending(store, request_identity)
    if pending is not None:
        revision = store.find_complete_revision(pending.revision_id)
        if revision is not None:
            if revision.request_digest != pending.request_digest:
                raise _Refused(
                    "pending-corrupt",
                    f"request ledger for {request_identity!r} names a different "
                    + f"request than revision {pending.revision_id!r}",
                )
            target = Path(pending.target)
            result = _resume_mirror(store, revision.revision_id, target, pending)
            return _result_payload(result, str(target))
        try:
            store.remove_pending(request_identity)
        except OSError as exc:
            raise _Refused(
                "storage-error",
                f"request ledger {store.pending_path(request_identity)} cannot be "
                + f"cleared: {exc}",
            ) from exc

    request_digest = records.request_fingerprint(delta)
    pending = _PendingMirror(
        request_identity=request_identity,
        request_digest=request_digest,
        revision_id=commit_mod.revision_id_for(delta),
        target=str(target.resolve()),
    )
    _write_pending(store, pending)

    def finalize(pending_revision: commit_mod.PendingRevision) -> None:
        # The mirror is the durability this projection claims, so it lands
        # before the record is promoted. The request ledger is cleared only
        # after the promotion succeeds.
        try:
            storage.write_atomic(target, pending_revision.markdown.encode("utf-8"))
        except OSError as exc:
            raise _MirrorError(f"mirror {target} cannot be finalized: {exc}") from exc

    try:
        result = commit_mod.commit(
            delta,
            store=store,
            durability=Durability.REPO_SNAPSHOT,
            finalize=finalize,
        )
    except _MirrorError as exc:
        _drop_uncommitted_pending(store, pending)
        raise _Refused("note-unwritable", str(exc)) from exc
    except commit_mod.GenesisConflictError as exc:
        _drop_uncommitted_pending(store, pending)
        raise _Refused("genesis-conflict", str(exc)) from exc
    except commit_mod.StaleParentError as exc:
        _drop_uncommitted_pending(store, pending)
        raise _Refused("stale-parent", str(exc)) from exc
    except commit_mod.CommitError as exc:
        _drop_uncommitted_pending(store, pending)
        raise _Refused("commit-refused", str(exc)) from exc
    except storage.StorageError as exc:
        _drop_uncommitted_pending(store, pending)
        raise _Refused("storage-error", str(exc)) from exc
    _clear_pending(store, request_identity)
    return _result_payload(result, str(target))


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
        raise _Refused(
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
        raise _Refused(
            "pending-corrupt", f"request ledger {path} is invalid: {exc}"
        ) from exc
    if (
        pending.request_identity != request_identity
        or not Path(pending.target).is_absolute()
    ):
        raise _Refused("pending-corrupt", f"request ledger {path} has invalid identity")
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
        raise _Refused(
            "note-unwritable", f"request ledger {path} cannot be written: {exc}"
        ) from exc


def _drop_uncommitted_pending(
    store: storage.WorkStore, pending: _PendingMirror
) -> None:
    if store.find_complete_revision(pending.revision_id) is not None:
        return
    try:
        store.remove_pending(pending.request_identity)
    except OSError:
        pass


def _clear_pending(store: storage.WorkStore, request_identity: str) -> None:
    try:
        store.remove_pending(request_identity)
    except OSError as exc:
        raise _Refused(
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
    def finalize(pending_revision: commit_mod.PendingRevision) -> None:
        try:
            storage.write_atomic(target, pending_revision.markdown.encode("utf-8"))
        except OSError as exc:
            raise _MirrorError(f"mirror {target} cannot be finalized: {exc}") from exc

    try:
        result = commit_mod.resume_revision(
            revision_id,
            store=store,
            finalize=finalize,
        )
    except _MirrorError as exc:
        raise _Refused("note-unwritable", str(exc)) from exc
    except (commit_mod.CommitError, storage.StorageError) as exc:
        raise _Refused("storage-error", str(exc)) from exc
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


def _run_show(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    work_id = cast(str, args.work_id)
    try:
        store = storage.WorkStore.open(work_id)
    except storage.StorageError as exc:
        raise _Refused("storage-error", str(exc)) from exc
    record = store.read_record()
    if record is None:
        raise _Refused(
            "record-missing",
            f"work {work_id!r} has no record at {store.record_path}",
        )
    return {
        "work_id": record.work_id,
        "status": record.status.value,
        "revision_id": record.revision_id,
        "revision_number": record.revision_number,
        "record": records.unstructure(record),
    }


def _run_resolve(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    ref = cast(str, args.ref)
    legacy_flag = cast(bool, args.legacy)
    resolution = (
        resolve_mod.resolve_legacy(ref, start=Path.cwd())
        if legacy_flag
        else resolve_mod.resolve(ref)
    )
    if resolution.outcome is resolve_mod.ResolutionOutcome.ERROR:
        raise _Refused(
            "invalid-reference",
            resolution.detail or f"reference {ref!r} could not be interpreted",
        )
    return {
        "ref": ref,
        "outcome": resolution.outcome.value,
        "dispatchable": resolution.dispatchable,
        "source": None if resolution.source is None else resolution.source.value,
        "work_id": resolution.work_id,
        "record": _maybe(resolution.record),
        "projection": _maybe(resolution.projection),
        "findings": _findings(resolution.findings),
        "matches": list(resolution.matches),
        "searched": list(resolution.searched),
        "legacy_note": (
            None if resolution.legacy_note is None else str(resolution.legacy_note)
        ),
        "legacy_slug": _maybe(resolution.legacy_slug),
        "detail": resolution.detail,
    }


def _run_lint(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    path = cast(str, args.path)
    report = lint_mod.lint_projection_file(path)
    return {
        "path": path,
        "clean": report.ok,
        "findings": _findings(report.findings),
        "projection": _maybe(report.projection),
    }


_RUNNERS = {
    "checkpoint": _run_checkpoint,
    "commit": _run_commit,
    "resolve": _run_resolve,
    "show": _run_show,
    "lint": _run_lint,
}


def _command_of(argv: list[str]) -> tuple[str | None, list[str]]:
    """The subcommand, read from the name it was invoked as, then from argv.

    The bundle gives every subcommand its own entry point into this one module
    and rewrites `argv[0]` to the subcommand name; running the module directly
    leaves `argv[0]` as the file, so the name is looked for in `argv[1]` next.
    """
    invoked = Path(argv[0]).name if argv else ""
    if invoked.endswith(".py"):
        invoked = invoked[: -len(".py")]
    if invoked in COMMANDS:
        return invoked, list(argv[1:])
    if len(argv) >= 2 and argv[1] in COMMANDS:
        return argv[1], list(argv[2:])
    return None, []


def _emit(stdout: TextIO, payload: dict[str, object]) -> None:
    _ = stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def _refuse(stdout: TextIO, command: str, code: str, message: str, status: int) -> int:
    _emit(
        stdout,
        {
            "ok": False,
            "command": command,
            "error": {"code": code, "message": message},
        },
    )
    return status


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    argv2: list[str] = sys.argv if argv is None else argv
    stdin2: TextIO = sys.stdin if stdin is None else stdin
    stdout2: TextIO = sys.stdout if stdout is None else stdout

    command, rest = _command_of(argv2)
    if command is None:
        return _refuse(
            stdout2,
            "unknown",
            "usage",
            f"expected one of {', '.join(COMMANDS)}",
            EXIT_USAGE,
        )
    try:
        args = _parser(command).parse_args(rest)
    except _BadUsage as exc:
        return _refuse(stdout2, command, "usage", str(exc), EXIT_USAGE)
    try:
        payload = _RUNNERS[command](args, stdin2)
    except _Refused as exc:
        return _refuse(stdout2, command, exc.code, str(exc), EXIT_REFUSED)
    except Exception as exc:  # noqa: BLE001 - a traceback is not a reply
        return _refuse(
            stdout2,
            command,
            "internal-error",
            f"{type(exc).__name__}: {exc}",
            EXIT_REFUSED,
        )
    _emit(stdout2, {"ok": True, "command": command, **payload})
    return EXIT_OK


def _bundle_main(command: str, argv: list[str]) -> int:
    return main([command, *argv])


def checkpoint_main(argv: list[str]) -> int:  # noqa: V103
    return _bundle_main("checkpoint", argv)


def commit_main(argv: list[str]) -> int:  # noqa: V103
    return _bundle_main("commit", argv)


def resolve_main(argv: list[str]) -> int:  # noqa: V103
    return _bundle_main("resolve", argv)


def show_main(argv: list[str]) -> int:  # noqa: V103
    return _bundle_main("show", argv)


def lint_main(argv: list[str]) -> int:  # noqa: V103
    return _bundle_main("lint", argv)


if __name__ == "__main__":
    sys.exit(main())
