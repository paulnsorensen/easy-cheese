#!/usr/bin/env python3
"""
Pick ours or theirs for conflict hunks.
For file types not handled by mergiraf (shell scripts, config files, etc.).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TypedDict

import fromargs

from easy_cheese.shared.git_utils import (
    MARKER_BASE,
    MARKER_OURS,
    MARKER_SEP,
    MARKER_THEIRS,
    binary_conflict_guidance,
    run_git,
)


def _resolve_conflict_block(
    conflict_text: list[str],
    ours_lines: list[str],
    theirs_lines: list[str],
    strategy: str,
    grep_pattern: str | None,
) -> list[str]:
    if grep_pattern and not re.search(grep_pattern, "\n".join(conflict_text)):
        return conflict_text
    return ours_lines if strategy == "ours" else theirs_lines


def resolve_hunks(content: str, strategy: str, grep_pattern: str | None = None) -> str:
    result: list[str] = []
    in_conflict = False
    current_section: str | None = None
    ours_lines: list[str] = []
    theirs_lines: list[str] = []
    conflict_text: list[str] = []

    for line in content.split("\n"):
        if line.startswith(MARKER_OURS):
            in_conflict = True
            current_section = "ours"
            ours_lines, theirs_lines = [], []
            conflict_text = [line]
            continue
        if not in_conflict:
            result.append(line)
            continue

        conflict_text.append(line)
        if line.startswith(MARKER_BASE):
            current_section = "base"
        elif line.startswith(MARKER_SEP):
            current_section = "theirs"
        elif line.startswith(MARKER_THEIRS):
            result.extend(
                _resolve_conflict_block(
                    conflict_text, ours_lines, theirs_lines, strategy, grep_pattern
                )
            )
            in_conflict = False
            current_section = None
        elif current_section == "ours":
            ours_lines.append(line)
        elif current_section == "theirs":
            theirs_lines.append(line)

    if in_conflict:
        # Unterminated conflict — preserve partial markers to avoid silent data loss
        result.extend(conflict_text)

    return "\n".join(result)


class _PickResult(TypedDict, total=False):
    path: str
    resolved: bool
    remaining: bool
    message: str
    content: str


def conflict_pick(
    file: str,
    *,
    ours: bool = False,
    theirs: bool = False,
    grep: str | None = None,
    dry_run: bool = False,
) -> _PickResult:
    """Pick ours or theirs for conflict hunks in one file.

    Parameters
    ----------
    file
        File to resolve.
    ours
        Take our changes for matching hunks.
    theirs
        Take their changes for matching hunks.
    grep
        Only resolve hunks matching this regex.
    dry_run
        Return resolved content without writing.
    """
    if ours and theirs:
        raise fromargs.CliError("Cannot use both --ours and --theirs", exit_code=1)
    if not ours and not theirs:
        raise fromargs.CliError("Must specify --ours or --theirs", exit_code=1)

    strategy = "ours" if ours else "theirs"

    guidance = binary_conflict_guidance(file)
    if guidance is not None:
        raise fromargs.CliError(guidance, exit_code=1)

    try:
        content = Path(file).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise fromargs.CliError(f"File not found: {file}", exit_code=1) from None
    except UnicodeDecodeError:
        raise fromargs.CliError(
            f"{file} is not UTF-8 text; resolve it manually", exit_code=1
        ) from None

    if "<<<<<<" not in content:
        return {"path": file, "resolved": False, "remaining": False, "message": "no conflicts"}

    resolved = resolve_hunks(content, strategy, grep)
    has_remaining = "<<<<<<" in resolved

    if dry_run:
        return {
            "path": file,
            "resolved": not has_remaining,
            "remaining": has_remaining,
            "message": "dry run",
            "content": resolved,
        }

    _ = Path(file).write_text(resolved, encoding="utf-8")
    if has_remaining:
        return {
            "path": file,
            "resolved": False,
            "remaining": True,
            "message": "some conflicts remain",
        }

    add_result: subprocess.CompletedProcess[str] = run_git(["add", file])
    if add_result.returncode != 0:
        raise fromargs.CliError(
            f"resolved but staging failed: {add_result.stderr.strip()}", exit_code=1
        )
    return {"path": file, "resolved": True, "remaining": False, "message": "resolved and staged"}


def build_app() -> fromargs.App:
    return fromargs.App(
        "conflict-pick",
        help="Pick ours or theirs for conflict hunks.",
        help_formatter="plain",
        default_command=conflict_pick,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
