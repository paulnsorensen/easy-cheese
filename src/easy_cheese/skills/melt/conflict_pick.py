#!/usr/bin/env python3
"""
Pick ours or theirs for conflict hunks.
For file types not handled by mergiraf (shell scripts, config files, etc.).
"""

from __future__ import annotations
# pyright: reportAny=false, reportArgumentType=false

import re

from cyclopts import App
from types import SimpleNamespace
import subprocess
import sys
from pathlib import Path

from easy_cheese.shared import cli

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


def _command(file: str, ours: bool = False, theirs: bool = False, grep: str | None = None, dry_run: bool = False) -> int:
    args = SimpleNamespace(file=file, ours=ours, theirs=theirs, grep=grep, dry_run=dry_run)

    if args.ours and args.theirs:
        print("Error: Cannot use both --ours and --theirs", file=sys.stderr)
        return 1
    if not args.ours and not args.theirs:
        print("Error: Must specify --ours or --theirs", file=sys.stderr)
        return 1

    strategy = "ours" if args.ours else "theirs"

    guidance = binary_conflict_guidance(args.file)
    if guidance is not None:
        print(f"Error: {guidance}", file=sys.stderr)
        return 1

    try:
        content = Path(args.file).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        return 1
    except UnicodeDecodeError:
        print(f"Error: {args.file} is not UTF-8 text; resolve it manually", file=sys.stderr)
        return 1

    if "<<<<<<" not in content:
        print(f"no conflicts in {args.file}")
        return 0

    resolved = resolve_hunks(content, strategy, args.grep)
    has_remaining = "<<<<<<" in resolved

    if args.dry_run:
        print(resolved)
        if has_remaining:
            print("# some conflicts remain (not matching --grep)", file=sys.stderr)
        return 0

    _ = Path(args.file).write_text(resolved, encoding="utf-8")
    if has_remaining:
        print(f"partial {args.file}: some conflicts remain")
        return 0

    add_result: subprocess.CompletedProcess[str] = run_git(["add", args.file])
    if add_result.returncode != 0:
        print(f"resolved but staging failed: {add_result.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"ok {args.file}: resolved and staged")
    return 0


app = App(name="conflict-pick")
_ = app.default(_command)


def main(argv: list[str] | None = None) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
