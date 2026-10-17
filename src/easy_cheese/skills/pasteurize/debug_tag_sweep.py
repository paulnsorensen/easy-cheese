#!/usr/bin/env python3
"""Scan a tree for /pasteurize instrumentation tags and emit a deterministic verdict.

The command exits 0 and reports the verdict in the `files`/`total` fields of
its JSON output, whether or not it finds a tag hit. A real failure
(unreadable root, unusable session tag, no Git worktree, etc.) exits 2.

/pasteurize prefixes every temporary log with one session tag such as
`[DEBUG-a4f2]`. Pass that session with `--session-tag a4f2`: the scan then
matches the exact token and nothing else, so the skill's own examples, this
module's constants, and the repository tests cannot report a false hit.

Pass `--changed-only` to restrict the scan to the files that the current Git
worktree changed. Tool artifacts (`.cheese/`, run logs, caches, archives)
never enter the scan.

`--tags` keeps the broad prefix scan for a tree whose session tag is unknown.
"""
from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TypedDict

import fromargs

DEFAULT_TAGS = (
    "[DEBUG-",
    "DEBUG:",
    "TEMP:",
    "TODO-pasteurize:",
    "# DEBUG",
    "// TEMP",
    "<!-- TODO-pasteurize",
)

# Directories that hold tool output rather than source: a hit inside one of
# them is never surviving instrumentation.
SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "site",
        ".cheese",
        ".milknado",
        ".claude",
        ".worktrees",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "target",
        "coverage",
    }
)

# File suffixes that hold tool output rather than source.
SKIP_SUFFIXES = frozenset({".log", ".jsonl", ".pyz", ".lock", ".map"})

_SESSION_TAG_RE = re.compile(r"\A[A-Za-z0-9_-]{1,32}\Z")


class _SweepResult(TypedDict):
    files: list[str]
    total: int


def session_tags(sessions: Iterable[str]) -> tuple[str, ...]:
    """Build the exact instrumentation token for each /pasteurize session tag."""
    tokens: list[str] = []
    for session in sessions:
        name = session.strip()
        if not name:
            continue
        if not _SESSION_TAG_RE.match(name):
            raise ValueError(
                f"session tag {session!r} must be 1-32 letters, digits, '-', or '_'"
            )
        tokens.append(f"[DEBUG-{name}]")
    if not tokens:
        raise ValueError("no session tag to scan for")
    return tuple(tokens)


def _is_skipped(path: Path) -> bool:
    return path.suffix in SKIP_SUFFIXES


def _is_binary(path: Path, *, sniff_bytes: int = 4096) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(sniff_bytes)
    except OSError:
        return True
    return b"\x00" in chunk


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _walk(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        found.extend(Path(dirpath) / name for name in filenames)
    return found


def changed_files(root: Path) -> list[Path]:
    """Return the files that the Git worktree at `root` added or changed."""
    commands = (
        ("diff", "--name-only", "--diff-filter=ACMR", "HEAD"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    names: set[str] = set()
    for command in commands:
        result = subprocess.run(
            ["git", "-C", str(root), *command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git reported an error")
        names.update(line for line in result.stdout.splitlines() if line)
    return [root / name for name in sorted(names)]


def sweep(
    root: Path,
    tags: tuple[str, ...],
    *,
    files: Sequence[Path] | None = None,
) -> _SweepResult:
    """Scan `files`, or all of `root`, and count the tag hits in each file."""
    hits: list[str] = []
    total = 0
    root = root.resolve()
    candidates = list(files) if files is not None else _walk(root)
    for candidate in candidates:
        full = candidate if candidate.is_absolute() else root / candidate
        if not full.is_file():
            continue
        relative = os.path.relpath(full, root)
        if any(part in SKIP_DIRS for part in Path(relative).parts):
            continue
        if _is_skipped(full) or _is_binary(full):
            continue
        text = _read_text(full)
        if text is None:
            continue
        file_hits = sum(text.count(tag) for tag in tags)
        if file_hits:
            hits.append(relative)
            total += file_hits
    hits.sort()
    return {"files": hits, "total": total}


def _resolve_tags(session_tag: str | None, tags: str | None) -> tuple[str, ...]:
    if session_tag and tags:
        raise fromargs.CliError("pass --session-tag or --tags, not both")
    if session_tag:
        try:
            return session_tags(session_tag.split(","))
        except ValueError as exc:
            raise fromargs.CliError(str(exc)) from exc
    resolved = tuple(t for t in (tags.split(",") if tags else DEFAULT_TAGS) if t)
    if not resolved:
        raise fromargs.CliError("no tags to scan for")
    return resolved


def sweep_cmd(
    *,
    root: Path | None = None,
    session_tag: str | None = None,
    tags: str | None = None,
    changed_only: bool = False,
) -> _SweepResult:
    """Scan a tree for /pasteurize instrumentation tags and report the verdict.

    Parameters
    ----------
    root
        Directory to scan (default: cwd).
    session_tag
        Comma-separated /pasteurize session tags (e.g. a4f2); matches the
        exact token [DEBUG-<tag>].
    tags
        Comma-separated tag tokens to scan for (default: pasteurize set).
    changed_only
        Scan only the files that this Git worktree changed.
    """
    root = root if root is not None else Path.cwd()
    resolved_root = root.resolve()
    if not resolved_root.exists():
        raise fromargs.CliError(f"root does not exist: {root}")
    if not resolved_root.is_dir():
        raise fromargs.CliError(f"root is not a directory: {root}")

    resolved_tags = _resolve_tags(session_tag, tags)

    files: list[Path] | None = None
    if changed_only:
        try:
            files = changed_files(resolved_root)
        except (OSError, RuntimeError) as exc:
            raise fromargs.CliError(f"--changed-only needs a Git worktree: {exc}") from exc

    return sweep(resolved_root, resolved_tags, files=files)


def build_app() -> fromargs.App:
    app = fromargs.App(
        "debug-tag-sweep",
        help="Scan a tree for /pasteurize instrumentation tags and emit a verdict.",
        help_formatter="plain",
        default_command=sweep_cmd,
    )
    return app


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())