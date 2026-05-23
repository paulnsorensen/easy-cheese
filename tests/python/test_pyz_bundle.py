"""Each consuming skill must build a self-contained .pyz that dispatches every
subcommand with its shared imports resolving from inside the zip — never from a
sys.path traversal to the plugin root (which does not survive `gh skill install`).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build_pyz.py"

EXPECTED = {
    "melt": [
        "batch-resolve",
        "conflict-pick",
        "conflict-summary",
        "detect-squash-residue",
        "lockfile-resolve",
    ],
    "cheese-factory": [
        "pr_plan_to_branches",
        "validate_decomposition",
        "validate_manifest",
        "validate_pr_plan",
    ],
}


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("pyz")
    result = subprocess.run(
        [sys.executable, str(BUILD), "--out-dir", str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return out


def _run(pyz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # Run from the bundle's own dir with PYTHONPATH stripped, so the only way an
    # import can resolve is from inside the .pyz itself.
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        cwd=str(pyz.parent),
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.parametrize(
    "skill,sub",
    [(skill, sub) for skill, subs in EXPECTED.items() for sub in subs],
)
def test_subcommand_imports_resolve_inside_pyz(built: Path, skill: str, sub: str) -> None:
    pyz = built / f"{skill}.pyz"
    assert pyz.exists(), f"{pyz} was not built"
    result = _run(pyz, sub, "--help")
    combined = result.stdout + result.stderr
    # A broken bundle surfaces as an import failure when runpy loads the module.
    assert "ModuleNotFoundError" not in combined, combined
    assert "Traceback" not in combined, combined


@pytest.mark.parametrize("skill", list(EXPECTED))
def test_unknown_subcommand_is_rejected(built: Path, skill: str) -> None:
    result = _run(built / f"{skill}.pyz", "no-such-subcommand")
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_melt_subcommand_executes_with_forwarded_args(built: Path, tmp_path: Path) -> None:
    """A real subcommand runs end-to-end through the bundle: proves the dispatcher
    forwards positional + flag args, the shared git_utils import resolves, and
    conflict-pick (not some other tool) actually ran."""
    conflict = tmp_path / "f.txt"
    conflict.write_text(
        "before\n<<<<<<< HEAD\nOURS_LINE\n=======\nTHEIRS_LINE\n>>>>>>> branch\nafter\n"
    )
    result = _run(built / "melt.pyz", "conflict-pick", str(conflict), "--theirs", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "THEIRS_LINE" in result.stdout
    assert "OURS_LINE" not in result.stdout
    assert "<<<<<<<" not in result.stdout


def test_cheese_factory_routing_is_subcommand_specific(built: Path, tmp_path: Path) -> None:
    """The same empty document yields validator-specific errors, proving the
    dispatcher routes each subcommand to its own tool (no cross-wiring) and that
    each validator executes — not merely imports — through the bundle."""
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    pyz = built / "cheese-factory.pyz"

    manifest = _run(pyz, "validate_manifest", str(empty))
    pr_plan = _run(pyz, "validate_pr_plan", str(empty))

    assert manifest.returncode == 1
    assert pr_plan.returncode == 1
    assert "manifest.slug is required" in manifest.stderr
    assert "manifest.slug" not in pr_plan.stderr
    assert "shape must be one of single" in pr_plan.stderr
