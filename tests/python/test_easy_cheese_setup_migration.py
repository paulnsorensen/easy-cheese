from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "skills/easy-cheese-setup/scripts/easy-cheese-setup.pyz"


def _run(config: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HALLOUMINATE_CONFIG"] = str(config)
    env["XDG_DATA_HOME"] = str(config.parent / "data")
    return subprocess.run([sys.executable, str(BUNDLE), *args], env=env, text=True, capture_output=True)


def test_global_migrate_legacy_dry_run_preserves_config(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    original = '[[corpus]]\nname = "cheese-global"\npaths = ["~/.cheese"]\n'
    _ = config.write_text(original)
    result = _run(config, "global", "--migrate-legacy")
    assert result.returncode == 0
    assert config.read_text() == original
    assert "remove legacy" in result.stdout


def test_global_migrate_legacy_apply_removes_only_legacy_block(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    _ = config.write_text('[[corpus]]\nname = "cheese-global"\npaths = ["~/.cheese"]\n\n[settings]\nkeep = true\n')
    result = _run(config, "global", "--migrate-legacy", "--apply")
    assert result.returncode == 0
    text = config.read_text()
    assert "cheese-global" not in text
    assert "keep = true" in text


@pytest.mark.parametrize("leg", ["local", "doctor"])
def test_migrate_legacy_rejected_for_other_legs(tmp_path: Path, leg: str) -> None:
    config = tmp_path / "config.toml"
    result = _run(config, leg, "--migrate-legacy")
    assert result.returncode == 2
    assert "only valid for global" in result.stderr
