#!/usr/bin/env python3
"""Validate wiki page conventions under .hallouminate/wiki/. Exit 0 on success, 1 on any failure.

Checks (per .hallouminate/wiki/wiki-conventions.md):
- first non-blank line of every page is a single `# ` H1
- file stem is a kebab-case slug
- every directory with pages carries an index.md with HALLOUMINATE index markers
- every index entry between the markers resolves to an existing file
- every non-index page appears in its directory's index between the markers

Discovery is hardcoded to .hallouminate/wiki/ (ADR hallouminate-wiring-stack-004);
frontmatter/lifecycle checks are a separate seam (issue #206) and must not be added here.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_SCRIPTS = SCRIPT_DIR.parents[1] / "shared" / "scripts"
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))

from paths import KEBAB_SLUG  # noqa: E402

WIKI_ROOT = Path(".hallouminate/wiki")
INDEX_START = "<!-- HALLOUMINATE:INDEX-START -->"
INDEX_END = "<!-- HALLOUMINATE:INDEX-END -->"
LINK_TARGET_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def validate_page(path: Path) -> list[str]:
    errors: list[str] = []

    stem = path.stem
    if not KEBAB_SLUG.match(stem):
        errors.append(
            f"{path}: file stem '{stem}' is not a kebab-case slug "
            f"(1-64 chars, lowercase a-z 0-9, no leading/trailing/consecutive hyphens)"
        )

    first_line = next(
        (line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()),
        None,
    )
    if first_line is None:
        errors.append(f"{path}: page is empty (first non-blank line must be a single '# ' H1)")
    elif not re.match(r"# \S", first_line):
        errors.append(
            f"{path}: first non-blank line is not a single '# ' H1 (got: {first_line[:60]!r})"
        )

    return errors


def index_link_targets(index: Path) -> tuple[list[Path] | None, list[str]]:
    """Resolved targets of the links between the HALLOUMINATE markers, plus errors.

    Targets are None only when the markers themselves are missing or out of
    order; a dangling entry is reported but does not stop target collection.
    """
    lines = index.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(INDEX_START)
        end = lines.index(INDEX_END)
    except ValueError:
        return None, [f"{index}: missing HALLOUMINATE index markers ({INDEX_START} / {INDEX_END})"]
    if end < start:
        return None, [f"{index}: HALLOUMINATE index markers are out of order"]

    errors: list[str] = []
    targets: list[Path] = []
    for line in lines[start + 1 : end]:
        for raw_target in LINK_TARGET_RE.findall(line):
            target = index.parent / raw_target
            if not target.is_file():
                errors.append(
                    f"{index}: index entry '{raw_target}' points at a missing file"
                )
            targets.append(target.resolve())
    return targets, errors


def validate_directory(directory: Path, pages: list[Path]) -> list[str]:
    index = directory / "index.md"
    if index not in pages:
        return [f"{directory}: directory has wiki pages but no index.md"]

    targets, errors = index_link_targets(index)
    if targets is None:
        return errors

    listed = set(targets)
    for page in pages:
        if page.name != "index.md" and page.resolve() not in listed:
            errors.append(
                f"{page}: page is not listed in {index} between the HALLOUMINATE markers"
            )
    return errors


def main() -> int:
    if not WIKI_ROOT.is_dir():
        print(f"ERROR: {WIKI_ROOT}/ directory not found", file=sys.stderr)
        return 1

    pages = sorted(WIKI_ROOT.rglob("*.md"))
    if not pages:
        print(f"ERROR: no wiki pages found under {WIKI_ROOT}/", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for page in pages:
        all_errors.extend(validate_page(page))

    by_dir: dict[Path, list[Path]] = {}
    for page in pages:
        by_dir.setdefault(page.parent, []).append(page)
    for directory in sorted(by_dir):
        all_errors.extend(validate_directory(directory, by_dir[directory]))

    if all_errors:
        for e in all_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(
            f"\nFAIL: {len(all_errors)} error(s) across {len(pages)} wiki page(s)",
            file=sys.stderr,
        )
        return 1

    print(f"OK: validated {len(pages)} wiki page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
