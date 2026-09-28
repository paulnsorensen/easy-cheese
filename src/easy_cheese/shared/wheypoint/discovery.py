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
from .ref_grammar import parse_ref

__all__ = [
    "Candidate",
    "DiscoveryResult",
    "Hit",
    "backlinks",
    "discover",
    "suggestions",
]


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


def _link_matcher(value: str) -> tuple[str, tuple[str, str] | None]:
    """What `value` matches: its normalized ref, plus the work it names when a
    `wheypoint:` ref carries no `@rev` or `#entry`, so any pin still matches."""
    ref = discovery_stores.normalized(value)
    try:
        parsed = parse_ref(ref)
    except ValueError:
        return ref, None
    if parsed.revision_id is not None or parsed.entry_id is not None:
        return ref, None
    return ref, discovery_stores.work_key(ref)


def _links_to(
    candidate: Candidate, matchers: list[tuple[str, tuple[str, str] | None]]
) -> bool:
    targets = [to for _, to in candidate.hit.edges_out] + list(candidate.links)
    for ref, key in matchers:
        for target in targets:
            if target == ref or (
                key is not None and discovery_stores.work_key(target) == key
            ):
                return True
    return False


def _entry_matches(
    candidate: Candidate, entry_kind: Sequence[str], entry_state: Sequence[str]
) -> bool:
    """Whether one entry satisfies both entry filters together."""
    return any(
        (not entry_kind or kind in entry_kind)
        and (not entry_state or state in entry_state)
        for kind, state in candidate.entries
    )


def _apply_filters(
    candidates: list[Candidate],
    *,
    grep: Sequence[str],
    status: Sequence[str],
    next: Sequence[str],
    source: str | None,
    since: str | None,
    entry_kind: Sequence[str] = (),
    entry_state: Sequence[str] = (),
    gated: bool | None = None,
    edge_kind: Sequence[str] = (),
    linked_to: Sequence[str] = (),
    forked_from: Sequence[str] = (),
) -> list[Candidate]:
    needles = [term.lower() for term in grep if term]
    since_date = _dt.date.fromisoformat(since) if since else None
    matchers = [_link_matcher(value) for value in linked_to]
    kept: list[Candidate] = []
    for candidate in candidates:
        hit = candidate.hit
        if needles and not any(n in candidate.haystack for n in needles):
            continue
        if status and hit.status not in status:
            continue
        if next and hit.next not in next:
            continue
        if source is not None and hit.source != source:
            continue
        if since_date is not None:
            updated_date = _dt.datetime.fromtimestamp(hit.updated).date()
            if updated_date < since_date:
                continue
        if (entry_kind or entry_state) and not _entry_matches(
            candidate, entry_kind, entry_state
        ):
            continue
        if gated is not None and bool(hit.gates) is not gated:
            continue
        if edge_kind and not any(kind in edge_kind for kind, _ in hit.edges_out):
            continue
        if matchers and not _links_to(candidate, matchers):
            continue
        if forked_from and hit.forked_from not in forked_from:
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
    grep: Sequence[str] = (),
    status: Sequence[str] = (),
    next: Sequence[str] = (),
    source: str | None = None,
    since: str | None = None,
    limit: int | None = None,
    show_mirrors: bool = False,
    entry_kind: Sequence[str] = (),
    entry_state: Sequence[str] = (),
    gated: bool | None = None,
    edge_kind: Sequence[str] = (),
    linked_to: Sequence[str] = (),
    forked_from: Sequence[str] = (),
) -> DiscoveryResult:
    """Every store and legacy note a caller can resume from, filtered and
    sorted newest first.

    `scope="project"` (default) reuses this project's store plus notes across
    the repository chain and every worktree. `scope="machine"` walks every
    project under `paths.corpus_home()` plus every machine search root.
    `projects` narrows either scope to the named project keys. Distinct
    filters combine with AND; the terms of one repeatable filter (`grep`,
    `status`, `next`, and the list filters below) combine with OR, so one
    call searches several terms at once. A note mirroring a store slug in
    the same project is hidden unless `show_mirrors` is set.

    `entry_kind` and `entry_state` match a record when one entry satisfies
    both together. `gated` keeps records with (True) or without (False)
    gating entries. `edge_kind` matches a held edge's kind, `forked_from` a
    parent work id, and `linked_to` any held edge target or artifact-link
    ref equal to the normalized ref; a `wheypoint:` ref without `@rev` or
    `#entry` matches the work at any pin.
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
        candidates,
        grep=grep,
        status=status,
        next=next,
        source=source,
        since=since,
        entry_kind=entry_kind,
        entry_state=entry_state,
        gated=gated,
        edge_kind=edge_kind,
        linked_to=linked_to,
        forked_from=forked_from,
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


def backlinks(
    ref: str,
    *,
    start: Path | str,
    scope: str = "project",
    corpus_root: Path | str | None = None,
    projects: Sequence[str] = (),
    roots: Sequence[Path | str] = (),
) -> tuple[Hit, ...]:
    """Every record in scope whose edges or links name `ref`.

    This is `discover(linked_to=(ref,))` by construction, so both return the
    same set; it never picks one record.
    """
    return discover(
        scope=scope,
        start=start,
        corpus_root=corpus_root,
        projects=projects,
        roots=roots,
        linked_to=(ref,),
    ).hits


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
