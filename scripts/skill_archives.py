#!/usr/bin/env python3
"""Locate or build temporary skill archives for tests.

Tests execute temporary archives built from the working tree. Committed release
archives live at skills/<skill>/scripts/<skill>.pyz and need no launcher or lock.

EASY_CHEESE_PREBUILT_PYZ names a directory that test and CI jobs fill once.
Without it, the first request builds the whole set into a temporary directory.

    python3 scripts/skill_archives.py build DIR
    python3 scripts/skill_archives.py path SKILL
"""

from __future__ import annotations

import argparse
import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
PREBUILT_ENV = "EASY_CHEESE_PREBUILT_PYZ"
# The wedge commit that tools/wedge/uv.lock pins.
WEDGE = ("uv", "run", "--locked", "--project", str(REPO_ROOT / "tools" / "wedge"), "wedge")

_process_dir: Path | None = None


def build_archives(out_dir: Path) -> None:
    """Build every skill archive into ``out_dir`` as ``<skill>-<digest12>.pyz``."""
    _ = subprocess.run(
        [*WEDGE, "build", "--root", "skills", "--out", str(out_dir)],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def _cleanup_process_dir() -> None:
    if _process_dir is not None:
        shutil.rmtree(_process_dir, ignore_errors=True)


def _archive_dir() -> Path:
    """The prebuilt directory, or a per-process directory built on first use."""
    global _process_dir
    prebuilt = os.environ.get(PREBUILT_ENV)
    if prebuilt:
        return Path(prebuilt)
    if _process_dir is None:
        _process_dir = Path(tempfile.mkdtemp(prefix="easy-cheese-archives-"))
        _ = atexit.register(_cleanup_process_dir)
        build_archives(_process_dir)
    return _process_dir


def archive_path(skill: str) -> Path:
    """The archive to execute for ``skill``."""
    directory = _archive_dir()
    named = re.compile(rf"{re.escape(skill)}-[0-9a-f]{{12}}\.pyz")
    found = sorted(p for p in directory.glob(f"{skill}-*.pyz") if named.fullmatch(p.name))
    if len(found) != 1:
        raise FileNotFoundError(
            f"{directory}: expected one archive for {skill!r}, found {[p.name for p in found]}; "
            + f"rebuild the set, or unset {PREBUILT_ENV} to build on demand"
        )
    return found[0]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    _ = commands.add_parser("build", help="build every archive into DIR").add_argument(
        "out_dir", type=Path
    )
    _ = commands.add_parser("path", help="print the archive path for SKILL").add_argument(
        "skill"
    )
    args = parser.parse_args(argv[1:])
    if cast(str, args.command) == "build":
        build_archives(cast(Path, args.out_dir))
        return 0
    if not os.environ.get(PREBUILT_ENV):
        # The caller runs the archive after this process exits, so the set
        # must outlive it: leave the directory in place.
        os.environ[PREBUILT_ENV] = tempfile.mkdtemp(prefix="easy-cheese-archives-")
        build_archives(Path(os.environ[PREBUILT_ENV]))
    print(archive_path(cast(str, args.skill)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
