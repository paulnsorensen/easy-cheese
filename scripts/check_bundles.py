#!/usr/bin/env python3
"""Check every rebuilt .pyz still matches the git copy it will ship.

Run after `build_pyz.py` has rebuilt the working tree. Compares each rebuilt
bundle to a git blob — HEAD in CI, the index for `just check` and the
pre-commit hook — by member name, CRC, and uncompressed size rather than raw bytes.

Bundles are ZIP_DEFLATED, and two zlib builds compress identical input to
different bytes. A raw-byte diff would fail for any contributor whose zlib
differs from whoever last committed. Member CRCs still catch the signal this
gate exists for: a source edit that never made it into the compared blob.

Byte-for-byte reproducibility is deliberately not asserted; see the spec's
accepted risk on ZIP_DEFLATED determinism.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_GLOB = "skills/*/scripts/*.pyz"
_MISSING_MARKERS = (
    b"exists on disk, but not in",
    b"does not exist in",
    b"path does not exist",
    b"does not exist",
)


def _manifest(data: bytes) -> dict[str, tuple[int, int]]:
    """Member name -> (CRC, uncompressed size). Compressed bytes are ignored."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {i.filename: (i.CRC, i.file_size) for i in archive.infolist()}


def classify_git_show(returncode: int, stderr: bytes) -> str:
    """ok | missing | error. Missing comparison blobs are stale bundles."""
    if returncode == 0:
        return "ok"
    lowered = stderr.lower()
    if any(marker in lowered for marker in _MISSING_MARKERS):
        return "missing"
    return "error"


def _spec(path: Path, against: str) -> str:
    posix = path.as_posix()
    return f":{posix}" if against == "index" else f"HEAD:{posix}"


def _git_blob(path: Path, against: str) -> bytes | None:
    """The blob at HEAD or the index, or None when the path is absent."""
    result = subprocess.run(
        ["git", "show", _spec(path, against)],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    kind = classify_git_show(result.returncode, result.stderr)
    if kind == "ok":
        return result.stdout
    if kind == "missing":
        return None
    sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
    raise RuntimeError(
        f"git show {_spec(path, against)!r} failed (exit {result.returncode})"
    )


def _describe(
    rebuilt: dict[str, tuple[int, int]], compared: dict[str, tuple[int, int]]
) -> list[str]:
    problems = []
    for name in sorted(set(rebuilt) - set(compared)):
        problems.append(f"    + {name} (built, not in the compared bundle)")
    for name in sorted(set(compared) - set(rebuilt)):
        problems.append(f"    - {name} (compared, no longer built)")
    for name in sorted(set(rebuilt) & set(compared)):
        if rebuilt[name] != compared[name]:
            problems.append(f"    ~ {name} (content differs)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--against",
        choices=("head", "index"),
        default="head",
        help="blob to compare the rebuilt worktree against (default: HEAD)",
    )
    args = parser.parse_args(argv)
    stale: list[str] = []
    checked = 0
    found = list(sorted(REPO_ROOT.glob(BUNDLE_GLOB)))
    if not found:
        print("::error::no .pyz bundles found under skills/*/scripts/", file=sys.stderr)
        return 1
    try:
        for path in found:
            relative = path.relative_to(REPO_ROOT)
            compared = _git_blob(relative, args.against)
            if compared is None:
                stale.append(
                    f"  {relative}\n"
                    "    + bundle is missing from the compared git tree"
                )
                continue
            checked += 1
            problems = _describe(_manifest(path.read_bytes()), _manifest(compared))
            if problems:
                stale.append(f"  {relative}\n" + "\n".join(problems))
    except RuntimeError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

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