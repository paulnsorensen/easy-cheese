"""Find every Wheypoint work item and legacy note a caller can resume from,
across worktrees, projects, or the whole machine.

Discovery is kernel code (G8): it returns typed hits and never picks one --
`resolve` remains the only authority that dispatches a checkpoint. Sorting is
display order only, by `updated` (file mtime) then path; it never breaks a
tie the way `resolve` would.
"""

from __future__ import annotations

import datetime as _dt
import difflib
from collections.abc import Sequence
from pathlib import Path

from . import discovery_notes, discovery_stores
from .discovery_types import Candidate, DiscoveryResult, Hit

__all__ = ["Candidate", "DiscoveryResult", "Hit", "discover", "suggestions"]


def _mirror_key(candidate: Candidate) -> tuple[str, str] | None:
    if candidate.slug is None:
        return None
    return (candidate.hit.project, candidate.slug)


def _hide_mirrors(
    candidates: list[Candidate], *, show_mirrors: bool
) -> tuple[list[Candidate], int]:
    """Drop a note whose slug mirrors a store slug in the same project."""
    store_keys = {
        _mirror_key(candidate)
        for candidate in candidates
        if candidate.hit.source == "store"
    }
    store_keys.discard(None)
    kept: list[Candidate] = []
    hidden = 0
    for candidate in candidates:
        is_mirror = (
            candidate.hit.source == "note" and _mirror_key(candidate) in store_keys
        )
        if is_mirror and not show_mirrors:
            hidden += 1
            continue
        kept.append(candidate)
    return kept, hidden


def _apply_filters(
    candidates: list[Candidate],
    *,
    grep: str | None,
    status: str | None,
    next: str | None,
    source: str | None,
    since: str | None,
) -> list[Candidate]:
    needle = grep.lower() if grep else None
    since_date = _dt.date.fromisoformat(since) if since else None
    kept: list[Candidate] = []
    for candidate in candidates:
        hit = candidate.hit
        if needle is not None and needle not in candidate.haystack:
            continue
        if status is not None and hit.status != status:
            continue
        if next is not None and hit.next != next:
            continue
        if source is not None and hit.source != source:
            continue
        if since_date is not None:
            updated_date = _dt.datetime.fromtimestamp(hit.updated).date()
            if updated_date < since_date:
                continue
        kept.append(candidate)
    return kept


def discover(
    *,
    scope: str = "project",
    start: Path | str,
    corpus_root: Path | str | None = None,
    projects: Sequence[str] = (),
    roots: Sequence[Path | str] = (),
    grep: str | None = None,
    status: str | None = None,
    next: str | None = None,
    source: str | None = None,
    since: str | None = None,
    limit: int | None = None,
    show_mirrors: bool = False,
) -> DiscoveryResult:
    """Every store and legacy note a caller can resume from, filtered and
    sorted newest first.

    `scope="project"` (default) reuses this project's store plus notes across
    the repository chain and every worktree. `scope="machine"` walks every
    project under `paths.corpus_home()` plus every machine search root.
    `projects` narrows either scope to the named project keys. Filters
    combine with AND; a note mirroring a store slug in the same project is
    hidden unless `show_mirrors` is set.
    """
    machine = scope == "machine"
    store_candidates, store_searched, store_errors = discovery_stores.discover(
        corpus_root=corpus_root, machine=machine
    )
    note_candidates, note_searched, note_errors = discovery_notes.discover(
        start=start, machine=machine, roots=roots
    )
    candidates = [*store_candidates, *note_candidates]
    if projects:
        wanted = set(projects)
        candidates = [c for c in candidates if c.hit.project in wanted]
    candidates, hidden = _hide_mirrors(candidates, show_mirrors=show_mirrors)
    candidates = _apply_filters(
        candidates, grep=grep, status=status, next=next, source=source, since=since
    )
    candidates.sort(key=lambda c: (-c.hit.updated, str(c.hit.path)))
    if limit is not None:
        candidates = candidates[:limit]
    return DiscoveryResult(
        hits=tuple(c.hit for c in candidates),
        searched=tuple(store_searched) + tuple(note_searched),
        hidden_mirrors=hidden,
        errors=tuple(store_errors) + tuple(note_errors),
    )


def suggestions(
    ref: str,
    *,
    start: Path | str,
    corpus_root: Path | str | None = None,
    scope: str = "project",
    roots: Sequence[Path | str] = (),
    limit: int = 5,
) -> tuple[str, ...]:
    """Close work ids and note slugs for `ref`; never picks one for the caller."""
    result = discover(
        scope=scope,
        start=start,
        corpus_root=corpus_root,
        roots=roots,
        show_mirrors=True,
    )
    candidates = sorted({hit.ref for hit in result.hits})
    return tuple(difflib.get_close_matches(ref, candidates, n=limit))
