#!/usr/bin/env python3
"""Atomically append an attempt row to `.cheese/hard-cheese/<slug>.md`.

Spec: skill-scripts Wave 2 — confirmation-bias killer for /hard-cheese.
Replaces hand-stenciled markdown-table writes so concurrent runs (or a
retried gate) cannot clobber the attempt log.

Usage:

    python3 skills/hard-cheese/scripts/append-attempt.py \\
        --slug <slug> --status PASS --score 4 \\
        --feedback "diff-grounded, names invariants" \\
        --explanation "<user explanation verbatim>"

Row shape (matches the hard-cheese audit-trail schema):

    | <ISO8601 timestamp> | <HEAD short sha> | <status> | <score> | <feedback> | <explanation> |

First write creates the file with a matching header. Re-invocations append
below the existing rows. A POSIX `fcntl.flock` sidecar serialises concurrent
appends; the read-modify-write itself is atomic via tmpfile + `os.rename`.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import os
import subprocess
import tempfile
from pathlib import Path

import cli  # noqa: E402

REPO_ROOT = Path.cwd()


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
        raise cli.CliError("--slug must not be empty")
    if ".." in slug or "/" in slug or "\\" in slug:
        raise cli.CliError(f"--slug rejects path traversal: {slug!r}")
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
            fh.write(new_text)
        os.rename(tmp_name, target)
    except Exception:
        # Best-effort cleanup; do not mask the original error.
        try:
            os.unlink(tmp_name)
        except OSError:
            # tmpfile already cleaned up by the OS or never created; swallow
            # so the original write error propagates uncovered.
            pass
        raise


def _append_row(target: Path, row: str) -> None:
    """Read existing content (or seed with header), append row, atomic rewrite."""
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if not existing:
        existing = HEADER
    elif not existing.endswith("\n"):
        existing += "\n"
    _atomic_rewrite(target, existing + row)


def _with_flock(lock_path: Path, fn) -> None:
    """Run fn() while holding an exclusive POSIX flock on lock_path."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # O_CREAT so concurrent processes share the same lockfile inode. 0o600
    # so the lockfile is not world-readable (CodeQL py/overly-permissive-file).
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        fn()
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _cmd_append(args: argparse.Namespace) -> None:
    slug = _validate_slug(args.slug)
    artifact_dir = _artifact_dir()
    target = artifact_dir / f"{slug}.md"
    lock = artifact_dir / f".{slug}.lock"
    timestamp = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    row = "| {} | {} | {} | {} | {} | {} |\n".format(
        timestamp,
        _head_sha(),
        _escape_cell(args.status),
        _escape_cell(str(args.score)),
        _escape_cell(args.feedback),
        _escape_cell(args.explanation),
    )
    _with_flock(lock, lambda: _append_row(target, row))
    try:
        rel = target.relative_to(REPO_ROOT)
        artifact_str = str(rel)
    except ValueError:
        artifact_str = str(target)
    cli.emit({"slug": slug, "artifact": artifact_str, "appended": True}, json_mode=args.json_mode)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--slug", required=True, help="artifact slug (no slashes, no '..')")
    parser.add_argument("--status", required=True, help="PASS | FAIL | ERROR | LOGGED | FAILED")
    parser.add_argument("--score", required=True, help="SOLO level 1-5 (or '-' when status=LOGGED)")
    parser.add_argument("--feedback", required=True, help="one-line judge feedback")
    parser.add_argument("--explanation", required=True, help="user explanation verbatim")
    parser.set_defaults(func=_cmd_append)


if __name__ == "__main__":
    cli.run(_setup)
