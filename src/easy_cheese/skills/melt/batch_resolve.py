#!/usr/bin/env python3
"""Batch conflict resolution using mergiraf.

Run without --apply for a dry run. Pass --debug <path> to inspect one file
without changing the working tree.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

import fromargs

from easy_cheese.shared.git_utils import (
    binary_conflict_guidance,
    extract_stages,
    get_conflicted_files,
    is_mergiraf_supported,
    run_git,
)


class _ResolveResult(TypedDict):
    path: str
    supported: bool
    resolved: bool
    message: str


class _DebugResult(TypedDict):
    path: str
    supported: bool
    tempdir: str | None
    merged_path: str | None
    log_path: str | None
    conflict_markers: int | None
    exit_code: int | None
    message: str


class _BatchResult(TypedDict):
    mode: str
    results: list[_ResolveResult]
    resolved: int
    total: int


def resolve_file(path: str, dry_run: bool = True, verbose: bool = False) -> _ResolveResult:
    result: _ResolveResult = {
        "path": path,
        "supported": is_mergiraf_supported(path),
        "resolved": False,
        "message": "",
    }

    guidance = binary_conflict_guidance(path)
    if guidance is not None:
        result["supported"] = False
        result["message"] = guidance
        return result

    if not result["supported"]:
        result["message"] = "unsupported file type"
        return result

    base, ours, theirs = extract_stages(path)

    if base is None or ours is None or theirs is None:
        result["message"] = "could not extract all three stages"
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = str(Path(tmpdir) / "base")
        ours_path = str(Path(tmpdir) / "ours")
        theirs_path = str(Path(tmpdir) / "theirs")
        merged_path = str(Path(tmpdir) / "merged")

        _ = Path(base_path).write_text(base)
        _ = Path(ours_path).write_text(ours)
        _ = Path(theirs_path).write_text(theirs)

        cmd: list[str] = [
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
            _ = Path(path).write_text(merged_content)
            add_result: subprocess.CompletedProcess[str] = run_git(["add", path])
            if add_result.returncode != 0:
                result["resolved"] = False
                result["message"] = f"resolved but staging failed: {add_result.stderr.strip()}"
            else:
                result["message"] = "resolved and staged"

    return result


def debug_file(path: str, keep_dir: str | None = None) -> _DebugResult:
    """Run mergiraf with debug logging; never modifies the working tree."""
    result: _DebugResult = {
        "path": path,
        "supported": is_mergiraf_supported(path),
        "tempdir": None,
        "merged_path": None,
        "log_path": None,
        "conflict_markers": None,
        "exit_code": None,
        "message": "",
    }

    guidance = binary_conflict_guidance(path)
    if guidance is not None:
        result["supported"] = False
        result["message"] = guidance
        return result

    if not result["supported"]:
        result["message"] = "unsupported file type"
        return result

    base, ours, theirs = extract_stages(path)
    if base is None or ours is None or theirs is None:
        result["message"] = "could not extract all three stages"
        return result

    tmpdir = keep_dir or tempfile.mkdtemp(prefix="melt-debug-")
    base_path = str(Path(tmpdir) / "base")
    ours_path = str(Path(tmpdir) / "ours")
    theirs_path = str(Path(tmpdir) / "theirs")
    merged_path = str(Path(tmpdir) / "merged")
    log_path = str(Path(tmpdir) / "mergiraf.log")

    _ = Path(base_path).write_text(base)
    _ = Path(ours_path).write_text(ours)
    _ = Path(theirs_path).write_text(theirs)

    cmd: list[str] = [
        "mergiraf", "merge",
        base_path, ours_path, theirs_path,
        "-o", merged_path,
        "-p", path,
    ]
    env = os.environ.copy()
    env["RUST_LOG"] = "mergiraf=debug"
    merge_result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    _ = Path(log_path).write_text(merge_result.stderr or "")

    result["tempdir"] = tmpdir
    result["log_path"] = log_path
    result["exit_code"] = merge_result.returncode

    try:
        merged_content = Path(merged_path).read_text()
        result["merged_path"] = merged_path
        result["conflict_markers"] = merged_content.count("<<<<<<<")
        if result["conflict_markers"] == 0:
            result["message"] = "clean merge"
        else:
            result["message"] = f"{result['conflict_markers']} conflict marker(s) remain"
    except FileNotFoundError:
        result["message"] = f"mergiraf produced no merged file (exit {merge_result.returncode})"

    return result


def batch_resolve(
    *files: str,
    apply: bool = False,
    verbose: bool = False,
    debug: str | None = None,
) -> _DebugResult | _BatchResult:
    """Resolve conflicts with mergiraf, or inspect one file with --debug.

    Parameters
    ----------
    files
        Specific files (default: all conflicted files).
    apply
        Apply resolutions (default is dry-run).
    verbose
        Emit mergiraf debug logs (RUST_LOG=mergiraf=debug) to stderr.
    debug
        Inspect mergiraf on a single file: keeps the tempdir, captures
        RUST_LOG=mergiraf=debug, and reports artifact paths. No working
        tree changes.
    """
    if not shutil.which("mergiraf"):
        raise fromargs.CliError(
            "mergiraf not found — install with: cargo install mergiraf", exit_code=1
        )

    if debug:
        return debug_file(debug)

    dry_run = not apply
    target_files = list(files) if files else get_conflicted_files()
    results = [resolve_file(p, dry_run=dry_run, verbose=verbose) for p in target_files]
    resolved = sum(1 for r in results if r["resolved"])
    return {
        "mode": "dry-run" if dry_run else "apply",
        "results": results,
        "resolved": resolved,
        "total": len(results),
    }


def build_app() -> fromargs.App:
    return fromargs.App(
        "batch-resolve",
        help="Resolve conflicts with mergiraf.",
        help_formatter="plain",
        default_command=batch_resolve,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())