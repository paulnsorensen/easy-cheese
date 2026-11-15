"""The Cook bundle rejects retired preparation commands without side effects."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COOK_ARCHIVE = ROOT / "skills" / "cook" / "scripts" / "cook.pyz"


@pytest.mark.parametrize("command", ["accept", "prepare", "resubmit"])
def test_cook_pyz_rejects_retired_entry_command(tmp_path: Path, command: str) -> None:
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    artifact_root = tmp_path / "artifacts"
    result = subprocess.run(
        [
            sys.executable,
            str(COOK_ARCHIVE),
            command,
            str(tmp_path / "missing-pointer.json"),
            "--artifact-root",
            str(artifact_root),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("usage: <pyz>")
    assert "Traceback" not in result.stderr
    assert not artifact_root.exists()
    assert list(tmp_path.iterdir()) == []
