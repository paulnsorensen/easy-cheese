"""Fork a child record from a parent in one revision: the child genesis.

`fork` writes only the child. It reads the parent without its lock and writes
nothing to it, and it copies or moves no parent entry. The child's
`forked_from` edge pins the parent revision the fork read; the edge is a
host-only commit input.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from easy_cheese_schemas import (
    ArtifactLink,
    Durability,
    NextAction,
    NextMove,
    RepositoryProvenance,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import EdgeKind, WorkEdge

from . import commit, records, storage
from .ref_grammar import normalize_ref

__all__ = ["ForkError", "fork"]


class ForkError(ValueError):
    """The fork cannot be made. The message starts with a `code:` prefix."""


def fork(
    *,
    parent: str,
    child: str,
    corpus_root: Path,
    session_provenance: SessionProvenance,
    orientation: str,
    links: Sequence[str] = (),
    context: Sequence[str] = (),
    notes: str | None = None,
    next: NextMove | None = None,  # noqa: A002 -- the `--next` verb flag
    artifact: str | None = None,
    repository: RepositoryProvenance | None = None,
    durability: Durability = Durability.CANONICAL_LOCAL,
    artifact_root: Path | str | None = None,
    finalize: Callable[[commit.PendingRevision], None] | None = None,
) -> commit.CommitResult:
    """Write the child genesis for a fork of `parent`, and nothing else.

    `session_provenance.captured_at` becomes the child's created time: the
    kernel reads no clock.
    """
    source = storage.WorkStore.open(parent, corpus_root=corpus_root).read_record()
    if source is None:
        raise ForkError(f"unknown-parent: work {parent!r} has no record")
    target = storage.WorkStore.open(child, corpus_root=corpus_root)
    if target.record_path.exists() or any(target.revisions_dir.glob("*.json")):
        raise ForkError(f"fork-exists: work {child!r} already has a record or history")
    origin = f"wheypoint:{source.project_key}/{parent}@{source.revision_id}"
    delta = WheypointDelta(
        work_id=child,
        expected_revision_id=commit.GENESIS_PARENT,
        orientation=orientation,
        working_context=list(context),
        notes=notes,
        next_action=NextAction(
            move=NextMove.HOLD if next is None else next,
            orientation=orientation,
            artifact=artifact,
        ),
        add_artifact_links=_links(source, links),
        session_provenance=session_provenance,
    )
    return commit.commit(
        delta,
        store=target,
        repository=repository,
        durability=durability,
        artifact_root=artifact_root,
        fork_edge=WorkEdge(to=origin, kind=EdgeKind.FORKED_FROM),
        finalize=finalize,
    )


def _links(source: WheypointRecord, refs: Sequence[str]) -> list[ArtifactLink] | None:
    """Copies of the named parent links; the child pins its own digests."""
    if not refs:
        return None
    by_ref = {
        _normalized(records.effective_ref(link)): link for link in source.artifact_links
    }
    unknown = [ref for ref in refs if _normalized(ref) not in by_ref]
    if unknown:
        raise ForkError(
            f"unknown-link: work {source.work_id!r} carries no link "
            + ", ".join(repr(ref) for ref in unknown)
        )
    return [
        ArtifactLink(path=by_ref[ref].path, ref=ref)
        for ref in dict.fromkeys(_normalized(ref) for ref in refs)
    ]


def _normalized(ref: str) -> str:
    try:
        return normalize_ref(ref)
    except ValueError:
        return ref
