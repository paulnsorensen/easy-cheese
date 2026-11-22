"""Fail when the sdist in dist/ would publish files outside its package.

Read the allowed members from $ALLOWED, separated by whitespace. An entry that
ends in "/" allows every member under that directory. Any other entry allows
one exact member. The sdist metadata files are always allowed.
"""

from __future__ import annotations

import os
import sys
import tarfile
from collections.abc import Iterable
from pathlib import Path

ALWAYS_ALLOWED = frozenset({"LICENSE", "PKG-INFO", "pyproject.toml", ".gitignore"})


def stray_members(members: Iterable[str], allowed: Iterable[str]) -> list[str]:
    allowed = list(allowed)
    prefixes = tuple(entry for entry in allowed if entry.endswith("/"))
    exact = ALWAYS_ALLOWED | {entry for entry in allowed if not entry.endswith("/")}
    return sorted(m for m in members if m not in exact and not m.startswith(prefixes))


def sdist_members(sdist: Path) -> set[str]:
    """Return member paths relative to the sdist's top-level directory."""
    with tarfile.open(sdist) as tar:
        return {name.split("/", 1)[1] for name in tar.getnames() if "/" in name}


def main() -> int:
    sdist = next(Path("dist").glob("*.tar.gz"))
    members = sdist_members(sdist)
    stray = stray_members(members, os.environ["ALLOWED"].split())
    if stray:
        print(f"::error::sdist would publish files outside the package: {stray}")
        return 1
    print(f"sdist is package-only ({len(members)} members).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
