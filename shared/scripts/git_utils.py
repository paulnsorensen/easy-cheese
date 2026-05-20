#!/usr/bin/env python3
"""Shared git utilities for melt skill."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(args: list[str], capture_output: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def get_conflicted_files() -> list[str]:
    result = run_git(["diff", "--name-only", "--diff-filter=U"])
    if result.returncode != 0:
        return []
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


def extract_stages(path: str) -> tuple[str | None, str | None, str | None]:
    """Returns (base, ours, theirs) from git stage slots; None for any unavailable stage."""
    base = ours = theirs = None

    # Stage 1 = common ancestor (base)
    result = run_git(["show", f":1:{path}"])
    if result.returncode == 0:
        base = result.stdout

    # Stage 2 = current branch (ours/HEAD)
    result = run_git(["show", f":2:{path}"])
    if result.returncode == 0:
        ours = result.stdout

    # Stage 3 = incoming branch (theirs)
    result = run_git(["show", f":3:{path}"])
    if result.returncode == 0:
        theirs = result.stdout

    return base, ours, theirs


def get_file_extension(path: str) -> str:
    return Path(path).suffix.lstrip(".")


def is_mergiraf_supported(path: str) -> bool:
    ext = get_file_extension(path)
    # Languages supported by mergiraf (Tree-sitter based)
    supported_extensions = {
        "rs",
        "go",
        "py",
        "ts",
        "tsx",
        "js",
        "jsx",
        "java",
        "scala",
        "c",
        "cc",
        "cpp",
        "cxx",
        "h",
        "hpp",
        "hxx",
        "rb",
        "php",
        "cs",
        "swift",
        "md",
    }
    return ext.lower() in supported_extensions


def parse_conflict_hunks(content: str) -> list[dict]:
    """Handles both diff3 (with ||||||| base) and standard (without base) conflict markers."""
    lines = content.split("\n")
    hunks = []
    current_hunk = None
    section = None

    for i, line in enumerate(lines, 1):
        if line.startswith("<<<<<<<"):
            current_hunk = {
                "start_line": i,
                "end_line": None,
                "ours": [],
                "base": [],
                "theirs": [],
                "marker_ours": line,
                "marker_theirs": None,
            }
            section = "ours"
        elif line.startswith("|||||||") and current_hunk:
            section = "base"
        elif line.startswith("=======") and current_hunk:
            section = "theirs"
        elif line.startswith(">>>>>>>") and current_hunk:
            current_hunk["end_line"] = i
            current_hunk["marker_theirs"] = line
            hunks.append(current_hunk)
            current_hunk = None
            section = None
        elif current_hunk and section:
            current_hunk[section].append(line)

    return hunks


def get_surrounding_context(
    content: str, start_line: int, end_line: int, context_lines: int = 3
) -> tuple[list[str], list[str]]:
    lines = content.split("\n")

    # Before context (avoiding conflict markers)
    before_start = max(0, start_line - context_lines - 1)
    before = []
    for i in range(before_start, start_line - 1):
        line = lines[i]
        if not any(marker in line for marker in ["<<<<<<", "======", ">>>>>>", "||||||"]):
            before.append(f"{i + 1}: {line}")

    after_end = min(len(lines), end_line + context_lines)
    after = []
    for i in range(end_line, after_end):
        line = lines[i]
        if not any(marker in line for marker in ["<<<<<<", "======", ">>>>>>", "||||||"]):
            after.append(f"{i + 1}: {line}")

    return before, after


def detect_lockfile_type(path: str) -> str | None:
    filename = Path(path).name.lower()

    lockfile_map = {
        "cargo.lock": "cargo",
        "package-lock.json": "npm",
        "yarn.lock": "yarn",
        "pnpm-lock.yaml": "pnpm",
        "poetry.lock": "poetry",
        "pipfile.lock": "pipenv",
        "uv.lock": "uv",
        "gemfile.lock": "bundler",
        "go.sum": "go",
    }

    return lockfile_map.get(filename)
