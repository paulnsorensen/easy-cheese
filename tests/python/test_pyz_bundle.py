"""The single easy-cheese.pyz must bundle every skill-runtime module and dispatch
every subcommand self-contained — imports resolve from inside the zip, never from a
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

SUBCOMMANDS = [
    "batch-resolve",
    "conflict-pick",
    "conflict-summary",
    "detect-squash-residue",
    "lockfile-resolve",
    "pr_plan_to_branches",
    "validate_decomposition",
    "validate_manifest",
    "validate_pr_plan",
    "pr-status",
    "curd-count",
]


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("pyz")
    result = subprocess.run(
        [sys.executable, str(BUILD), "--out-dir", str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    pyz = out / "easy-cheese.pyz"
    assert pyz.exists(), result.stdout + result.stderr
    return pyz


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


@pytest.mark.parametrize("sub", SUBCOMMANDS)
def test_every_subcommand_resolves_inside_bundle(bundle: Path, sub: str) -> None:
    # --help loads the module (and its shared imports) before any tool logic; a
    # broken bundle surfaces as an import failure when runpy loads the module.
    result = _run(bundle, sub, "--help")
    combined = result.stdout + result.stderr
    assert "ModuleNotFoundError" not in combined, combined
    assert "Traceback" not in combined, combined


def test_unknown_subcommand_is_rejected(bundle: Path) -> None:
    result = _run(bundle, "no-such-subcommand")
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_melt_subcommand_executes_with_forwarded_args(bundle: Path, tmp_path: Path) -> None:
    """A real subcommand runs end-to-end through the bundle: proves the dispatcher
    forwards positional + flag args, the shared git_utils import resolves, and
    conflict-pick (not some other tool) actually ran."""
    conflict = tmp_path / "f.txt"
    conflict.write_text(
        "before\n<<<<<<< HEAD\nOURS_LINE\n=======\nTHEIRS_LINE\n>>>>>>> branch\nafter\n"
    )
    result = _run(bundle, "conflict-pick", str(conflict), "--theirs", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "THEIRS_LINE" in result.stdout
    assert "OURS_LINE" not in result.stdout
    assert "<<<<<<<" not in result.stdout


def test_cheese_factory_routing_is_subcommand_specific(bundle: Path, tmp_path: Path) -> None:
    """The same empty document yields validator-specific errors, proving the
    dispatcher routes each subcommand to its own tool (no cross-wiring) and that
    each validator executes — not merely imports — through the bundle."""
    empty = tmp_path / "empty.json"
    empty.write_text("{}")

    manifest = _run(bundle, "validate_manifest", str(empty))
    pr_plan = _run(bundle, "validate_pr_plan", str(empty))

    assert manifest.returncode == 1
    assert pr_plan.returncode == 1
    assert "manifest.slug is required" in manifest.stderr
    assert "manifest.slug" not in pr_plan.stderr
    assert "shape must be one of single" in pr_plan.stderr
