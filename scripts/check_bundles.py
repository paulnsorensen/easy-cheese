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

import io
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_GLOB = "skills/*/scripts/*.pyz"


def _manifest(data: bytes) -> dict[str, tuple[int, int]]:
    """Member name -> (CRC, uncompressed size). Compressed bytes are ignored."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {i.filename: (i.CRC, i.file_size) for i in archive.infolist()}


def _committed(path: Path) -> bytes | None:
    """The blob at HEAD, or None when the bundle is newly added."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
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


def main() -> int:
    stale: list[str] = []
    checked = 0
    for path in sorted(REPO_ROOT.glob(BUNDLE_GLOB)):
        relative = path.relative_to(REPO_ROOT)
        committed = _committed(relative)
        if committed is None:
            print(f"new bundle, nothing to compare: {relative}")
            continue
        checked += 1
        problems = _describe(_manifest(path.read_bytes()), _manifest(committed))
        if problems:
            stale.append(f"  {relative}\n" + "\n".join(problems))

    if stale:
        print(
            "::error::.pyz bundles are stale; run 'python3 scripts/build_pyz.py' "
            "and commit the generated skills/*/scripts/*.pyz files."
        )
        print("\n".join(stale))
        return 1

    print(f".pyz bundles are current ({checked} checked, by member CRC).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
