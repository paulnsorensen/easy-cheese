#!/usr/bin/env python3
"""Conflict summary script for melt skill.

Emits structured JSON: one entry per file, with per-hunk content.
"""

from __future__ import annotations

from pathlib import Path
from typing import NotRequired, TypedDict, cast

import fromargs

from easy_cheese.shared.git_utils import (
    binary_conflict_guidance,
    get_conflicted_files,
    get_file_extension,
    get_surrounding_context,
    is_mergiraf_supported,
    parse_conflict_hunks,
)


class _Hunk(TypedDict):
    start_line: int
    end_line: int
    ours: list[str]
    base: list[str]
    theirs: list[str]


class _HunkSummary(TypedDict):
    hunk_number: int
    lines: str
    ours: list[str]
    theirs: list[str]
    has_base: bool
    context_before: list[str]
    context_after: list[str]
    base: NotRequired[list[str]]


class _Summary(TypedDict):
    path: str
    extension: str
    mergiraf_supported: bool
    hunk_count: int
    hunks: list[_HunkSummary]
    recommendation: str


class _ErrorSummary(TypedDict):
    path: str
    error: str


_OURS_CAP = 5
_THEIRS_CAP = 5
_BASE_CAP = 3
_VERBOSE_OURS_CAP = 10
_VERBOSE_THEIRS_CAP = 10
_VERBOSE_BASE_CAP = 5


def _recommendation(path: str, ext: str, hunk_count: int, mergiraf_ok: bool) -> str:
    if mergiraf_ok and hunk_count > 0:
        return "batch-resolve.py"
    if ext in ("lock", "sum") or "lock" in Path(path).name.lower():
        return "lockfile-resolve.py"
    if ext in ("sh", "bash", "zsh", "yaml", "yml", "json", "md"):
        return "conflict-pick.py"
    return "git mergetool"


def summarize_file(path: str, context_lines: int = 3) -> _Summary | _ErrorSummary:
    ext = get_file_extension(path)
    guidance = binary_conflict_guidance(path)
    if guidance is not None:
        return {
            "path": path,
            "extension": ext,
            "mergiraf_supported": False,
            "hunk_count": 0,
            "hunks": [],
            "recommendation": guidance,
        }

    try:
        content = Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return {"path": path, "error": str(e)}
    hunks = cast(list[_Hunk], parse_conflict_hunks(content))

    hunk_summaries: list[_HunkSummary] = []
    for i, hunk in enumerate(hunks, 1):
        before, after = get_surrounding_context(
            content, hunk["start_line"], hunk["end_line"], context_lines
        )

        hunk_summary: _HunkSummary = {
            "hunk_number": i,
            "lines": f"{hunk['start_line']}-{hunk['end_line']}",
            "ours": hunk["ours"],
            "theirs": hunk["theirs"],
            "has_base": bool(hunk["base"]),
            "context_before": before,
            "context_after": after,
        }

        if hunk["base"]:
            hunk_summary["base"] = hunk["base"]

        hunk_summaries.append(hunk_summary)

    mergiraf_supported = is_mergiraf_supported(path)
    hunk_count = len(hunk_summaries)
    return {
        "path": path,
        "extension": ext,
        "mergiraf_supported": mergiraf_supported,
        "hunk_count": hunk_count,
        "hunks": hunk_summaries,
        "recommendation": _recommendation(path, ext, hunk_count, mergiraf_supported),
    }


def conflict_summary(*files: str, context: int = 3) -> dict[str, list[_Summary | _ErrorSummary]]:
    """Summarize merge conflicts.

    Parameters
    ----------
    files
        Specific files (default: all conflicted files).
    context
        Lines of context to show around each hunk.
    """
    target_files = list(files) if files else get_conflicted_files()
    if not target_files:
        return {"files": []}
    return {"files": [summarize_file(f, context) for f in target_files]}


def build_app() -> fromargs.App:
    return fromargs.App(
        "conflict-summary",
        help="Summarize merge conflicts.",
        help_formatter="plain",
        default_command=conflict_summary,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
