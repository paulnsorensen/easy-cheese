#!/usr/bin/env python3
"""Run the bundle currency gate against a temporary checkout of the index."""

from __future__ import annotations

import fcntl
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _wheel_cache(requirements: Path, common_dir: Path) -> Path:
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    cache_root = common_dir / "bundle-currency-wheel-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    cache = cache_root / digest
    with (cache_root / f"{digest}.lock").open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if cache.is_dir():
            if not any(cache.glob("*.whl")):
                raise RuntimeError(f"wheel cache is empty: {cache}")
            return cache
        with tempfile.TemporaryDirectory(prefix=f".{digest}-", dir=cache_root) as staging:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    "--no-deps",
                    "--only-binary=:all:",
                    "--require-hashes",
                    "--requirement",
                    str(requirements),
                    "--dest",
                    staging,
                ],
                cwd=requirements.parent,
                check=True,
            )
            if not list(Path(staging).glob("*.whl")):
                raise RuntimeError(f"pip download produced no wheels in {staging}")
            os.replace(staging, cache)
    return cache


def _absolute_git_path(path: str) -> str:
    candidate = Path(path)
    return str(candidate if candidate.is_absolute() else (REPO_ROOT / candidate).resolve())


def main() -> int:
    git_dir = _absolute_git_path(
        subprocess.check_output(
            ["git", "rev-parse", "--git-dir"], cwd=REPO_ROOT, text=True
        ).strip()
    )
    index_file = _absolute_git_path(
        subprocess.check_output(
            ["git", "rev-parse", "--git-path", "index"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    )
    common_dir = _absolute_git_path(
        subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"], cwd=REPO_ROOT, text=True
        ).strip()
    )

    with tempfile.TemporaryDirectory(prefix="bundle-currency-") as raw_tmp:
        checkout = Path(raw_tmp) / "repo"
        checkout.mkdir()
        subprocess.run(
            ["git", "checkout-index", "--all", f"--prefix={checkout}/"],
            cwd=REPO_ROOT,
            check=True,
        )
        env = os.environ.copy()
        env["GIT_DIR"] = git_dir
        env["GIT_INDEX_FILE"] = index_file
        cache = _wheel_cache(checkout / "requirements-vendor.txt", Path(common_dir))
        offline_env = env | {"PIP_NO_INDEX": "1", "PIP_FIND_LINKS": str(cache)}
        commands = (
            ([sys.executable, "scripts/vendor_deps.py"], offline_env),
            ([sys.executable, "scripts/build_pyz.py"], env),
            ([sys.executable, "scripts/check_bundles.py", "--against", "index"], env),
        )
        for command, command_env in commands:
            result = subprocess.run(command, cwd=checkout, env=command_env)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
