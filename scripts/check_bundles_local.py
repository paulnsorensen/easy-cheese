#!/usr/bin/env python3
"""Check current worktree sources and bundles without mutating the worktree."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_COMMAND = (
    "uv",
    "run",
    "--no-project",
    "--with-requirements",
    "requirements-build.txt",
    "--with-requirements",
    "requirements/runtime.txt",
    "python",
    "scripts/build_pyz.py",
)


def _materialize_files(destination: Path) -> None:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO_ROOT,
    )
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe repository path: {relative}")
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            raise RuntimeError(f"unsupported repository entry: {relative}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="easy-cheese-local-bundles-") as raw:
        root = Path(raw)
        checkout = root / "checkout"
        baseline = root / "baseline"
        _materialize_files(checkout)
        baseline.mkdir()
        for bundle in checkout.glob("skills/*/scripts/*.pyz"):
            target = baseline / bundle.relative_to(checkout)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundle, target)
        result = subprocess.run(BUILD_COMMAND, cwd=checkout)
        if result.returncode:
            return result.returncode
        return subprocess.run(
            [sys.executable, "scripts/check_bundles.py", "--baseline-root", str(baseline)],
            cwd=checkout,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
