"""The `fork` command: a thin mouth over `fork.fork`."""

from __future__ import annotations

import datetime as _dt
from collections.abc import Sequence
from pathlib import Path

import fromargs

from easy_cheese_schemas import Durability, NextMove, SessionProvenance

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import checkpoint as checkpoint_mod
from easy_cheese.shared.wheypoint import commit as commit_mod
from easy_cheese.shared.wheypoint import fork as fork_mod
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import storage

from easy_cheese.cli.wheypoint.checkpoint import (
    MirrorError,
    enum_values,
    mirror_finalizer,
    note_dir_for,
    open_store,
    read_notes_file,
    refusal_for,
    result_payload,
)
from easy_cheese.cli.wheypoint.queries import project_key


def _corpus_root(project: str | None) -> Path:
    if project is None:
        return paths.project_corpus_root()
    return paths.corpus_home() / project_key(project)


def _next_move(value: str | None, artifact: str | None) -> NextMove | None:
    """The child's next move, held to the artifact rule `checkpoint` applies."""
    if value is None:
        return None
    (move,) = enum_values("--next", [value], NextMove, "invalid-intent")
    try:
        checkpoint_mod.check_move_artifact(move, artifact)
    except checkpoint_mod.IntentError as exc:
        raise fromargs.CliError(f"invalid-intent: {exc}", exit_code=2) from exc
    return move


def run_fork(
    parent: str,
    child: str,
    *,
    orientation: str,
    links: Sequence[str] = (),
    context: Sequence[str] = (),
    notes_file: str | None = None,
    next: str | None = None,  # noqa: A002 -- the `--next` verb flag
    artifact: str | None = None,
    project: str | None = None,
) -> dict[str, object]:
    """The child genesis of a fork; the parent is read, never written (G3).

    Like `checkpoint`, the child's projection is mirrored beside the
    repository, except under `--project`: another corpus has no home here.
    """
    next_move = _next_move(next, artifact)
    corpus_root = _corpus_root(project)
    try:
        _ = open_store(parent, corpus_root=corpus_root).read_record()
    except storage.SchemaVersionFutureError as exc:
        raise refusal_for(exc) from exc
    except ValueError as exc:
        raise fromargs.CliError(
            f"record-unreadable: work {parent!r} has a record that cannot be read, "
            + f"so no fork can be taken from it: {exc}",
            exit_code=2,
        ) from exc
    captured_at = _dt.datetime.now(_dt.timezone.utc).strftime(
        checkpoint_mod.TIMESTAMP_FORMAT
    )
    note_dir = None if project is not None else note_dir_for(note_dir=None, no_note=False)
    target = None if note_dir is None else note_dir / f"{child}.md"
    if note_dir is not None:
        try:
            note_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise fromargs.CliError(
                f"note-unwritable: note directory {note_dir} cannot be created: {exc}",
                exit_code=2,
            ) from exc
    try:
        result = fork_mod.fork(
            parent=parent,
            child=child,
            corpus_root=corpus_root,
            session_provenance=SessionProvenance(
                harness=None, session_id=None, captured_at=captured_at
            ),
            orientation=orientation,
            links=links,
            context=context,
            notes=read_notes_file(notes_file),
            next=next_move,
            artifact=artifact,
            durability=(
                Durability.CANONICAL_LOCAL if target is None else Durability.REPO_SNAPSHOT
            ),
            finalize=None if target is None else mirror_finalizer(target),
        )
    except MirrorError as exc:
        raise fromargs.CliError(f"note-unwritable: {exc}", exit_code=2) from exc
    except (fork_mod.ForkError, commit_mod.CommitError, storage.StorageError) as exc:
        raise refusal_for(exc) from exc
    except ValueError as exc:
        raise fromargs.CliError(f"invalid-intent: {exc}", exit_code=2) from exc
    return {
        **result_payload(result, None if target is None else str(target)),
        "edges": [records.unstructure(edge) for edge in result.record.edges],
    }
