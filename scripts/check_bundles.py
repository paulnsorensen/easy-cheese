#!/usr/bin/env python3
"""Check every committed .pyz still matches its sources, by content.

Run after `build_pyz.py` has rebuilt the working tree: this compares each
rebuilt bundle against the copy committed at HEAD.

The comparison is per-member name, CRC, and uncompressed size rather than raw
bytes. Shiv assembles deterministic wheel members, but ZIP metadata can vary
between toolchains. A raw-byte diff would therefore fail for contributors whose
runtime differs from whoever last committed, which is noise, not staleness.
Member CRCs still catch the signal this gate exists for: a source edit that never
made it into the committed bundle.

Committed common.pyz archives are rejected: each skill owns a same-named archive.
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
    """Source member name -> (CRC, uncompressed size).

    Shiv generates bootstrap metadata, console-script wrappers, and RECORD files
    from the host interpreter, so those host-dependent members are not a source
    staleness signal.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {
            i.filename: (i.CRC, i.file_size)
            for i in archive.infolist()
            if i.filename != "environment.json"
            and not i.filename.startswith("site-packages/bin/")
            and not i.filename.endswith(".dist-info/RECORD")
        }


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
    for path in sorted(REPO_ROOT.glob("skills/*/scripts/common.pyz")):
        stale.append(f"  {path.relative_to(REPO_ROOT)} (obsolete shared bundle)")
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
