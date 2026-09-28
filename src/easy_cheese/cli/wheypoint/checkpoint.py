"""The `checkpoint` command and its durable pending-mirror transaction.

A note-mirrored checkpoint spans two writes -- the canonical commit and the
readable mirror beside the repository -- so a crash between them must be
resumable rather than silently doubled or lost. `_PendingMirror` is the
ledger entry that makes the second write idempotent across a retry.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path
from typing import TextIO, TypeVar, cast

import fromargs
from attrs import define, evolve

from easy_cheese_schemas import (
    LOWER_IDENTIFIER_RE,
    CheckpointIntent,
    CompactionRecord,
    Durability,
    WheypointDelta,
    WheypointRecord,
)

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import canonical
from easy_cheese.shared.wheypoint import checkpoint as checkpoint_mod
from easy_cheese.shared.wheypoint import commit as commit_mod
from easy_cheese.shared.wheypoint import fork as fork_mod
from easy_cheese.shared.wheypoint import intent_flags
from easy_cheese.shared.wheypoint import legacy as legacy_mod
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import ref_grammar
from easy_cheese.shared.wheypoint import storage

# A kernel refusal that names its own code: `<word>-<word>...: <message>`.
_CODED_REFUSAL = re.compile(r"[a-z]+(?:-[a-z]+)+: ")

_E = TypeVar("_E", bound=Enum)


def enum_values(
    flag: str, values: Sequence[str], choices: type[_E], code: str
) -> tuple[_E, ...]:
    """Each flag value as a member of `choices`, or a `code` refusal naming the known ones."""
    try:
        return tuple(choices(value) for value in values)
    except ValueError as exc:
        known = ", ".join(cast(str, item.value) for item in choices)
        raise fromargs.CliError(f"{code}: {flag} {exc}; known: {known}", exit_code=1) from exc


def parsed_ref(ref: str) -> str:
    """`ref` when the ref grammar can read it, else a `flag-link` refusal."""
    try:
        _ = ref_grammar.parse_ref(ref)
    except ValueError as exc:
        raise fromargs.CliError(f"flag-link: {exc}", exit_code=1) from exc
    return ref


@define(frozen=True, kw_only=True)
class IntentFlags:
    """The `checkpoint` and `validate` flags that build or overlay an intent (G7)."""

    work_id: str | None = None
    question: Sequence[str] = ()
    blocker: Sequence[str] = ()
    gates: bool = False
    decision: Sequence[str] = ()
    rationale: Sequence[str] = ()
    directive: Sequence[str] = ()
    quote: Sequence[str] = ()
    resolve: Sequence[str] = ()
    withdraw: Sequence[str] = ()
    orientation: str | None = None
    next: str | None = None
    artifact: str | None = None
    context: Sequence[str] = ()
    notes_file: str | None = None
    link: Sequence[str] = ()
    kind: Sequence[str] = ()
    covers: Sequence[str] = ()

    def given(self) -> bool:
        return self != IntentFlags()

    def apply(self, payload: object) -> dict[str, object]:
        """`payload` with the flags overlaid by the kernel's one builder."""
        if not isinstance(payload, dict):
            raise fromargs.CliError(
                "invalid-intent: flags overlay a JSON object intent, not "
                + f"{type(payload).__name__}",
                exit_code=1,
            )
        try:
            return intent_flags.overlay(
                cast(dict[str, object], payload),
                work_id=self.work_id,
                question=self.question,
                blocker=self.blocker,
                gates=self.gates,
                decision=self.decision,
                rationale=self.rationale,
                directive=self.directive,
                quote=self.quote,
                resolve=self.resolve,
                withdraw=self.withdraw,
                orientation=self.orientation,
                next=self.next,
                artifact=self.artifact,
                context=self.context,
                notes=read_notes_file(self.notes_file),
                link=self.link,
                kind=self.kind,
                covers=self.covers,
            )
        except intent_flags.IntentFlagError as exc:
            raise refusal_for(exc) from exc


def read_notes_file(path_arg: str | None) -> str | None:
    """The text of `--notes-file`, or None when the flag is absent."""
    if path_arg is None:
        return None
    try:
        return Path(path_arg).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise fromargs.CliError(
            f"notes-unreadable: {path_arg}: {exc}", exit_code=1
        ) from exc


@define(frozen=True)
class _PendingMirror:
    """A durable identity for a revision whose mirror still needs finalization."""

    request_identity: str
    request_digest: str
    revision_id: str
    target: str


def note_dir_for(*, note_dir: str | None, no_note: bool) -> Path | None:
    """Where the readable mirror goes, or None when none is to be written.

    `--no-note` refuses one outright; an explicit `--note-dir` is taken as
    given; otherwise the mirror belongs beside the repository the checkpoint
    describes, and outside a repository there is nowhere for it to belong.
    """
    if no_note:
        return None
    if note_dir is not None:
        return Path(note_dir).expanduser()
    toplevel = paths.git_toplevel()
    if toplevel is None:
        return None
    return toplevel.joinpath(*legacy_mod.NOTES_DIR_PARTS)


def read_payload(stdin: TextIO) -> object:
    try:
        return cast(object, json.loads(stdin.read()))
    except ValueError as exc:
        raise fromargs.CliError(
            f"invalid-json: stdin is not one JSON value: {exc}", exit_code=1
        ) from exc


def read_intent(
    intent_arg: str | None, stdin: TextIO, flags: IntentFlags | None = None
) -> object:
    """The JSON intent from a path argument, `-`, or stdin when neither (G6)."""
    return _read_overlaid(intent_arg, stdin, flags)[0]


def _read_overlaid(
    intent_arg: str | None, stdin: TextIO, flags: IntentFlags | None
) -> tuple[object, int | None]:
    """The intent, and the index of its first flag-built artifact link.

    Flags overlay that intent (G7). With flags, a positional that names no
    existing path is the work id, and flags with no intent start from an
    empty one: they never read stdin unless the intent argument is `-`.
    The index is None when no flag is given.
    """
    if flags is not None and flags.given():
        if intent_arg is not None and intent_arg != "-":
            path = Path(intent_arg)
            if not path.exists():
                flags = _positional_work_id(intent_arg, flags)
                intent_arg = None
            elif not path.is_file():
                raise fromargs.CliError(
                    f"intent-unreadable: {intent_arg!r} is not a file: pass "
                    + "--work-id to write to a work id that shares its name",
                    exit_code=1,
                )
        base: object = {} if intent_arg is None else read_intent(intent_arg, stdin)
        return flags.apply(base), _link_count(base)
    if intent_arg is None or intent_arg == "-":
        return read_payload(stdin), None
    path = Path(intent_arg)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise fromargs.CliError(
            f"intent-unreadable: {intent_arg}: {exc}", exit_code=1
        ) from exc
    try:
        return cast(object, json.loads(raw)), None
    except ValueError as exc:
        raise fromargs.CliError(
            f"invalid-json: {intent_arg} is not one JSON value: {exc}", exit_code=1
        ) from exc


def _link_count(payload: object) -> int:
    """How many artifact links `payload` names before the flags add theirs."""
    if not isinstance(payload, dict):
        return 0
    links = cast(dict[str, object], payload).get("artifact_links")
    return len(cast(list[object], links)) if isinstance(links, list) else 0


def _positional_work_id(value: str, flags: IntentFlags) -> IntentFlags:
    """`flags` writing to the work id `value`, the AC-14 positional form."""
    if value.endswith(".json") or "/" in value or os.sep in value:
        raise fromargs.CliError(
            f"intent-unreadable: {value}: no such intent file", exit_code=1
        )
    if not LOWER_IDENTIFIER_RE.fullmatch(value):
        raise fromargs.CliError(
            f"intent-unreadable: {value!r} is neither an intent file nor a work id: "
            + "pass `<intent-file|-> --<flag>` or `<work-id> --<flag>`",
            exit_code=1,
        )
    if flags.work_id not in (None, value):
        raise fromargs.CliError(
            f"intent-ambiguous: the positional work id {value!r} and --work-id "
            + f"{flags.work_id!r} differ",
            exit_code=1,
        )
    return evolve(flags, work_id=value)


def open_store(work_id: str, *, corpus_root: Path | None = None) -> storage.WorkStore:
    try:
        return storage.WorkStore.open(work_id, corpus_root=corpus_root)
    except storage.StorageError as exc:
        raise fromargs.CliError(f"storage-error: {exc}", exit_code=1) from exc


def run_checkpoint(
    intent_arg: str | None,
    stdin: TextIO,
    *,
    compacted: str | None,
    note_dir: str | None,
    no_note: bool,
    flags: IntentFlags | None = None,
) -> dict[str, object]:
    """A semantic intent, bound to the current record and committed.

    The binding is a read outside the lock, so it settles nothing: `commit`
    re-checks the parent under the lock and refuses a delta whose record has
    moved on. This command shortens the authoring, not the checking.
    """
    payload, carry_from = _read_overlaid(intent_arg, stdin, flags)
    return commit_intent(
        payload,
        compacted=compacted,
        note_dir=note_dir,
        no_note=no_note,
        carry_from=carry_from,
    )


def commit_intent(
    payload: object,
    *,
    compacted: str | None = None,
    note_dir: str | None = None,
    no_note: bool = False,
    carry_from: int | None = None,
) -> dict[str, object]:
    """Structure, bind, and commit one intent payload; the one write path.

    `carry_from` is the index of the first flag-built artifact link: from it
    on, a link that names no coverage keeps the coverage the record already
    holds for it. None carries nothing.
    """
    reserved = checkpoint_mod.commit_only_fields(payload)
    if reserved:
        raise fromargs.CliError(
            f"commit-only-field: checkpoint does not author {', '.join(reserved)}: "
            + "the runtime binds the parent automatically. Use base_revision_id to pin "
            + "a read revision. Use checkpoint --compacted <proof-path> for a compaction proof.",
            exit_code=1,
        )
    try:
        intent = records.structure(payload, CheckpointIntent, forbid_unknown=True)
    except records.RecordError as exc:
        raise fromargs.CliError(f"invalid-intent: {exc}", exit_code=1) from exc
    secret = checkpoint_mod.secret_field(intent)
    if secret is not None:
        raise fromargs.CliError(
            f"secret-pattern: {secret} looks like a credential: a checkpoint is "
            + "durable, digest-protected text, so it cannot carry one",
            exit_code=1,
        )
    proof = _compaction_proof(compacted)
    store = open_store(intent.work_id)
    try:
        current = store.read_record()
    except ValueError as exc:
        raise fromargs.CliError(
            f"record-unreadable: work {intent.work_id!r} has a record that cannot "
            + f"be read, so no checkpoint can be bound to it: {exc}",
            exit_code=1,
        ) from exc
    if carry_from is not None:
        intent = carry_coverage(intent, current, carry_from)
    # The proof is part of the request: an identical intent with and without a
    # proof must not share a pending-mirror ledger entry.
    request_identity = request_identity_for(intent, proof)
    try:
        delta = checkpoint_mod.build_delta(intent, current)
    except checkpoint_mod.IntentError as exc:
        raise fromargs.CliError(f"invalid-intent: {exc}", exit_code=1) from exc
    if proof is not None:
        delta = evolve(delta, compacted=True, compaction=proof)
    return _promote(
        delta,
        store,
        note_dir=note_dir_for(note_dir=note_dir, no_note=no_note),
        request_identity=request_identity,
    )


def carry_coverage(
    intent: CheckpointIntent, current: WheypointRecord | None, start: int
) -> CheckpointIntent:
    """`intent` with each uncovering link from index `start` on given the
    coverage `current` holds for it.

    Links match as the kernel merges them: a ref matches itself once
    normalized, and an unpinned `wheypoint:` ref also matches its target
    pinned at any revision.
    """
    if current is None or not intent.artifact_links:
        return intent
    held = [
        (_normalized(records.effective_ref(link)), link.covers_entry_ids)
        for link in current.artifact_links
    ]
    return evolve(
        intent,
        artifact_links=[
            link
            if index < start or link.covers_entry_ids
            else evolve(
                link, covers_entry_ids=_held_covers(held, records.effective_ref(link))
            )
            for index, link in enumerate(intent.artifact_links)
        ],
    )


def _held_covers(held: Sequence[tuple[str, Sequence[str]]], ref: str) -> list[str]:
    key = _normalized(ref)
    target = commit_mod.record_target(key)
    unpinned = target is not None and target == key
    matches = [
        covers
        for held_ref, covers in held
        if held_ref == key or (unpinned and commit_mod.record_target(held_ref) == target)
    ]
    return list(matches[-1]) if matches else []


def _normalized(ref: str) -> str:
    try:
        return ref_grammar.normalize_ref(ref)
    except ValueError:
        return ref


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


def _compaction_proof(path_arg: str | None) -> CompactionRecord | None:
    """The `--compacted` proof, validated before it can touch a delta."""
    if path_arg is None:
        return None
    path = Path(path_arg)
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except OSError as exc:
        raise fromargs.CliError(
            f"compaction-proof-unreadable: {path_arg}: {exc}", exit_code=1
        ) from exc
    except ValueError as exc:
        raise fromargs.CliError(
            f"compaction-proof-unreadable: {path_arg} is not one JSON value: {exc}",
            exit_code=1,
        ) from exc
    try:
        return records.structure(raw, CompactionRecord, forbid_unknown=True)
    except records.RecordError as exc:
        raise fromargs.CliError(f"invalid-compaction-proof: {exc}", exit_code=1) from exc


def refusal_for(exc: Exception) -> fromargs.CliError:
    """The one mapping from a kernel/storage error to a reply code, every path.

    A fork, flag, or commit refusal whose message starts with its own code
    surfaces that code; any other commit refusal is `commit-refused`.
    """
    if isinstance(exc, commit_mod.GenesisConflictError):
        return fromargs.CliError(f"genesis-conflict: {exc}", exit_code=1)
    if isinstance(exc, commit_mod.StaleParentError):
        return fromargs.CliError(f"stale-parent: {exc}", exit_code=1)
    if isinstance(
        exc, (commit_mod.CommitError, fork_mod.ForkError, intent_flags.IntentFlagError)
    ):
        if _CODED_REFUSAL.match(str(exc)):
            return fromargs.CliError(str(exc), exit_code=1)
        return fromargs.CliError(f"commit-refused: {exc}", exit_code=1)
    return fromargs.CliError(f"storage-error: {exc}", exit_code=1)


def _promote(
    delta: WheypointDelta,
    store: storage.WorkStore,
    *,
    note_dir: Path | None,
    request_identity: str,
) -> dict[str, object]:
    if note_dir is None:
        try:
            result = commit_mod.commit(
                delta,
                store=store,
                durability=Durability.CANONICAL_LOCAL,
            )
        except (commit_mod.CommitError, storage.StorageError) as exc:
            raise refusal_for(exc) from exc
        return result_payload(result, None)

    try:
        note_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise fromargs.CliError(
            f"note-unwritable: note directory {note_dir} cannot be created: {exc}",
            exit_code=1,
        ) from exc

    try:
        current = store.read_record()
    except ValueError as exc:
        raise fromargs.CliError(
            f"record-unreadable: work {store.work_id!r} has a record that cannot "
            + f"be read: {exc}",
            exit_code=1,
        ) from exc
    target = note_dir / (f"{store.work_id if current is None else current.slug}.md")
    pending = _read_pending(store, request_identity)
    if pending is not None:
        revision = store.find_complete_revision(pending.revision_id)
        if revision is not None:
            if revision.request_digest != pending.request_digest:
                raise fromargs.CliError(
                    f"pending-corrupt: request ledger for {request_identity!r} names "
                    + f"a different request than revision {pending.revision_id!r}",
                    exit_code=1,
                )
            resume_target = note_dir / pending.target
            result = _resume_mirror(store, revision.revision_id, resume_target, pending)
            return result_payload(result, str(resume_target))
        try:
            store.remove_pending(request_identity)
        except OSError as exc:
            raise fromargs.CliError(
                "storage-error: request ledger "
                + f"{store.pending_path(request_identity)} cannot be cleared: {exc}",
                exit_code=1,
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
            finalize=mirror_finalizer(target),
        )
    except MirrorError as exc:
        _drop_uncommitted_pending(store, pending)
        raise fromargs.CliError(f"note-unwritable: {exc}", exit_code=1) from exc
    except (commit_mod.CommitError, storage.StorageError) as exc:
        _drop_uncommitted_pending(store, pending)
        raise refusal_for(exc) from exc
    _clear_pending(store, request_identity)
    return result_payload(result, str(target))


def mirror_finalizer(
    target: Path,
) -> Callable[[commit_mod.PendingRevision], None]:
    """The mirror finalizer: the durability this projection claims lands
    before the record is promoted.
    """

    def finalize(pending_revision: commit_mod.PendingRevision) -> None:
        try:
            storage.write_atomic(target, pending_revision.markdown.encode("utf-8"))
        except OSError as exc:
            raise MirrorError(f"mirror {target} cannot be finalized: {exc}") from exc

    return finalize


class MirrorError(OSError):
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
        raise fromargs.CliError(
            f"storage-error: request ledger {path} cannot be read: {exc}", exit_code=1
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
        raise fromargs.CliError(
            f"pending-corrupt: request ledger {path} is invalid: {exc}", exit_code=1
        ) from exc
    if pending.request_identity != request_identity:
        raise fromargs.CliError(
            f"pending-corrupt: request ledger {path} has invalid identity", exit_code=1
        )
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
        raise fromargs.CliError(
            f"note-unwritable: request ledger {path} cannot be written: {exc}",
            exit_code=1,
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
        raise fromargs.CliError(
            "storage-error: request ledger "
            + f"{store.pending_path(request_identity)} cannot be cleared: {exc}",
            exit_code=1,
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
            finalize=mirror_finalizer(target),
        )
    except MirrorError as exc:
        raise fromargs.CliError(f"note-unwritable: {exc}", exit_code=1) from exc
    except (commit_mod.CommitError, storage.StorageError) as exc:
        raise refusal_for(exc) from exc
    _clear_pending(store, pending.request_identity)
    return result


def result_payload(
    result: commit_mod.CommitResult, note_path: str | None
) -> dict[str, object]:
    """The commit reply every write verb shares, with each derived id named."""
    revision = result.revision
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
        "derived_entry_ids": [entry.entry_id for entry in revision.applied_additions],
        "applied_transitions": [
            records.unstructure(item) for item in revision.applied_transitions
        ],
        "applied_edges": [records.unstructure(edge) for edge in revision.applied_edges],
        "removed_edges": [records.unstructure(key) for key in revision.removed_edges],
    }
