#!/usr/bin/env python3
"""Build and check bundles from the staged Git index in an isolated checkout."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AFFECTED = re.compile(
    r"^(src/|skills/[^/]+/(phase-contract\.yaml|scripts/[^/]+\.pyz)$|"
    r"scripts/(build_pyz|check_bundles|check_bundles_local|precommit_bundle_currency)\.py$|"
    r"\.github/workflows/build-pyz\.yml$|pyproject\.toml$|requirements-build\.txt$|"
    r"requirements/(runtime\.txt|bundles/[^/]+\.txt)$)"
)
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


def _staged_inputs() -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACDMRTUXB", "-z"],
        cwd=REPO_ROOT,
    )
    return [
        path
        for raw_path in output.split(b"\0")
        if raw_path
        for path in [os.fsdecode(raw_path)]
        if AFFECTED.match(path)
    ]


def main() -> int:
    if not _staged_inputs():
        return 0
    git_env = os.environ.copy()
    git_env["GIT_DIR"] = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-dir"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    git_env["GIT_INDEX_FILE"] = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-path", "index"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    with tempfile.TemporaryDirectory(prefix="easy-cheese-bundle-currency-") as raw:
        checkout = Path(raw) / "checkout"
        checkout.mkdir()
        subprocess.run(
            ["git", "checkout-index", "--all", f"--prefix={checkout}/"],
            cwd=REPO_ROOT,
            check=True,
        )
        for command in (
            BUILD_COMMAND,
            [sys.executable, "scripts/check_bundles.py", "--against", "index"],
        ):
            result = subprocess.run(command, cwd=checkout, env=git_env)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())