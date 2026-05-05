#!/usr/bin/env python3
"""Conflict summary script for melt skill.

Default output is terse and LLM-oriented: one line of metadata per file,
followed by per-hunk content with minimal framing. Use --verbose for the
markdown-formatted human view, or --json for structured output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from git_utils import (
    get_conflicted_files,
    get_file_extension,
    get_surrounding_context,
    is_mergiraf_supported,
    parse_conflict_hunks,
)

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


def summarize_file(path: str, context_lines: int = 3) -> dict:
    try:
        content = Path(path).read_text()
    except Exception as e:
        return {"path": path, "error": str(e)}

    ext = get_file_extension(path)
    hunks = parse_conflict_hunks(content)

    summary = {
        "path": path,
        "extension": ext,
        "mergiraf_supported": is_mergiraf_supported(path),
        "hunk_count": len(hunks),
        "hunks": [],
    }

    for i, hunk in enumerate(hunks, 1):
        before, after = get_surrounding_context(
            content, hunk["start_line"], hunk["end_line"], context_lines
        )

        hunk_summary = {
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

        summary["hunks"].append(hunk_summary)

    summary["recommendation"] = _recommendation(
        path, ext, summary["hunk_count"], summary["mergiraf_supported"]
    )
    return summary


def _capped_terse(items: list, cap: int, marker: str) -> list[str]:
    out = [f"    {marker} {line}" for line in items[:cap]]
    extra = len(items) - cap
    if extra > 0:
        out.append(f"    {marker}({extra} more)")
    return out


def _render_hunk_terse(hunk: dict) -> list[str]:
    lines = [f"  [h{hunk['hunk_number']} L{hunk['lines']}]"]
    lines.extend(f"    {ctx}" for ctx in hunk["context_before"])
    lines.extend(_capped_terse(hunk["ours"], _OURS_CAP, "+"))
    if hunk["has_base"]:
        lines.extend(_capped_terse(hunk.get("base", []), _BASE_CAP, "|"))
    lines.extend(_capped_terse(hunk["theirs"], _THEIRS_CAP, "-"))
    lines.extend(f"    {ctx}" for ctx in hunk["context_after"])
    return lines


def format_terse_output(summaries: list) -> str:
    """Compact, LLM-oriented format. One header line per file, minimal hunk framing."""
    if not summaries:
        return "no conflicts"

    lines = ["# legend: +ours |base -theirs"]
    for s in summaries:
        if "error" in s:
            lines.append(f"{s['path']} error: {s['error']}")
            continue
        mergiraf = "y" if s["mergiraf_supported"] else "n"
        lines.append(
            f"{s['path']} hunks={s['hunk_count']} ext={s['extension']} "
            f"mergiraf={mergiraf} rec={s['recommendation']}"
        )
        for hunk in s["hunks"]:
            lines.extend(_render_hunk_terse(hunk))

    return "\n".join(lines)


def _capped_verbose(items: list, cap: int, marker: str) -> list[str]:
    out = [f"  {marker} {line}" for line in items[:cap]]
    if len(items) > cap:
        out.append(f"  ... ({len(items) - cap} more lines)")
    return out


def _render_hunk_verbose(hunk: dict) -> list[str]:
    lines = [f"### Hunk {hunk['hunk_number']} (lines {hunk['lines']})"]
    if hunk["context_before"]:
        lines.append("Context before:")
        lines.extend(f"  {ctx}" for ctx in hunk["context_before"])
    lines.append("OURS:")
    lines.extend(_capped_verbose(hunk["ours"], _VERBOSE_OURS_CAP, "+"))
    if hunk["has_base"]:
        lines.append("BASE:")
        lines.extend(_capped_verbose(hunk.get("base", []), _VERBOSE_BASE_CAP, "|"))
    lines.append("THEIRS:")
    lines.extend(_capped_verbose(hunk["theirs"], _VERBOSE_THEIRS_CAP, "-"))
    if hunk["context_after"]:
        lines.append("Context after:")
        lines.extend(f"  {ctx}" for ctx in hunk["context_after"])
    lines.append("")
    return lines


def format_verbose_output(summaries: list) -> str:
    """Markdown-formatted human view, retained for --verbose."""
    if not summaries:
        return "No conflicted files found."

    lines = [f"# Conflict Summary — {len(summaries)} file(s)", ""]

    for summary in summaries:
        if "error" in summary:
            lines.append(f"## {summary['path']}")
            lines.append(f"Error: {summary['error']}")
            lines.append("")
            continue

        status = "supported" if summary["mergiraf_supported"] else "not supported"
        lines.append(f"## {summary['path']}")
        lines.append(
            f"Extension: .{summary['extension']} | Mergiraf: {status} | "
            f"Hunks: {summary['hunk_count']}"
        )
        lines.append("")

        for hunk in summary["hunks"]:
            lines.extend(_render_hunk_verbose(hunk))

        lines.append(f"**Recommendation:** {summary['recommendation']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Summarize merge conflicts. Default output is terse for LLMs."
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    parser.add_argument(
        "--verbose", action="store_true", help="Emit markdown-formatted human view."
    )
    parser.add_argument(
        "--context", type=int, default=3, help="Lines of context to show (default: 3)."
    )
    parser.add_argument("files", nargs="*", help="Specific files (default: all conflicted files).")

    args = parser.parse_args()

    files = args.files if args.files else get_conflicted_files()

    if not files:
        if args.json:
            print(json.dumps({"files": []}))
        else:
            print("no conflicts")
        return 0

    summaries = [summarize_file(f, args.context) for f in files]

    if args.json:
        print(json.dumps({"files": summaries}, indent=2))
    elif args.verbose:
        print(format_verbose_output(summaries))
    else:
        print(format_terse_output(summaries))

    return 0


if __name__ == "__main__":
    sys.exit(main())
