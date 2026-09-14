"""Shared subprocess driver for age-bench CLI tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"

_DRIVER = (
    "from easy_cheese.skills.age_bench.commands import main;"
    "import sys;"
    "sys.exit(main(sys.argv[1:]))"
)


def run_cli(
    args: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, "PYTHONPATH": str(SRC)}
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", _DRIVER, *args],
        cwd=REPO_ROOT,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
