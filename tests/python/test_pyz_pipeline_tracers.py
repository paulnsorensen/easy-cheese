"""Outer pipeline tracers (Cut RED evidence for pyz-pipeline-contracts).

Each test drives a declared outer seam — the build subprocess, the bundle
dispatcher, or a just recipe — and fails until the corresponding pipeline
contract is implemented. Sandboxed runs copy the working tree into tmp_path so
no tracer ever mutates the project.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WITNESS_COMMON_CONSUMER = (
    "On main the invocation fails because skills/cook/scripts/common.pyz is "
    "never built; after cook joins COMMON_CONSUMERS it resolves and exits 0 "
    "on --help"
)
WITNESS_DEAD_REGISTRATION = (
    "On main press.pyz red-gate dispatches successfully; asserting exit 2 "
    "usage-rejection fails until the dead registration is pruned"
)
WITNESS_SCRIPT_MAP = (
    "On main no src/PYTHON_SCRIPTS.md exists; the gate must fail the build "
    "until the checked-in map byte-matches the registries"
)


def _copy_project_subset(dest: Path, dirs: tuple[str, ...], files: tuple[str, ...]) -> None:
    ignore = shutil.ignore_patterns("__pycache__", ".DS_Store")
    dest.mkdir(parents=True, exist_ok=True)
    for name in dirs:
        shutil.copytree(REPO_ROOT / name, dest / name, ignore=ignore)
    for name in files:
        shutil.copy2(REPO_ROOT / name, dest / name)


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)


def _output(proc: subprocess.CompletedProcess[str]) -> str:
    return f"{proc.stdout}\n{proc.stderr}"


def test_cook_ships_common_bundle(tmp_path: Path) -> None:
    bundle = REPO_ROOT / "skills" / "cook" / "scripts" / "common.pyz"
    assert bundle.is_file(), WITNESS_COMMON_CONSUMER
    isolated = tmp_path / "common.pyz"
    shutil.copy2(bundle, isolated)
    proc = _run([sys.executable, str(isolated), "read_handoff_slug", "--help"], cwd=tmp_path)
    detail = f"exit={proc.returncode}\n{_output(proc)}"
    assert proc.returncode == 0, f"{WITNESS_COMMON_CONSUMER}\n{detail}"


def test_press_red_gate_registration_pruned() -> None:
    proc = _run(
        [sys.executable, "skills/press/scripts/press.pyz", "red-gate", "--help"],
        cwd=REPO_ROOT,
    )
    detail = f"exit={proc.returncode}\n{_output(proc)}"
    assert proc.returncode == 2 and "usage: <pyz>" in proc.stderr, (
        f"{WITNESS_DEAD_REGISTRATION}\n{detail}"
    )


def test_script_map_gate(tmp_path: Path) -> None:
    sandbox = tmp_path / "project"
    _copy_project_subset(
        sandbox,
        dirs=("scripts", "src", "shared", "skills", "vendor"),
        files=("requirements-vendor.txt",),
    )
    (sandbox / "src" / "PYTHON_SCRIPTS.md").unlink(missing_ok=True)
    proc = _run(
        [sys.executable, "scripts/build_pyz.py", "--out-dir", str(tmp_path / "out")],
        cwd=sandbox,
    )
    detail = f"exit={proc.returncode}\n{_output(proc)}"
    assert proc.returncode != 0, f"{WITNESS_SCRIPT_MAP}\n{detail}"
    assert "PYTHON_SCRIPTS.md" in _output(proc), f"{WITNESS_SCRIPT_MAP}\n{detail}"
