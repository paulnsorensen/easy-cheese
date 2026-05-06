#!/usr/bin/env python3
"""
Pick ours or theirs for conflict hunks.
For file types not handled by mergiraf (shell scripts, config files, etc.).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from git_utils import run_git


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
        if line.startswith("<<<<<<<"):
            in_conflict = True
            current_section = "ours"
            ours_lines, theirs_lines = [], []
            conflict_text = [line]
            continue
        if not in_conflict:
            result.append(line)
            continue

        conflict_text.append(line)
        if line.startswith("|||||||"):
            current_section = "base"
        elif line.startswith("======="):
            current_section = "theirs"
        elif line.startswith(">>>>>>>"):
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pick ours or theirs for conflict hunks")
    parser.add_argument("file", help="File to resolve")
    parser.add_argument("--ours", action="store_true", help="Take our changes for matching hunks")
    parser.add_argument(
        "--theirs", action="store_true", help="Take their changes for matching hunks"
    )
    parser.add_argument("--grep", metavar="PATTERN", help="Only resolve hunks matching this regex")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print resolved content without writing"
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.ours and args.theirs:
        print("Error: Cannot use both --ours and --theirs")
        return 1
    if not args.ours and not args.theirs:
        print("Error: Must specify --ours or --theirs")
        return 1

    strategy = "ours" if args.ours else "theirs"

    try:
        content = Path(args.file).read_text()
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}")
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

    Path(args.file).write_text(resolved)
    if has_remaining:
        print(f"partial {args.file}: some conflicts remain")
        return 0

    add_result = run_git(["add", args.file])
    if add_result.returncode != 0:
        print(f"resolved but staging failed: {add_result.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"ok {args.file}: resolved and staged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
