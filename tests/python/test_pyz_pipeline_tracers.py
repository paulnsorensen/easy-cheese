"""Outer pipeline tracers (Cut RED evidence for pyz-pipeline-contracts).

Each test drives a declared outer seam — the build subprocess, the bundle
dispatcher, or a just recipe — and fails until the corresponding pipeline
contract is implemented. Sandboxed runs copy the working tree into tmp_path so
no tracer ever mutates the project.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WITNESS_IMPORT_CLOSURE = (
    "On main, staging a script whose function-body imports an undeclared "
    "cross-directory module builds cleanly; the closure gate must exit "
    "nonzero naming the unresolved module and its importer"
)
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
WITNESS_BUNDLE_CURRENCY = (
    "On main just check passes with a stale bundle because check_bundles.py "
    "is not wired into the recipe"
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


def test_import_closure_gate(tmp_path: Path) -> None:
    sandbox = tmp_path / "project"
    _copy_project_subset(
        sandbox,
        dirs=("scripts", "src", "shared", "vendor"),
        files=("requirements-vendor.txt",),
    )
    probe = sandbox / "src" / "melt" / "batch-resolve.py"
    probe.write_text(
        probe.read_text(encoding="utf-8")
        + "\n\ndef _cut_red_tracer_probe():\n    import wiring_topo_sort\n",
        encoding="utf-8",
    )
    proc = _run(
        [sys.executable, "scripts/build_pyz.py", "--out-dir", str(tmp_path / "out"), "melt"],
        cwd=sandbox,
    )
    detail = f"exit={proc.returncode}\n{_output(proc)}"
    assert proc.returncode != 0, f"{WITNESS_IMPORT_CLOSURE}\n{detail}"
    assert "wiring_topo_sort" in _output(proc), f"{WITNESS_IMPORT_CLOSURE}\n{detail}"
    assert "batch_resolve" in _output(proc) or "batch-resolve" in _output(proc), (
        f"{WITNESS_IMPORT_CLOSURE}\n{detail}"
    )


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


def test_bundle_currency_wired_into_check(tmp_path: Path) -> None:
    sandbox = tmp_path / "project"
    _copy_project_subset(
        sandbox,
        dirs=("scripts", "src", "shared", "skills", "vendor"),
        files=("requirements-vendor.txt", "justfile"),
    )
    git = ["git", "-c", "user.email=cut@tracer", "-c", "user.name=cut", "-c", "commit.gpgsign=false"]
    assert _run([*git, "init", "-q"], cwd=sandbox).returncode == 0
    assert _run([*git, "add", "-A", "-f"], cwd=sandbox).returncode == 0
    assert _run([*git, "commit", "-q", "-m", "base"], cwd=sandbox).returncode == 0

    match = re.search(
        r"^check:(.*)$",
        (sandbox / "justfile").read_text(encoding="utf-8"),
        re.M,
    )
    assert match is not None, WITNESS_BUNDLE_CURRENCY
    deps = match.group(1).split()
    detail = f"check deps={deps}"
    assert "bundle" in deps and "check-bundles" in deps, (
        f"{WITNESS_BUNDLE_CURRENCY}\n{detail}"
    )
    assert deps.index("bundle") < deps.index("check-bundles"), (
        f"{WITNESS_BUNDLE_CURRENCY}\n{detail}"
    )

    stale_source = sandbox / "src" / "melt" / "batch-resolve.py"
    stale_source.write_text(
        stale_source.read_text(encoding="utf-8") + "\n# cut tracer staleness probe\n",
        encoding="utf-8",
    )
    rebuild = _run([sys.executable, "scripts/build_pyz.py", "melt"], cwd=sandbox)
    assert rebuild.returncode == 0, f"{WITNESS_BUNDLE_CURRENCY}\n{_output(rebuild)}"

    recipe = _run([sys.executable, "scripts/check_bundles.py"], cwd=sandbox)
    detail = f"exit={recipe.returncode}\n{_output(recipe)}"
    assert recipe.returncode != 0 and "stale" in _output(recipe), (
        f"{WITNESS_BUNDLE_CURRENCY}\n{detail}"
    )
