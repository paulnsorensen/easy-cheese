"""Outer pipeline tracers (Cut RED evidence for pyz-pipeline-contracts).

Each test drives a declared outer seam — the build subprocess, the bundle
dispatcher, or a just recipe — and fails until the corresponding pipeline
contract is implemented. Sandboxed runs copy the working tree into tmp_path so
no tracer ever mutates the project.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

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


def _run(
    argv: list[str], cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=env)


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


WITNESS_BUNDLE_CURRENCY = (
    "The bundle currency hook must build from the staged index, not an "
    "unstaged source edit"
)


def test_bundle_currency_wired_into_check(tmp_path: Path) -> None:
    sandbox = tmp_path / "project"
    _copy_project_subset(
        sandbox,
        dirs=("scripts", "src", "shared", "skills", "vendor"),
        files=("requirements-vendor.txt", "justfile", ".pre-commit-config.yaml"),
    )
    git = [
        "git",
        "-c",
        "user.email=cut@tracer",
        "-c",
        "user.name=cut",
        "-c",
        "commit.gpgsign=false",
    ]
    assert _run([*git, "init", "-q"], cwd=sandbox).returncode == 0
    assert _run([*git, "add", "-A", "-f"], cwd=sandbox).returncode == 0
    assert _run([*git, "commit", "-q", "-m", "base"], cwd=sandbox).returncode == 0
    assert _run([*git, "rm", "--cached", "-q", "-r", "vendor"], cwd=sandbox).returncode == 0

    just = (sandbox / "justfile").read_text(encoding="utf-8")
    check = re.search(r"^check:(.*)$", just, re.M)
    ci = re.search(r"^ci:(.*)$", just, re.M)
    assert check is not None and ci is not None, WITNESS_BUNDLE_CURRENCY
    check_deps = check.group(1).split()
    ci_deps = ci.group(1).split()
    assert check_deps.index("bundle") < check_deps.index("check-bundles")
    assert ci_deps.index("bundle") < ci_deps.index("check-bundles-ci")
    assert "check_bundles.py --against index" in just
    assert "check_bundles.py --against head" in just

    config = yaml.safe_load(
        (sandbox / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hook = config["repos"][0]["hooks"][0]
    trigger = re.compile(hook["files"])
    for path in (
        ".github/workflows/build-pyz.yml",
        "src/melt/batch-resolve.py",
        "shared/scripts/paths.py",
        "skills/melt/phase-contract.yaml",
        "skills/melt/scripts/melt.pyz",
        "scripts/build_pyz.py",
        "scripts/check_bundles.py",
        "scripts/precommit_bundle_currency.py",
        "scripts/vendor_deps.py",
        "pyproject.toml",
        "requirements-vendor.txt",
    ):
        assert trigger.search(path), path

    source = sandbox / "src" / "melt" / "batch-resolve.py"
    bundle = sandbox / "skills" / "melt" / "scripts" / "melt.pyz"
    source.write_text(
        source.read_text(encoding="utf-8") + "\n# staged pair probe\n",
        encoding="utf-8",
    )
    rebuild = _run([sys.executable, "scripts/build_pyz.py", "melt"], cwd=sandbox)
    assert rebuild.returncode == 0, f"{WITNESS_BUNDLE_CURRENCY}\n{_output(rebuild)}"
    assert _run([*git, "add", str(source), str(bundle)], cwd=sandbox).returncode == 0

    source.write_text(
        source.read_text(encoding="utf-8") + "\n# unstaged source probe\n",
        encoding="utf-8",
    )
    vendor_module = sandbox / "vendor" / "attr" / "__init__.py"
    vendor_module.write_text(
        vendor_module.read_text(encoding="utf-8") + "\n# unstaged vendor probe\n",
        encoding="utf-8",
    )
    hook_run = _run(["bash", "-c", hook["entry"]], cwd=sandbox)
    assert hook_run.returncode == 0, (
        f"{WITNESS_BUNDLE_CURRENCY}\n{_output(hook_run)}"
    )

    offline_env = os.environ.copy()
    offline_env["PIP_INDEX_URL"] = "http://127.0.0.1:9/simple"
    offline_env["PIP_NO_INDEX"] = "1"
    offline_hook_run = _run(
        ["bash", "-c", hook["entry"]], cwd=sandbox, env=offline_env
    )
    assert offline_hook_run.returncode == 0, (
        f"{WITNESS_BUNDLE_CURRENCY}\n{_output(offline_hook_run)}"
    )

    source.write_text(
        source.read_text(encoding="utf-8") + "\n# stale staged source probe\n",
        encoding="utf-8",
    )
    assert _run([*git, "add", str(source)], cwd=sandbox).returncode == 0
    rebuild = _run([sys.executable, "scripts/build_pyz.py", "melt"], cwd=sandbox)
    assert rebuild.returncode == 0, f"{WITNESS_BUNDLE_CURRENCY}\n{_output(rebuild)}"

    recipe = _run(
        [sys.executable, "scripts/check_bundles.py", "--against", "index"],
        cwd=sandbox,
    )
    detail = f"exit={recipe.returncode}\n{_output(recipe)}"
    assert recipe.returncode != 0 and "stale" in _output(recipe), (
        f"{WITNESS_BUNDLE_CURRENCY}\n{detail}"
    )


def test_missing_bundle_from_index_fails_currency_check(tmp_path: Path) -> None:
    sandbox = tmp_path / "project"
    _copy_project_subset(
        sandbox,
        dirs=("scripts", "src", "shared", "skills", "vendor"),
        files=("requirements-vendor.txt",),
    )
    git = [
        "git",
        "-c",
        "user.email=cut@tracer",
        "-c",
        "user.name=cut",
        "-c",
        "commit.gpgsign=false",
    ]
    assert _run([*git, "init", "-q"], cwd=sandbox).returncode == 0
    assert _run([*git, "add", "-A", "-f"], cwd=sandbox).returncode == 0
    assert _run([*git, "commit", "-q", "-m", "base"], cwd=sandbox).returncode == 0

    bundle = sandbox / "skills" / "melt" / "scripts" / "melt.pyz"
    assert _run([*git, "rm", "--cached", "-q", str(bundle)], cwd=sandbox).returncode == 0
    recipe = _run(
        [sys.executable, "scripts/check_bundles.py", "--against", "index"],
        cwd=sandbox,
    )
    detail = f"exit={recipe.returncode}\n{_output(recipe)}"
    assert recipe.returncode != 0 and "stale" in _output(recipe), detail
