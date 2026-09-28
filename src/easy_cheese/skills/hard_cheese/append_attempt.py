#!/usr/bin/env python3
"""Atomically append an attempt row to `.cheese/hard-cheese/<slug>.md`.

Spec: skill-scripts Wave 2 — confirmation-bias killer for /hard-cheese.
Replaces hand-stenciled markdown-table writes so concurrent runs (or a
retried gate) cannot clobber the attempt log.

Usage:

    python3 skills/hard-cheese/scripts/hard-cheese.pyz append-attempt \\
        --slug <slug> --status PASS --score 4 \\
        --feedback "diff-grounded, names invariants" \\
        --explanation "<user explanation verbatim>"

Row shape (matches the hard-cheese audit-trail schema):

    | <ISO8601 timestamp> | <HEAD short sha> | <status> | <score> | <feedback> | <explanation> |

First write creates the file with a matching header. Re-invocations append
below the existing rows. An advisory lock sidecar (`fcntl.flock` on POSIX,
`msvcrt.locking` on Windows) serialises concurrent appends; the read-modify-write
itself is atomic via tmpfile + `os.replace`.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import fromargs

try:
    import fcntl  # POSIX advisory file locks
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None

try:
    import msvcrt  # Windows advisory file locks
except ImportError:  # pragma: no cover - exercised only on POSIX
    msvcrt = None

REPO_ROOT = Path.cwd()


def _lock(fd: int, *, exclusive: bool) -> None:
    """Acquire (exclusive=True) or release an advisory lock on fd, cross-platform."""
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_UN)
    else:  # pragma: no cover - Windows only
        assert msvcrt is not None
        msvcrt.locking(fd, msvcrt.LK_LOCK if exclusive else msvcrt.LK_UNLCK, 1)


def _artifact_dir() -> Path:
    """Resolved at call time so tests can redirect via $HARD_CHEESE_ARTIFACT_DIR."""
    override = os.environ.get("HARD_CHEESE_ARTIFACT_DIR")
    return Path(override) if override else REPO_ROOT / ".cheese" / "hard-cheese"

HEADER = (
    "| timestamp | head_sha | status | score | feedback | explanation |\n"
    "| --- | --- | --- | --- | --- | --- |\n"
)


def _validate_slug(slug: str) -> str:
    if not slug:
        raise fromargs.CliError("--slug must not be empty")
    if ".." in slug or "/" in slug or "\\" in slug:
        raise fromargs.CliError(f"--slug rejects path traversal: {slug!r}")
    return slug


def _head_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=False, cwd=str(REPO_ROOT),
        )
        sha = out.stdout.strip()
        return sha or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _escape_cell(value: str) -> str:
    # Markdown table cells: collapse newlines, escape pipes so the row stays one line.
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>").replace("\r", "")


def _atomic_rewrite(target: Path, new_text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            _ = fh.write(new_text)
        _ = Path(tmp_name).replace(target)
    except Exception:
        # Best-effort cleanup; do not mask the original error.
        with contextlib.suppress(OSError):
            Path(tmp_name).unlink()
        raise


def _append_row(target: Path, row: str) -> None:
    """Read existing content (or seed with header), append row, atomic rewrite."""
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if not existing:
        existing = HEADER
    elif not existing.endswith("\n"):
        existing += "\n"
    _atomic_rewrite(target, existing + row)


def _with_flock(lock_path: Path, fn: Callable[[], None]) -> None:
    """Run fn() while holding an exclusive advisory lock on lock_path.

    Uses POSIX ``fcntl.flock`` where available and falls back to
    ``msvcrt.locking`` on Windows so the concurrency guard is not silently lost.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # O_CREAT so concurrent processes share the same lockfile inode. 0o600
    # so the lockfile is not world-readable (CodeQL py/overly-permissive-file).
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _lock(fd, exclusive=True)
        fn()
    finally:
        try:
            _lock(fd, exclusive=False)
        finally:
            os.close(fd)


def append_attempt(
    *, slug: str, status: str, score: str, feedback: str, explanation: str
) -> dict[str, object]:
    """Atomically append an attempt row to .cheese/hard-cheese/<slug>.md.

    Parameters
    ----------
    slug
        artifact slug (no slashes, no '..')
    status
        PASS | FAIL | ERROR | LOGGED | FAILED
    score
        SOLO level 1-5 (or '-' when status=LOGGED)
    feedback
        one-line judge feedback
    explanation
        user explanation verbatim
    """
    slug = _validate_slug(slug)
    artifact_dir = _artifact_dir()
    target = artifact_dir / f"{slug}.md"
    lock = artifact_dir / f".{slug}.lock"
    timestamp = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    row = f"| {timestamp} | {_head_sha()} | {_escape_cell(status)} | {_escape_cell(score)} | {_escape_cell(feedback)} | {_escape_cell(explanation)} |\n"
    _with_flock(lock, lambda: _append_row(target, row))
    try:
        rel = target.relative_to(REPO_ROOT)
        artifact_str = str(rel)
    except ValueError:
        artifact_str = str(target)
    return {"slug": slug, "artifact": artifact_str, "appended": True}


def build_app() -> fromargs.App:
    app = fromargs.App(
        "append-attempt",
        help="Atomically append an attempt row to .cheese/hard-cheese/<slug>.md.",
        help_formatter="plain",
        default_command=append_attempt,
    )
    return app


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())