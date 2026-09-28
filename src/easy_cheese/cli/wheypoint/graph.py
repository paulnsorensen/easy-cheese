"""The five work-graph commands: fork, link, unlink, shape, backlinks.

Each one is a thin mouth over the kernel. `fork` calls `fork.fork`; `link`
and `unlink` build one intent and commit it through the same path as
`checkpoint`; `shape` and `backlinks` only serialize what the kernel found.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

import attrs
import fromargs

from easy_cheese_schemas import NextMove, SessionProvenance
from easy_cheese_schemas.contracts import EdgeKind

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import checkpoint as checkpoint_mod
from easy_cheese.shared.wheypoint import commit as commit_mod
from easy_cheese.shared.wheypoint import discovery
from easy_cheese.shared.wheypoint import fork as fork_mod
from easy_cheese.shared.wheypoint import intent_flags
from easy_cheese.shared.wheypoint import records
from easy_cheese.shared.wheypoint import shape as shape_mod
from easy_cheese.shared.wheypoint import storage

from easy_cheese.cli.wheypoint.checkpoint import (
    commit_intent,
    read_notes_file,
    refusal_for,
    result_payload,
)
from easy_cheese.cli.wheypoint.queries import hit_item, project_key


def _corpus_root(project: str | None) -> Path:
    if project is None:
        return paths.project_corpus_root()
    return paths.corpus_home() / project_key(project)


def _next_move(value: str | None) -> NextMove | None:
    if value is None:
        return None
    try:
        return NextMove(value)
    except ValueError as exc:
        known = ", ".join(move.value for move in NextMove)
        raise fromargs.CliError(f"--next: {value!r} names none of {known}") from exc


def _edge_kinds(values: Sequence[str]) -> tuple[EdgeKind, ...]:
    try:
        return tuple(EdgeKind(value) for value in values)
    except ValueError as exc:
        known = ", ".join(kind.value for kind in EdgeKind)
        raise fromargs.CliError(f"--kind: {exc}; known: {known}") from exc


def run_fork(
    parent: str,
    child: str,
    *,
    orientation: str,
    move: Sequence[str] = (),
    copy: Sequence[str] = (),
    dossier: Sequence[str] = (),
    links: Sequence[str] = (),
    context: Sequence[str] = (),
    notes_file: str | None = None,
    next: str | None = None,  # noqa: A002 -- the `--next` verb flag
    project: str | None = None,
) -> dict[str, object]:
    """The child genesis of a fork; the parent is read, never written (G3)."""
    captured_at = _dt.datetime.now(_dt.timezone.utc).strftime(
        checkpoint_mod.TIMESTAMP_FORMAT
    )
    try:
        result = fork_mod.fork(
            parent=parent,
            child=child,
            corpus_root=_corpus_root(project),
            session_provenance=SessionProvenance(
                harness=None, session_id=None, captured_at=captured_at
            ),
            orientation=orientation,
            move=move,
            copy=copy,
            dossier=dossier,
            links=links,
            context=context,
            notes=read_notes_file(notes_file),
            next=_next_move(next),
        )
    except (fork_mod.ForkError, commit_mod.CommitError, storage.StorageError) as exc:
        raise refusal_for(exc) from exc
    return {
        **result_payload(result, None),
        "origins": {
            entry.entry_id: entry.origin
            for entry in records.entries(result.record)
            if entry.origin is not None
        },
        "edges": [records.unstructure(edge) for edge in result.record.edges],
    }


def run_link(
    work_id: str,
    ref: str,
    *,
    kind: str,
    covers: Sequence[str] = (),
    rationale: str | None = None,
) -> dict[str, object]:
    """One edge on `work_id`, plus a pinned link for a pinnable ref (G4).

    A `--covers` link rides even for an unpinnable ref, so `commit` is the
    one that refuses it as `unpinnable-scheme`.
    """
    try:
        payload = intent_flags.overlay({}, work_id=work_id, link=[ref], kind=[kind])
    except intent_flags.IntentFlagError as exc:
        raise refusal_for(exc) from exc
    if rationale is not None:
        cast(list[dict[str, object]], payload["add_edges"])[0]["rationale"] = rationale
    if covers:
        links = cast(
            list[dict[str, object]],
            payload.setdefault("artifact_links", [{"path": ref.partition(":")[2], "ref": ref}]),
        )
        links[0]["covers_entry_ids"] = list(covers)
    reply = commit_intent(payload)
    return {**reply, "link": {"to": ref, "kind": kind}}


def run_unlink(work_id: str, ref: str, *, kind: str) -> dict[str, object]:
    """Remove the edge keyed by `(ref, kind)` from `work_id` (G4)."""
    return commit_intent(
        {"work_id": work_id, "remove_edges": [{"to": ref, "kind": kind}]}
    )


def _shape_edge(edge: shape_mod.ShapeEdge) -> dict[str, object]:
    return {
        "from": edge.from_ref,
        "to": edge.to,
        "kind": edge.kind.value,
        "revision_id": edge.revision_id,
        "pending": edge.pending,
    }


def run_shape(
    work_id: str | None = None,
    *,
    scope: Literal["project", "machine"] = "project",
    project: Sequence[str] = (),
    depth: int | None = None,
    kind: Sequence[str] = (),
) -> dict[str, object]:
    """The work graph in scope as JSON, with its Graphviz rendering in `dot` (G5)."""
    if depth is not None and depth < 0:
        raise fromargs.CliError(f"--depth: must be at least 0, not {depth}")
    report = shape_mod.shape(
        scope=scope,
        corpus_home=paths.corpus_home(),
        project=paths.project_key(),
        projects=[project_key(key) for key in project],
        work_id=work_id,
        depth=depth,
        kinds=_edge_kinds(kind),
    )
    return {
        "nodes": [attrs.asdict(node) for node in report.nodes],
        "edges": [_shape_edge(edge) for edge in report.edges],
        "pending": [_shape_edge(edge) for edge in report.pending],
        "documents": [attrs.asdict(document) for document in report.documents],
        "roots": list(report.roots),
        "dangling": [_shape_edge(edge) for edge in report.dangling],
        "dot": report.dot,
    }


def run_backlinks(
    ref: str,
    *,
    scope: Literal["project", "machine"] = "project",
    project: Sequence[str] = (),
    corpus_root: str | None = None,
) -> dict[str, object]:
    """Every record in scope whose edges or links name `ref` (G6)."""
    projects = [project_key(key) for key in project]
    hits = discovery.backlinks(
        ref,
        start=Path.cwd(),
        scope="machine" if projects else scope,
        corpus_root=corpus_root,
        projects=projects,
    )
    return {"ref": ref, "items": [hit_item(hit) for hit in hits]}
