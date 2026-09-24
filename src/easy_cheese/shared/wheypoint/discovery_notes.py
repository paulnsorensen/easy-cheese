"""Legacy note discovery: worktree-scoped in one repository, or machine-wide
with an optional `rg` accelerator.

`rg` is never required: bundle doctrine forbids a required external
executable, so every search falls back to a pure-Python `os.walk`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from easy_cheese.shared import paths

from . import legacy as legacy_mod
from .discovery_types import Candidate, Hit

_RG_TIMEOUT_SECONDS = 20
_PRUNE_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", ".cache", "target", "dist"}
)
_NOTE_GLOB = "**/.cheese/notes/*.md"
_SEARCH_ROOTS_ENV = "EASY_CHEESE_SEARCH_ROOTS"

_project_key_cache: dict[Path, str] = {}


def _project_scope_roots(start: Path | str) -> tuple[list[Path], str | None]:
    seen: dict[Path, None] = {}
    for root in (
        *legacy_mod.repository_chain(start),
        *legacy_mod.worktree_roots(start).roots,
    ):
        seen.setdefault(root)
    return list(seen), legacy_mod.worktree_roots(start).error


def _machine_scope_roots(extra_roots: Sequence[Path | str]) -> list[Path]:
    raw = os.environ.get(_SEARCH_ROOTS_ENV, "").strip()
    parts = raw.split(os.pathsep) if raw else [str(Path.home())]
    seen: dict[Path, None] = {}
    for part in (*parts, *extra_roots):
        if not str(part):
            continue
        seen.setdefault(Path(part).expanduser())
    return list(seen)


def _walk_notes(root: Path) -> list[Path]:
    found: list[Path] = []
    if root.is_file():
        return found
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _PRUNE_DIRS]
        current = Path(dirpath)
        if current.name == "notes" and current.parent.name == ".cheese":
            found.extend(current / name for name in filenames if name.endswith(".md"))
    return found


def _rg_notes(roots: list[Path]) -> list[Path] | None:
    existing = [str(root) for root in roots if root.exists()]
    if not existing:
        return []
    # The same prune set as the walk, so both backends return the same hits.
    prune_globs = [
        arg for name in sorted(_PRUNE_DIRS) for arg in ("-g", f"!**/{name}/**")
    ]
    try:
        completed = subprocess.run(
            [
                "rg",
                "--files",
                "--hidden",
                "--no-ignore",
                "-g",
                _NOTE_GLOB,
                *prune_globs,
                *existing,
            ],
            capture_output=True,
            text=True,
            timeout=_RG_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode not in (0, 1):
        return None
    return [Path(line) for line in completed.stdout.splitlines() if line]


def _find_notes(roots: list[Path]) -> tuple[list[Path], str, list[str]]:
    errors: list[str] = []
    if shutil.which("rg") is not None:
        found = _rg_notes(roots)
        if found is not None:
            return found, "rg", errors
        errors.append("rg failed or timed out; fell back to a directory walk")
    walked: list[Path] = []
    for root in roots:
        walked.extend(_walk_notes(root))
    return walked, "walk", errors


def _cached_project_key(root: Path) -> str:
    if root not in _project_key_cache:
        _project_key_cache[root] = paths.project_key(root)
    return _project_key_cache[root]


def _headline(text: str) -> str:
    """The first non-empty line without its heading marks.

    A handwritten note has no preamble, so its title stands in for the
    orientation line in a listing.
    """
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


def _note_candidate(path: Path) -> Candidate:
    resolved = path.resolve()
    worktree = resolved.parent.parent.parent
    project = _cached_project_key(worktree)
    slug = resolved.stem
    try:
        updated = resolved.stat().st_mtime
    except OSError:
        updated = 0.0
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        hit = Hit(
            source="note",
            project=project,
            ref=slug,
            status=None,
            next=None,
            orientation="",
            updated=updated,
            path=resolved,
            resume=resolved,
            problem=f"note could not be read: {exc}",
        )
        return Candidate(hit=hit, slug=slug, haystack=slug.lower())
    try:
        parsed = legacy_mod.parse_legacy_note(text)
    except legacy_mod.LegacyDecodeError as exc:
        hit = Hit(
            source="note",
            project=project,
            ref=slug,
            status=None,
            next=None,
            orientation=_headline(text),
            updated=updated,
            path=resolved,
            resume=resolved,
            problem=f"note is unparseable: {exc}",
        )
        return Candidate(hit=hit, slug=slug, haystack=f"{slug}\n{text}".lower())
    hit = Hit(
        source="note",
        project=project,
        ref=slug,
        status=parsed.status,
        next=parsed.next_skill,
        orientation=parsed.orientation,
        updated=updated,
        path=resolved,
        resume=resolved,
    )
    haystack = f"{slug}\n{parsed.orientation}\n{text}".lower()
    return Candidate(hit=hit, slug=slug, haystack=haystack)


def discover(
    *, start: Path | str, machine: bool, roots: Sequence[Path | str] = ()
) -> tuple[list[Candidate], list[str], list[str]]:
    """Every legacy note as a candidate, plus what was searched and errors.

    Project scope searches the repository chain and every worktree of the
    repository containing `start`. Machine scope searches
    `$EASY_CHEESE_SEARCH_ROOTS` (default `~`) plus any caller-given `roots`,
    and always also looks in `~/.cheese/notes`.
    """
    errors: list[str] = []
    if machine:
        search_roots = _machine_scope_roots(roots)
    else:
        search_roots, root_error = _project_scope_roots(start)
        if root_error is not None:
            errors.append(root_error)
    found, backend, backend_errors = _find_notes(search_roots)
    errors.extend(backend_errors)
    searched = [f"{backend}:{root}" for root in search_roots]
    if machine:
        always = Path.home() / ".cheese" / "notes"
        searched.append(f"always:{always}")
        if always.is_dir():
            found = [*found, *sorted(always.glob("*.md"))]
    candidates = [_note_candidate(path) for path in sorted(set(found))]
    return candidates, searched, errors
