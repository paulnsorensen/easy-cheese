#!/usr/bin/env python3
"""Check every selected-snapshot .pyz still matches its sources, by content.

The selected HEAD or index snapshot is rebuilt in isolation, then each rebuilt
bundle is compared against that snapshot's committed archive.

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
import contextlib
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_GLOB = "skills/*/scripts/*.pyz"


def _manifest(data: bytes) -> dict[str, tuple[int, int]]:
    """Member name -> (CRC, uncompressed size). Compressed bytes are ignored."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {i.filename: (i.CRC, i.file_size) for i in archive.infolist()}


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


def _rebuild_snapshot(root: Path) -> Path:
    """Rebuild bundles from ``root``'s sources, never from the live checkout."""
    output = Path(tempfile.mkdtemp(prefix="easy-cheese-rebuilt-"))
    try:
        vendor_script = root / "scripts" / "vendor_deps.py"
        if vendor_script.is_file():
            vendor_args = ["--check"] if (root / "vendor").exists() else []
            subprocess.run(
                [sys.executable, str(vendor_script), *vendor_args],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
        subprocess.run(
            [sys.executable, str(root / "scripts" / "build_pyz.py"), "--out-dir", str(output)],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return output


def _extract_snapshot(bundle: tarfile.TarFile, target: Path) -> None:
    """Extract Git archives with data filtering, including early 3.11 builds."""
    data_filter = getattr(tarfile, "data_filter", None)
    if callable(data_filter):
        bundle.extractall(target, filter="data")
        return
    root = target.resolve()
    for member in bundle.getmembers():
        if member.name.startswith("/"):
            raise ValueError(f"unsafe absolute snapshot member: {member.name}")
        destination = (root / member.name).resolve()
        if destination != root and root not in destination.parents:
            raise ValueError(f"unsafe snapshot member: {member.name}")
        if member.issym() or member.islnk():
            raise ValueError(f"links are not allowed in snapshots: {member.name}")
        trusted_filter = getattr(tarfile, "fully_trusted_filter", None)
        if callable(trusted_filter):
            bundle.extract(member, target, filter=trusted_filter)
        else:
            bundle.extract(member, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check generated bundle currency.")
    parser.add_argument("--against", choices=("head", "index"), default="head",
                        help="compare worktree bundles against HEAD or the staged index")
    args = parser.parse_args(argv)
    snapshot = "HEAD" if args.against == "head" else "index"
    with materialize_snapshot(snapshot) as snapshot_root:
        layout_problems = check_layout_currency(snapshot=snapshot)
        if layout_problems:
            print("::error::.pyz bundle layout violates the skill-owned archive doctrine.")
            print("\n".join(f"  {problem}" for problem in layout_problems))
            return 1
        try:
            rebuilt_root = _rebuild_snapshot(snapshot_root)
        except (OSError, subprocess.CalledProcessError) as exc:
            print("::error::could not rebuild selected snapshot bundles.")
            stderr = getattr(exc, "stderr", None)
            if stderr:
                print(stderr, end="")
            return 1
        stale: list[str] = []
        checked = 0
        for path in sorted(snapshot_root.glob(BUNDLE_GLOB)):
            relative = path.relative_to(snapshot_root)
            built = rebuilt_root / path.name
            if not built.is_file():
                stale.append(f"  {relative}\n    - {path.name} (committed, no longer built)")
                continue
            checked += 1
            problems = _describe(_manifest(built.read_bytes()), _manifest(path.read_bytes()))
            if problems:
                stale.append(f"  {relative}\n" + "\n".join(problems))
        shutil.rmtree(rebuilt_root, ignore_errors=True)
    if stale:
        print("::error::.pyz bundles are stale; rebuild and commit generated archives.")
        print("\n".join(stale))
        return 1
    print(f".pyz bundles are current ({checked} checked, by member CRC).")
    return 0




@contextlib.contextmanager
def materialize_snapshot(snapshot: str = "worktree") -> Iterator[Path]:
    """Materialize a stable worktree, index, or HEAD snapshot."""
    if snapshot == "worktree":
        yield REPO_ROOT
        return
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
    try:
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
            _extract_snapshot(bundle, target)
        yield target
    finally:
        shutil.rmtree(target, ignore_errors=True)


def check_layout_currency(*, snapshot: str = "worktree") -> tuple[str, ...]:
    """Check doctrine archives are same-named and contain no central common archive."""
    with materialize_snapshot(snapshot) as root:
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
