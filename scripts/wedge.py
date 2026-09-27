#!/usr/bin/env python3
"""Run the pinned wedge CLI.

wedge (github.com/paulnsorensen/skillz-that-grillz, `lib/`) builds each skill's
content-addressed .pyz, writes its lock and launcher, checks locks, and
publishes assets. This wrapper pins one commit so every developer machine,
`just` recipe, and test builds with the same wedge. The GitHub workflow in
.github/workflows/wedge.yml pins the same commit; a test keeps them equal.

    python3 scripts/wedge.py lock skills/<skill>     # rewrite lock + launcher
    python3 scripts/wedge.py check --root skills     # verify every lock
    python3 scripts/wedge.py build skills/<skill> --out <dir>
"""

from __future__ import annotations

import subprocess
import sys

WEDGE_REPO = "paulnsorensen/skillz-that-grillz"
WEDGE_SHA = "db88754fb3682d2984fbba375938873c1e83bdc7"
WEDGE_SPEC = f"skillz-that-grillz @ git+https://github.com/{WEDGE_REPO}@{WEDGE_SHA}#subdirectory=lib"


def wedge_command(*args: str) -> list[str]:
    """The argv that runs the pinned wedge with ``args``."""
    return ["uvx", "--from", WEDGE_SPEC, "wedge", *args]


def main(argv: list[str]) -> int:
    return subprocess.call(wedge_command(*argv[1:]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
