"""Each skill ships a self-contained <skill>.pyz containing only its own scripts
plus the shared modules it imports. Every subcommand must dispatch and resolve its
imports from inside the zip — no sys.path traversal, and no other skill's code.
"""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build_pyz.py"

# Every shipped bundle (real skills + the cross-cutting "common" bundle) and the
# subcommands it must dispatch. Keys are .pyz basenames under the build out-dir.
SKILL_SUBCOMMANDS = {
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
        "wiring_topo_sort",
        "manifest_update",
    ],
    "affinage": ["pr-status"],
    "mold": ["curd-count", "agent_scope_diff"],
    "briesearch": ["route_research", "pick_tavily_rung", "confidence_cap"],
    "cheese": ["classify"],
    "cheez-search": ["pick_kind"],
    "cook": ["self_eval_check"],
    "hard-cheese": ["append-attempt", "freshness-check"],
    "pasteurize": ["debug-tag-sweep", "repro-rerun"],
    "ultracook": ["phase_decision"],
    "common": [
        "slugify",
        "write_handoff_artifact",
        "read_handoff_slug",
        "findings_cli",
        "gates_cli",
        "paths_cli",
        "handoff_cli",
    ],
}


@pytest.fixture(scope="module")
def bundles(tmp_path_factory) -> Path:
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
    [(skill, sub) for skill, subs in SKILL_SUBCOMMANDS.items() for sub in subs],
)
def test_subcommand_resolves_inside_bundle(bundles: Path, skill: str, sub: str) -> None:
    result = _run(bundles / f"{skill}.pyz", sub, "--help")
    combined = result.stdout + result.stderr
    assert "ModuleNotFoundError" not in combined, combined
    assert "Traceback" not in combined, combined


@pytest.mark.parametrize("skill", list(SKILL_SUBCOMMANDS))
def test_unknown_subcommand_is_rejected(bundles: Path, skill: str) -> None:
    result = _run(bundles / f"{skill}.pyz", "no-such-subcommand")
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_melt_subcommand_executes_with_forwarded_args(bundles: Path, tmp_path: Path) -> None:
    """A real subcommand runs end-to-end through the bundle: proves argv forwarding,
    the shared git_utils import resolving, and correct routing."""
    conflict = tmp_path / "f.txt"
    conflict.write_text(
        "before\n<<<<<<< HEAD\nOURS_LINE\n=======\nTHEIRS_LINE\n>>>>>>> branch\nafter\n"
    )
    result = _run(bundles / "melt.pyz", "conflict-pick", str(conflict), "--theirs", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "THEIRS_LINE" in result.stdout
    assert "OURS_LINE" not in result.stdout
    assert "<<<<<<<" not in result.stdout


def test_cheese_factory_routing_is_subcommand_specific(bundles: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    manifest = _run(bundles / "cheese-factory.pyz", "validate_manifest", str(empty))
    pr_plan = _run(bundles / "cheese-factory.pyz", "validate_pr_plan", str(empty))
    assert manifest.returncode == 1
    assert pr_plan.returncode == 1
    assert "manifest.slug is required" in manifest.stderr
    assert "manifest.slug" not in pr_plan.stderr
    assert "shape must be one of single" in pr_plan.stderr


def test_bundle_carries_only_its_own_skill(bundles: Path) -> None:
    """The O(n) guarantee: a skill's bundle excludes other skills' scripts and any
    shared module it does not import."""
    melt = set(zipfile.ZipFile(bundles / "melt.pyz").namelist())
    assert "conflict_pick.py" in melt
    assert "git_utils.py" in melt  # the one shared module melt imports
    assert "validate_manifest.py" not in melt  # cheese-factory's script
    assert "pr_status.py" not in melt  # affinage's script
    assert "manifest_io.py" not in melt  # shared module melt does not import
    assert "severity.py" not in melt  # shared module no bundled skill imports

    affinage = set(zipfile.ZipFile(bundles / "affinage.pyz").namelist())
    assert "pr_status.py" in affinage
    assert not (affinage & {"git_utils.py", "manifest_io.py", "schema.py"})  # no shared needed


def test_common_slugify_executes_end_to_end(bundles: Path) -> None:
    """The fanned-out common bundle resolves cli from inside the zip and runs."""
    result = _run(
        bundles / "common.pyz", "slugify", "from-task",
        "--task", "Add retry to the upload client", "--json",
    )
    assert result.returncode == 0, result.stderr
    assert '"slug": "add-retry-upload-client"' in result.stdout


def test_common_bundle_carries_clis_plus_libs_not_skill_scripts(bundles: Path) -> None:
    """common.pyz ships the cross-cutting CLI entrypoints and the shared libs they
    import (e.g. cli), but no skill-specific script."""
    common = set(zipfile.ZipFile(bundles / "common.pyz").namelist())
    assert {"slugify.py", "findings_cli.py", "write_handoff_artifact.py"} <= common
    assert "cli.py" in common  # the shared argparse helper every CLI imports
    assert "conflict_pick.py" not in common  # melt's
    assert "self_eval_check.py" not in common  # cook's
