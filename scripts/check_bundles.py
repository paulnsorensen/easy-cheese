#!/usr/bin/env python3
"""Check every committed .pyz still matches its sources, by content.

Run after `build_pyz.py` has rebuilt the working tree: this compares each
rebuilt bundle against the copy committed at HEAD.

The comparison is per-member name, CRC, and uncompressed size rather than raw
bytes. Bundles are ZIP_DEFLATED, and two zlib builds compress identical input
to different bytes -- observed on one machine across two CPython builds
reporting the same zlib 1.3.1. A raw-byte diff would therefore fail for any
contributor whose zlib differs from whoever last committed, which is noise, not
staleness. Member CRCs still catch the signal this gate exists for: a source
edit that never made it into the committed bundle.

Byte-for-byte reproducibility is deliberately not asserted; see the spec's
accepted risk on ZIP_DEFLATED determinism.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_GLOB = "skills/*/scripts/*.pyz"


def _manifest(data: bytes) -> dict[str, tuple[int, int]]:
    """Member name -> (CRC, uncompressed size). Compressed bytes are ignored."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {i.filename: (i.CRC, i.file_size) for i in archive.infolist()}


def _committed(path: Path, against: str = "head") -> bytes | None:
    """Return the bundle blob from the requested repository snapshot."""
    ref = "HEAD" if against == "head" else ":"
    result = subprocess.run(
        ["git", "show", f"{ref}{path.as_posix()}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _describe(rebuilt: dict[str, tuple[int, int]], committed: dict[str, tuple[int, int]]) -> list[str]:
    problems = []
    for name in sorted(set(rebuilt) - set(committed)):
        problems.append(f"    + {name} (built, not in the committed bundle)")
    for name in sorted(set(committed) - set(rebuilt)):
        problems.append(f"    - {name} (committed, no longer built)")
    for name in sorted(set(rebuilt) & set(committed)):
        if rebuilt[name] != committed[name]:
            problems.append(f"    ~ {name} (content differs)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check generated bundle currency.")
    parser.add_argument("--against", choices=("head", "index"), default="head",
                        help="compare worktree bundles against HEAD or the staged index")
    args = parser.parse_args(argv)
    snapshot = "HEAD" if args.against == "head" else "index"
    layout_problems = check_layout_currency(snapshot=snapshot)
    if layout_problems:
        print("::error::.pyz bundle layout violates the skill-owned archive doctrine.")
        print("\n".join(f"  {problem}" for problem in layout_problems))
        return 1
    stale: list[str] = []
    checked = 0
    for path in sorted(REPO_ROOT.glob(BUNDLE_GLOB)):
        relative = path.relative_to(REPO_ROOT)
        committed = _committed(relative, args.against)
        if committed is None:
            print(f"new bundle, nothing to compare: {relative}")
            continue
        checked += 1
        problems = _describe(_manifest(path.read_bytes()), _manifest(committed))
        if problems:
            stale.append(f"  {relative}\n" + "\n".join(problems))
    if stale:
        print("::error::.pyz bundles are stale; rebuild and commit generated archives.")
        print("\n".join(stale))
        return 1
    print(f".pyz bundles are current ({checked} checked, by member CRC).")
    return 0




def materialize_snapshot(snapshot: str = "worktree") -> Path:
    """Materialize a stable worktree, index, or HEAD snapshot."""
    if snapshot == "worktree":
        return REPO_ROOT
    if snapshot not in {"index", "HEAD"}:
        raise ValueError("snapshot must be worktree, index, or HEAD")
    if snapshot == "HEAD":
        archive = subprocess.run(
            ["git", "archive", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
    else:
        tree = subprocess.run(
            ["git", "write-tree"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        archive = subprocess.run(
            ["git", "archive", tree],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
    target = Path(tempfile.mkdtemp(prefix=f"easy-cheese-{snapshot.lower()}-"))
    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
        if sys.version_info >= (3, 12):
            bundle.extractall(target, filter="data")
        else:
            bundle.extractall(target)
    return target


def check_layout_currency(*, snapshot: str = "worktree") -> tuple[str, ...]:
    """Check doctrine archives are same-named and contain no central common archive."""
    root = materialize_snapshot(snapshot)
    problems: list[str] = []
    for skill_dir in sorted((root / "skills").glob("*/scripts")):
        archives = sorted(skill_dir.glob("*.pyz"))
        for archive in archives:
            relative = archive.relative_to(root)
            if archive.name == "common.pyz":
                problems.append(str(relative))
            elif archive.stem != skill_dir.parent.name:
                problems.append(str(relative))
    return tuple(problems)


if __name__ == "__main__":
    sys.exit(main())
