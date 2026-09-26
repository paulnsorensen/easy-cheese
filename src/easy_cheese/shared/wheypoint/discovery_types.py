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


@define(frozen=True)
class DiscoveryResult:
    """Everything a search found, plus exactly where and how it looked."""

    hits: tuple[Hit, ...] = field(default=())
    searched: tuple[str, ...] = field(default=())
    hidden_mirrors: int = 0
    errors: tuple[str, ...] = field(default=())


@define(frozen=True)
class Candidate:
    """A hit plus the internal data discovery needs but never publishes."""

    hit: Hit
    slug: str | None
    haystack: str
