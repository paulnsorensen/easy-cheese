"""Deterministic lookup of a pre-Wheypoint `.cheese/notes/<slug>.md` note.

A legacy note is a fallback, not an authority, and the only way it stays safe
is that finding one is a *pure function of which files exist*:

* Every worktree `git worktree list --porcelain` reports is searched, not just
  the one the caller happens to stand in -- that omission is what let a
  checkpoint written in a sibling worktree disappear on resume.
* Two notes for one slug are an ambiguity, full stop. Nothing here compares
  modification times, session ids, or slug recency, because a slug is an alias
  and the newer file is not thereby the right one.
* A miss reports the exact candidate paths that were probed, so the caller can
  say where it looked instead of guessing that nothing exists anywhere.

When git cannot be listed the scan degrades to the starting worktree alone and
says so: a partial search that reports itself as complete would turn a missing
sibling into a confident "no note".
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path

from attrs import define, field

NOTES_DIR_PARTS = (".cheese", "notes")
WORKTREE_LIST_ARGS = ("git", "worktree", "list", "--porcelain")
_GIT_TIMEOUT_SECONDS = 5
# A slug is joined onto a worktree root, so it has to be a single safe segment
# before it ever touches the filesystem.
_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")

# (args, cwd) -> stdout, or None when the command could not be run.
Runner = Callable[[Sequence[str], Path], "str | None"]


class LegacyLookupError(ValueError):
    """Raised when a lookup is asked for something it must not join to a path."""


class LegacyOutcome(str, Enum):
    FOUND = "found"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not-found"


@define(frozen=True)
class LegacyNote:
    """One `<worktree>/.cheese/notes/<slug>.md` that exists."""

    worktree: Path
    path: Path



@define(frozen=True)
class LegacyHandoffSlug:
    """Decoded legacy handoff metadata, kept separate from the shared parser."""

    status: str
    halt_reason: str | None
    next_skill: str
    artifact: str | None
    orientation: str
    mode: str = "single"
    session: str | None = None
    git: str | None = None
    created: str | None = None
    parents: str | None = None
    baseline: str | None = None
    taste_test: str | None = None
    durable_flags: str | None = None

    def is_halt(self) -> bool:
        return self.status == "halt"

    def is_gated(self) -> bool:
        return self.status == "gated"


class LegacyDecodeError(ValueError):
    """Raised when a legacy note wrapper or preamble is malformed."""


_HEADER_RE = re.compile(r"^(?P<key>[a-z][a-z0-9_]*):\s*(?P<value>.*?)\s*$")
_FENCE_RE = re.compile(r"^(?P<marker>\x60{3,}|~{3,})(?:text)?\s*$")
_ALLOWED_HEADER_KEYS = frozenset(
    {
        "status",
        "next",
        "artifact",
        "mode",
        "session",
        "git",
        "created",
        "parents",
        "baseline",
        "taste_test",
        "durable_flags",
    }
)


def _parse_legacy_status(value: str) -> tuple[str, str | None]:
    if value == "ok":
        return "ok", None
    for status in ("halt", "gated"):
        if value == status:
            return status, None
        prefix = f"{status}:"
        if value.startswith(prefix):
            reason = value[len(prefix) :].strip()
            if not reason:
                raise LegacyDecodeError(f"{status} status requires a reason")
            return status, reason
    raise LegacyDecodeError(
        "status must be 'ok', 'halt: <reason>', or 'gated: <reason>'"
    )


def _unwrap_legacy_note(text: str) -> str:
    lines = text.splitlines()
    first = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first is None or lines[first].strip() != "## Handoff slug":
        return text
    index = first + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        raise LegacyDecodeError("handoff wrapper fence is missing")
    match = _FENCE_RE.fullmatch(lines[index].strip())
    if match is None:
        raise LegacyDecodeError("handoff wrapper needs a backtick or tilde fence")
    marker = match.group("marker")
    index += 1
    close = None
    for candidate in range(index, len(lines)):
        if lines[candidate].strip() == marker:
            close = candidate
            break
    if close is None:
        raise LegacyDecodeError("handoff wrapper fence is not closed")
    if any(line.strip() == "## Handoff slug" for line in lines[close + 1 :]):
        raise LegacyDecodeError("legacy note contains multiple handoff wrappers")
    return "\n".join(lines[index:close])


def _parse_legacy_header(text: str) -> LegacyHandoffSlug:
    values: dict[str, str] = {}
    orientation: str | None = None
    for line in text.splitlines():
        match = _HEADER_RE.fullmatch(line)
        if match is None:
            orientation = line.strip()
            if not orientation:
                raise LegacyDecodeError("orientation line must be non-empty")
            break
        key = match.group("key")
        if key not in _ALLOWED_HEADER_KEYS:
            if orientation is None:
                raise LegacyDecodeError(f"unknown handoff key {key!r}")
            break
        if key in values:
            raise LegacyDecodeError(f"duplicate '{key}:' line in handoff preamble")
        value = match.group("value")
        if key != "artifact" and not value:
            raise LegacyDecodeError(f"'{key}:' line requires a value")
        values[key] = value
    missing = [key for key in ("status", "next", "artifact") if key not in values]
    if missing:
        raise LegacyDecodeError("handoff preamble missing " + ", ".join(missing))
    if orientation is None:
        raise LegacyDecodeError("orientation line missing after keyed preamble lines")
    status, halt_reason = _parse_legacy_status(values["status"])
    next_skill = values["next"].lstrip("/")
    if not next_skill:
        raise LegacyDecodeError("'next:' line requires a value")
    mode = values.get("mode", "single")
    if mode not in {"single", "parallel"}:
        raise LegacyDecodeError("mode must be 'single' or 'parallel'")
    return LegacyHandoffSlug(
        status=status,
        halt_reason=halt_reason,
        next_skill=next_skill,
        artifact=values["artifact"] or None,
        orientation=orientation,
        mode=mode,
        session=values.get("session"),
        git=values.get("git"),
        created=values.get("created"),
        parents=values.get("parents"),
        baseline=values.get("baseline"),
        taste_test=values.get("taste_test"),
        durable_flags=values.get("durable_flags"),
    )


def _parse_legacy_note(text: str) -> LegacyHandoffSlug:
    """Decode a raw preamble or a historical handoff wrapper."""
    return _parse_legacy_header(_unwrap_legacy_note(text))


@define(frozen=True)
class WorktreeScan:
    """The worktrees to search, and why the list may be short."""

    roots: tuple[Path, ...]
    error: str | None = None


@define(frozen=True)
class LegacyLookup:
    """What the search found, plus exactly where it looked."""

    outcome: LegacyOutcome
    matches: tuple[LegacyNote, ...] = field(default=())
    searched: tuple[str, ...] = field(default=())
    error: str | None = None

    @property
    def note(self) -> LegacyNote | None:
        """The one note, or None -- an ambiguity never collapses to a pick."""
        return self.matches[0] if self.outcome is LegacyOutcome.FOUND else None

    @property
    def match_paths(self) -> tuple[str, ...]:
        return tuple(str(note.path) for note in self.matches)


def _run_git(args: Sequence[str], cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def parse_worktree_list(porcelain: str) -> tuple[Path, ...]:
    """The working directories in `git worktree list --porcelain` output.

    Bare entries are dropped: a bare repository has no working tree, so it can
    never hold a `.cheese/notes` directory to search.
    """
    roots: list[Path] = []
    worktree: Path | None = None
    bare = False

    def flush() -> None:
        if worktree is not None and not bare:
            roots.append(worktree)

    for raw in porcelain.splitlines():
        line = raw.strip()
        if not line:
            flush()
            worktree, bare = None, False
            continue
        if line.startswith("worktree "):
            flush()
            worktree, bare = Path(line[len("worktree ") :]), False
        elif line == "bare":
            bare = True
    flush()
    return tuple(roots)


def worktree_roots(start: Path | str, *, run: Runner | None = None) -> WorktreeScan:
    """Every worktree to search, starting worktree first, then siblings sorted.

    The order is for reporting only -- `find_legacy_note` never lets position
    break a tie.
    """
    base = Path(start).resolve()
    output = (run or _run_git)(WORKTREE_LIST_ARGS, base)
    if output is None:
        return WorktreeScan(
            roots=(base,),
            error=f"{' '.join(WORKTREE_LIST_ARGS)} could not be run in {base}",
        )
    siblings = sorted(
        {path.resolve() for path in parse_worktree_list(output)} - {base},
        key=str,
    )
    return WorktreeScan(roots=(base, *siblings))


def find_legacy_note(
    slug: str, *, start: Path | str, run: Runner | None = None
) -> LegacyLookup:
    """Find one legacy note by safe slug or exact absolute note path."""
    reference = Path(slug).expanduser()
    if reference.is_absolute():
        try:
            try:
                path = reference.resolve(strict=True)
            except FileNotFoundError:
                path = reference.resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise LegacyLookupError(
                "absolute legacy reference could not be resolved"
            ) from exc
        if (
            path.parent.name != NOTES_DIR_PARTS[1]
            or path.parent.parent.name != NOTES_DIR_PARTS[0]
            or path.suffix != ".md"
            or _SLUG_RE.fullmatch(path.stem) is None
        ):
            raise LegacyLookupError(
                "absolute legacy reference must be a .cheese/notes/<slug>.md path"
            )
        searched = (str(path),)
        if path.is_file():
            root = path.parent.parent.parent
            return LegacyLookup(
                outcome=LegacyOutcome.FOUND,
                matches=(LegacyNote(worktree=root, path=path),),
                searched=searched,
            )
        return LegacyLookup(outcome=LegacyOutcome.NOT_FOUND, searched=searched)

    if _SLUG_RE.fullmatch(slug) is None:
        raise LegacyLookupError(
            f"slug {slug!r} must be a single path segment matching "
            f"{_SLUG_RE.pattern}"
        )
    scan = worktree_roots(start, run=run)
    searched: list[str] = []
    matches: list[LegacyNote] = []
    for root in scan.roots:
        candidate = root.joinpath(*NOTES_DIR_PARTS, f"{slug}.md")
        searched.append(str(candidate))
        if candidate.is_file():
            matches.append(LegacyNote(worktree=root, path=candidate))
    if len(matches) == 1:
        outcome = LegacyOutcome.FOUND
    elif matches:
        outcome = LegacyOutcome.AMBIGUOUS
    else:
        outcome = LegacyOutcome.NOT_FOUND
    return LegacyLookup(
        outcome=outcome,
        matches=tuple(matches),
        searched=tuple(searched),
        error=scan.error,
    )
