#!/usr/bin/env python3
"""Scan a tree for /pasteurize instrumentation tags and emit a deterministic verdict.

Exit codes (spec):
  0 — clean tree (no hits)
  1 — at least one tag hit (deterministic "instrumentation still present")
  2 — error (unreadable root, etc.)

Default tags come from skills/pasteurize/SKILL.md's cleanup checklist plus
common shapes used during Phase 4 instrumentation. Override with --tags.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import cli  # noqa: E402

DEFAULT_TAGS = (
    "[DEBUG-",
    "DEBUG:",
    "TEMP:",
    "TODO-pasteurize:",
    "# DEBUG",
    "// TEMP",
    "<!-- TODO-pasteurize",
)

SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv", "site"})


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


def sweep(root: Path, tags: tuple[str, ...]) -> dict:
    """Walk `root` and return {files: [...], total: N} for any file containing a tag."""
    hits: list[str] = []
    total = 0
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = Path(dirpath) / name
            if _is_binary(full):
                continue
            text = _read_text(full)
            if text is None:
                continue
            file_hits = sum(text.count(tag) for tag in tags)
            if file_hits:
                hits.append(str(full.relative_to(root)))
                total += file_hits
    hits.sort()
    return {"files": hits, "total": total}


def _run(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    if not root.exists():
        raise cli.CliError(f"root does not exist: {args.root}")
    if not root.is_dir():
        raise cli.CliError(f"root is not a directory: {args.root}")

    tags = tuple(t for t in (args.tags.split(",") if args.tags else DEFAULT_TAGS) if t)
    if not tags:
        raise cli.CliError("no tags to scan for")

    result = sweep(root, tags)

    if args.json_mode:
        cli.emit(result, json_mode=True)
    else:
        cli.emit(
            result["files"] or ["(clean)"],
            limit=args.limit,
            full=args.full,
        )
        print(f"total: {result['total']}")

    sys.exit(1 if result["total"] else 0)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="Directory to scan (default: cwd).")
    parser.add_argument("--tags", default=None,
                        help="Comma-separated tag tokens to scan for (default: pasteurize set).")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max files to list in plain output (default: 50).")
    parser.set_defaults(func=_run)


if __name__ == "__main__":
    cli.run(_setup)
