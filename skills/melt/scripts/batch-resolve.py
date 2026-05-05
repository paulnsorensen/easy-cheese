#!/usr/bin/env python3
"""Batch conflict resolution using mergiraf.

Default output is terse: one line per file plus a one-line summary.
Use --verbose for markdown-sectioned output. Run without --apply for dry-run.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from git_utils import (
    extract_stages,
    get_conflicted_files,
    is_mergiraf_supported,
    run_git,
)


def check_mergiraf_available() -> bool:
    try:
        result = subprocess.run(["mergiraf", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def resolve_file(path: str, dry_run: bool = True, verbose: bool = False) -> dict:
    """Attempt to resolve a single file with mergiraf. Returns status dict."""
    result = {
        "path": path,
        "supported": is_mergiraf_supported(path),
        "resolved": False,
        "message": "",
    }

    if not result["supported"]:
        result["message"] = "unsupported file type"
        return result

    base, ours, theirs = extract_stages(path)

    if base is None or ours is None or theirs is None:
        result["message"] = "could not extract all three stages"
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = os.path.join(tmpdir, "base")
        ours_path = os.path.join(tmpdir, "ours")
        theirs_path = os.path.join(tmpdir, "theirs")
        merged_path = os.path.join(tmpdir, "merged")

        Path(base_path).write_text(base)
        Path(ours_path).write_text(ours)
        Path(theirs_path).write_text(theirs)

        cmd = [
            "mergiraf",
            "merge",
            base_path,
            ours_path,
            theirs_path,
            "-o",
            merged_path,
            "-p",
            path,
        ]

        if verbose:
            env = os.environ.copy()
            env["RUST_LOG"] = "mergiraf=debug"
            merge_result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if merge_result.stderr:
                print(f"DEBUG {path}:\n{merge_result.stderr}", file=sys.stderr)
        else:
            merge_result = subprocess.run(cmd, capture_output=True, text=True)

        try:
            merged_content = Path(merged_path).read_text()
        except FileNotFoundError:
            err = merge_result.stderr.strip() or f"exit {merge_result.returncode}"
            result["message"] = f"mergiraf failed: {err}"
            return result

        if "<<<<<<<" in merged_content:
            result["message"] = "conflicts remain after mergiraf"
            return result

        result["resolved"] = True

        if dry_run:
            result["message"] = "would resolve cleanly"
        else:
            Path(path).write_text(merged_content)
            add_result = run_git(["add", path])
            if add_result.returncode != 0:
                result["resolved"] = False
                result["message"] = f"resolved but staging failed: {add_result.stderr.strip()}"
            else:
                result["message"] = "resolved and staged"

    return result


def format_terse(results: list, dry_run: bool) -> str:
    if not results:
        return "no conflicts"

    lines = []
    for r in results:
        marker = "ok" if r["resolved"] else "--"
        lines.append(f"{marker} {r['path']}: {r['message']}")

    resolved = sum(1 for r in results if r["resolved"])
    mode = "dry-run" if dry_run else "apply"
    lines.append(f"{resolved}/{len(results)} resolved ({mode})")
    return "\n".join(lines)


def format_verbose(results: list, dry_run: bool) -> str:
    resolved = [r for r in results if r["resolved"]]
    unresolved = [r for r in results if not r["resolved"]]

    lines = [
        "# Batch Resolution Summary",
        f"Mode: {'dry-run' if dry_run else 'apply'}",
        f"Total: {len(results)} | Resolved: {len(resolved)} | Unresolved: {len(unresolved)}",
        "",
    ]

    if resolved:
        lines.append("## Resolved")
        for r in resolved:
            lines.append(f"  ok {r['path']}: {r['message']}")
        lines.append("")

    if unresolved:
        lines.append("## Needs Manual Resolution")
        for r in unresolved:
            lines.append(f"  -- {r['path']}: {r['message']}")
        lines.append("")

    if dry_run and resolved:
        lines.append("Run with --apply to apply these resolutions.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Batch resolve conflicts using mergiraf.")
    parser.add_argument(
        "--apply", action="store_true", help="Apply resolutions (default is dry-run)."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Markdown-formatted output and mergiraf debug logs."
    )
    parser.add_argument("files", nargs="*", help="Specific files (default: all conflicted files).")

    args = parser.parse_args()

    if not check_mergiraf_available():
        print("mergiraf not found — install with: cargo install mergiraf", file=sys.stderr)
        return 1

    dry_run = not args.apply
    files = args.files if args.files else get_conflicted_files()

    if not files:
        print("no conflicts")
        return 0

    results = [resolve_file(p, dry_run=dry_run, verbose=args.verbose) for p in files]

    if args.verbose:
        print(format_verbose(results, dry_run))
    else:
        print(format_terse(results, dry_run))

    unresolved = [r for r in results if not r["resolved"]]
    return 0 if not unresolved else 1


if __name__ == "__main__":
    sys.exit(main())
