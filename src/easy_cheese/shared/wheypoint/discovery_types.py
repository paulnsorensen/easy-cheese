"""Shared types for Wheypoint discovery: hits, results, and search candidates."""

from __future__ import annotations

from pathlib import Path

from attrs import define, field


@define(frozen=True)
class Hit:
    """One discovered work item or legacy note, ready to render or resume.

    `updated` orders the display only: resolution never picks by mtime.
    `resume` is the absolute path `resolve` and `/cheese --continue` accept
    from any cwd -- the current projection for a store, the note itself for
    a note. `problem` is set instead of raising when a note cannot be parsed.

    `edges_out` pairs each held edge's kind with its normalized target;
    `edges_in` pairs the kind of each edge that names this record with the
    `wheypoint:` ref of the record holding it, among the records searched.
    `forked_from` is the parent work id of a `forked_from` edge, and `gates`
    the gating entry ids. A note leaves all four empty.
    """

    source: str  # "store" | "note"
    project: str
    ref: str  # work_id for a store, slug for a note
    status: str | None
    next: str | None
    orientation: str
    updated: float
    path: Path
    resume: Path
    revision_number: int | None = None
    problem: str | None = None
    edges_out: tuple[tuple[str, str], ...] = ()
    edges_in: tuple[tuple[str, str], ...] = ()
    forked_from: str | None = None
    gates: tuple[str, ...] = ()


@define(frozen=True)
class DiscoveryResult:
    """Everything a search found, plus exactly where and how it looked."""

    hits: tuple[Hit, ...] = field(default=())
    searched: tuple[str, ...] = field(default=())
    hidden_mirrors: int = 0
    errors: tuple[str, ...] = field(default=())


@define(frozen=True)
class Candidate:
    """A hit plus the internal data discovery needs but never publishes.

    `entries` pairs each entry's kind with its state; `links` holds the
    normalized effective ref of each artifact link.
    """

    hit: Hit
    slug: str | None
    haystack: str
    entries: tuple[tuple[str, str], ...] = ()
    links: tuple[str, ...] = ()
