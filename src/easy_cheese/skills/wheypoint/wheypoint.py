"""The nine commands the bundle exposes: checkpoint, validate, schema, resolve, show, lint, list, log, turns.

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

All nine commands live in this one module because the bundle dispatcher gives
each subcommand its own entry point and rewrites `sys.argv[0]` to the
subcommand name -- so the command is read from `argv[0]` first, and from
`argv[1]` when the module is run directly.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import json
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, TextIO, cast, override

from attrs import define, evolve

from easy_cheese_schemas import (
    CheckpointIntent,
    CompactionRecord,
    Durability,
    WheypointDelta,
    load,
    registered_contracts,
)
from easy_cheese_schemas import schema_runtime

from easy_cheese.shared import paths

from . import canonical
from . import checkpoint as checkpoint_mod
from . import commit as commit_mod
from . import legacy as legacy_mod
from . import lint as lint_mod
from . import projection
from . import records
from . import resolve as resolve_mod
from . import storage
from . import transcript

COMMANDS = (
    "checkpoint",
    "validate",
    "schema",
    "resolve",
    "show",
    "lint",
    "list",
    "log",
    "turns",
)

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3


class _Refused(Exception):
    """A command that has an error shape to report rather than a payload."""

    def __init__(self, code: str, message: str, extra: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code: str = code
        self.extra: dict[str, object] = {} if extra is None else extra


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
    if command == "checkpoint":
        _ = parser.add_argument(
            "--compacted",
            dest="compacted",
            default=None,
            metavar="PROOF_JSON",
            help=(
                "path to a caller-authored CompactionRecord proving the session "
                + "rehydrated from the current revision before writing"
            ),
        )
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
    elif command == "schema":
        _ = parser.add_argument("slug", help="a registered contract slug, e.g. checkpoint-intent")
    elif command in ("list", "log"):
        _ = parser.add_argument(
            "--corpus-root",
            dest="corpus_root",
            default=None,
            help="the per-project corpus root (default: the project's own corpus)",
        )
        if command == "log":
            _ = parser.add_argument("--work-id", required=True, dest="work_id")
    elif command == "turns":
        _ = parser.add_argument("--transcript", default=None, help="path to a session .jsonl transcript")
        _ = parser.add_argument("--session", default=None, help="session id under the derived projects directory")
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


def _open(work_id: str, *, corpus_root: Path | None = None) -> storage.WorkStore:
    try:
        return storage.WorkStore.open(work_id, corpus_root=corpus_root)
    except storage.StorageError as exc:
        raise _Refused("storage-error", str(exc)) from exc


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
    try:
        intent = records.structure(payload, CheckpointIntent, forbid_unknown=True)
    except records.RecordError as exc:
        raise _Refused("invalid-intent", str(exc)) from exc
    secret = checkpoint_mod.secret_field(intent)
    if secret is not None:
        raise _Refused(
            "secret-pattern",
            f"{secret} looks like a credential: a checkpoint is durable, "
            + "digest-protected text, so it cannot carry one",
        )
    proof = _compaction_proof(args)
    # The proof is part of the request: an identical intent with and without a
    # proof must not share a pending-mirror ledger entry.
    request_identity = request_identity_for(intent, proof)
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
    if proof is not None:
        delta = evolve(delta, compacted=True, compaction=proof)
    return _promote(
        delta,
        store,
        args,
        request_identity=request_identity,
    )


def request_identity_for(intent: CheckpointIntent, proof: CompactionRecord | None) -> str:
    """The pending-mirror ledger key: the intent, plus the proof when one rides with it."""
    if proof is None:
        return canonical.digest_value(records.unstructure(intent))
    return canonical.digest_value(
        {"intent": records.unstructure(intent), "compaction": records.unstructure(proof)}
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
        raise _Refused("compaction-proof-unreadable", f"{path_arg}: {exc}") from exc
    except ValueError as exc:
        raise _Refused("compaction-proof-unreadable", f"{path_arg} is not one JSON value: {exc}") from exc
    try:
        return records.structure(raw, CompactionRecord, forbid_unknown=True)
    except records.RecordError as exc:
        raise _Refused("invalid-compaction-proof", str(exc)) from exc


def _refusal_for(exc: Exception) -> _Refused:
    """The one mapping from a kernel/storage error to a reply code, both paths."""
    if isinstance(exc, commit_mod.GenesisConflictError):
        return _Refused("genesis-conflict", str(exc))
    if isinstance(exc, commit_mod.StaleParentError):
        return _Refused("stale-parent", str(exc))
    if isinstance(exc, commit_mod.CommitError):
        return _Refused("commit-refused", str(exc))
    return _Refused("storage-error", str(exc))


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
            resume_target = note_dir / pending.target
            result = _resume_mirror(store, revision.revision_id, resume_target, pending)
            return _result_payload(result, str(resume_target))
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
        raise _Refused("note-unwritable", str(exc)) from exc
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
    if pending.request_identity != request_identity:
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
    with contextlib.suppress(OSError):
        store.remove_pending(pending.request_identity)


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
    try:
        result = commit_mod.resume_revision(
            revision_id,
            store=store,
            finalize=_mirror_finalizer(target),
        )
    except _MirrorError as exc:
        raise _Refused("note-unwritable", str(exc)) from exc
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


def _run_show(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    work_id = cast(str, args.work_id)
    store = _open(work_id)
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


def _run_validate(args: argparse.Namespace, stdin: TextIO) -> dict[str, object]:
    """Schema-only dry run: every problem, no store opened (AC-11)."""
    _ = args
    payload = _payload(stdin)
    if not isinstance(payload, dict):
        raise _Refused(
            "invalid-intent",
            f"a checkpoint intent must be a JSON object, not {type(payload).__name__}",
        )
    intent_payload = cast("dict[str, object]", payload)
    problems = [
        f"{name} belongs to the compaction proof or the parent binding: pass it "
        + "through --compacted or let the runtime bind it"
        for name in checkpoint_mod.commit_only_fields(intent_payload)
    ]
    scrubbed = {
        key: value
        for key, value in cast(dict[str, object], payload).items()
        if key not in checkpoint_mod.COMMIT_ONLY_FIELDS
    }
    loaded = load(scrubbed, CheckpointIntent, strict=True, forbid_unknown=True)
    problems.extend(loaded.problems)
    if loaded.value is not None:
        problems.extend(f"{hit} looks like a credential" for hit in checkpoint_mod.secret_fields(loaded.value))
        # The same delta the checkpoint would build, against no record: every
        # NextAction and delta invariant fires here, with the store untouched.
        problems.extend(checkpoint_mod.delta_problems(loaded.value, None))
    if problems:
        raise _Refused("invalid-intent", "; ".join(problems), {"problems": problems})
    return {"valid": True, "work_id": loaded.value.work_id if loaded.value else None}


def _run_schema(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    """The JSON Schema for one registered contract, so no one unzips the bundle (AC-12)."""
    slug = cast(str, args.slug)
    table = dict(registered_contracts())
    if slug not in table:
        raise _Refused(
            "unknown-contract",
            f"no contract is registered as {slug!r}; known: {', '.join(sorted(table))}",
            {"known": sorted(table)},
        )
    document = cast(dict[str, object], json.loads(schema_runtime.schema_bytes(table[slug])))
    return {"slug": slug, "schema": document}


def _corpus_root(args: argparse.Namespace) -> Path:
    root_arg = cast("str | None", args.corpus_root)
    return Path(root_arg) if root_arg is not None else paths.project_corpus_root()


def _tsv_lines(
    items: list[dict[str, object]],
    columns: tuple[str | tuple[str, Callable[[object], str]], ...],
) -> list[str]:
    """One tab-separated line per item; a missing column key renders as `-`."""
    lines: list[str] = []
    for item in items:
        cells: list[str] = []
        for column in columns:
            key, formatter = column if isinstance(column, tuple) else (column, str)
            cell = "-" if key not in item else formatter(item[key])
            cells.append(projection.escape(cell, tab=True))
        lines.append("\t".join(cells))
    return lines


def _run_list(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    """One line per work item under the corpus root (AC-13)."""
    root = _corpus_root(args)
    items: list[dict[str, object]] = []
    for store in storage.WorkStore.enumerate(root):
        work_id = store.work_id
        try:
            record = store.read_record()
        except (storage.StorageError, records.RecordError, ValueError) as exc:
            items.append(
                {"work_id": work_id, "status": "unreadable", "unreadable": str(exc), "orientation": str(exc)}
            )
            continue
        if record is None:
            items.append({"work_id": work_id, "status": "no-record", "no_record": True})
            continue
        head = record.orientation.strip().partition("\n")[0]
        items.append(
            {
                "work_id": record.work_id,
                "revision_number": record.revision_number,
                "status": record.status.value,
                "next": record.next_action.move.value,
                "orientation": head,
            }
        )
    lines = _tsv_lines(items, ("work_id", "revision_number", "status", "next", "orientation"))
    return {"corpus_root": str(root), "items": items, "lines": lines}


def _run_log(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    """One line per complete revision, oldest first (AC-14)."""
    work_id = cast(str, args.work_id)
    store = _open(work_id, corpus_root=_corpus_root(args))
    scan = store.revisions()
    files, skipped = scan.files, scan.skipped
    if not files and store.read_record() is None:
        raise _Refused("record-missing", f"work {work_id!r} has no record at {store.record_path}")
    if not files and skipped:
        raise _Refused(
            "store-inconsistent",
            f"work {work_id!r} has a record but every revision was dropped: {'; '.join(skipped)}",
        )
    entries: list[dict[str, object]] = []
    for file in files:
        revision = file.revision
        captured = (
            revision.session_provenance.captured_at
            if revision.session_provenance is not None
            and revision.session_provenance.captured_at is not None
            else "-"
        )
        entries.append(
            {
                "revision_number": revision.revision_number,
                "revision_id": revision.revision_id,
                "captured_at": captured,
                "additions": len(revision.applied_additions),
                "transitions": len(revision.applied_transitions),
                "compacted": revision.compaction is not None,
            }
        )
    lines = _tsv_lines(
        entries,
        (
            "revision_number",
            "revision_id",
            "captured_at",
            ("additions", lambda n: f"+{n}"),
            ("transitions", lambda n: f"~{n}"),
            ("compacted", lambda c: "compacted" if c else "-"),
        ),
    )
    unreadable = [
        {"path": path, "reason": reason}
        for path, _, reason in (entry.partition(": ") for entry in skipped)
    ]
    return {"work_id": work_id, "revisions": entries, "lines": lines, "unreadable": unreadable}


def _run_turns(args: argparse.Namespace, _stdin: TextIO) -> dict[str, object]:
    """The user's own turns from a session transcript (AC-27, AC-28)."""
    transcript_arg = cast("str | None", args.transcript)
    session = cast("str | None", args.session)
    if transcript_arg is not None:
        path = Path(transcript_arg)
    else:
        directory = transcript.projects_dir(Path.cwd())
        if session is None:
            stamped: list[tuple[float | None, str]] = []
            for candidate in directory.glob("*.jsonl"):
                try:
                    mtime: float | None = candidate.stat().st_mtime
                except OSError:
                    mtime = None
                stamped.append((mtime, candidate.stem))
            listing = [
                {
                    "session": stem,
                    "modified": (
                        None
                        if mtime is None
                        else _dt.datetime.fromtimestamp(mtime, tz=_dt.timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        )
                    ),
                }
                for mtime, stem in sorted(
                    stamped, key=lambda pair: (pair[0] is not None, pair[0] or 0.0), reverse=True
                )
            ]
            raise _Refused(
                "session-required",
                f"{len(listing)} transcript(s) under {directory}: pass --session <id> "
                + "(never guessed by recency) or --transcript <path>",
                {"projects_dir": str(directory), "candidates": listing},
            )
        if transcript.SESSION_ID_RE.fullmatch(session) is None:
            raise _Refused("invalid-session", f"session id {session!r} must be one safe file-name segment")
        path = directory / f"{session}.jsonl"
    if not path.is_file():
        raise _Refused("transcript-missing", f"no transcript at {path}", {"path": str(path)})
    turns, skipped = transcript.user_turns(path)
    rows: list[dict[str, object]] = [
        {"timestamp": turn["timestamp"], "text": turn["text"]} for turn in turns
    ]
    return {
        "transcript": str(path),
        "count": len(turns),
        "skipped_lines": skipped,
        "turns": rows,
        "lines": _tsv_lines(rows, ("timestamp", "text")),
    }


_RUNNERS = {
    "checkpoint": _run_checkpoint,
    "validate": _run_validate,
    "schema": _run_schema,
    "resolve": _run_resolve,
    "show": _run_show,
    "lint": _run_lint,
    "list": _run_list,
    "log": _run_log,
    "turns": _run_turns,
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


def _refuse(
    stdout: TextIO,
    command: str,
    code: str,
    message: str,
    status: int,
    extra: dict[str, object] | None = None,
) -> int:
    _emit(
        stdout,
        {
            "ok": False,
            "command": command,
            "error": {"code": code, "message": message, **(extra or {})},
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
        return _refuse(stdout2, command, exc.code, str(exc), EXIT_REFUSED, exc.extra)
    except Exception as exc:  # noqa: BLE001 - a traceback is not a reply
        traceback.print_exc(file=sys.stderr)
        return _refuse(
            stdout2,
            command,
            "internal-error",
            f"{type(exc).__name__}: {exc}",
            EXIT_INTERNAL,
        )
    _emit(stdout2, {"ok": True, "command": command, **payload})
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
