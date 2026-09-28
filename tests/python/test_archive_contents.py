"""Direct archive membership and cold execution contracts."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import runtime_gates  # noqa: E402
import stage_release  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SKILLS = runtime_gates.SKILLS


@pytest.fixture(scope="module")
def staged(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return stage_release.stage(tmp_path_factory.mktemp("release") / "tree")


def archive(staged_root: Path, skill: str) -> Path:
    return staged_root / "skills" / skill / "scripts" / f"{skill}.pyz"


@pytest.mark.parametrize("skill", SKILLS)
def test_archive_contains_own_namespace_and_support(skill: str, staged: Path) -> None:
    path = archive(staged, skill)
    assert path.is_file(), path
    with zipfile.ZipFile(path) as bundle:
        names = set(bundle.namelist())
    prefix = "site-packages/easy_cheese/skills/"
    roots = {
        remaining.split("/", 1)[0]
        for name in names
        if name.startswith(prefix)
        and "/" in (remaining := name[len(prefix):])
    }
    package = skill.replace("-", "_")
    assert roots == {package}
    site_packages = "site-packages/"
    assert f"{site_packages}easy_cheese/__init__.py" in names
    assert f"{site_packages}easy_cheese/skills/__init__.py" in names
    assert f"{site_packages}easy_cheese/skills/{package}/__init__.py" in names
    assert f"{site_packages}easy_cheese/shared/__init__.py" in names
    assert f"{site_packages}easy_cheese/cli/__init__.py" in names
    assert f"{site_packages}easy_cheese_schemas/__init__.py" in names


@pytest.mark.parametrize("skill", SKILLS)
def test_archive_executes_help_without_repository_source(
    skill: str, staged: Path, tmp_path: Path
) -> None:
    cold = tmp_path / "cold"
    cold.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "SHIV_ROOT": str(tmp_path / "shiv"),
            "PYTHONPATH": "",
        }
    )
    env["PATH"] = "/usr/bin:/bin"
    audit = textwrap.dedent(
        """
        import runpy
        import sys

        def reject_network(event, args):
            if event in {"socket.connect", "socket.getaddrinfo"}:
                raise RuntimeError(event)

        sys.addaudithook(reject_network)
        sys.argv = [sys.argv[1], "--help"]
        runpy.run_path(sys.argv[0], run_name="__main__")
        """
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", audit, str(archive(staged, skill))],
        cwd=cold,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_archive_shebang_executes_directly(staged: Path, tmp_path: Path) -> None:
    cold = tmp_path / "cold"
    cold.mkdir()
    result = subprocess.run(
        [str(archive(staged, SKILLS[0])), "--help"],
        cwd=cold,
        env={
            "HOME": str(tmp_path / "home"),
            "SHIV_ROOT": str(tmp_path / "shiv"),
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": "",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_mold_assets_are_immutable(staged: Path) -> None:
    source_root = ROOT / "src" / "easy_cheese" / "skills" / "mold" / "assets"
    assets = sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file() and path.stat().st_size
    )
    assert assets

    with zipfile.ZipFile(archive(staged, "mold")) as bundle:
        for asset in assets:
            relative = asset.relative_to(source_root).as_posix()
            member = f"site-packages/easy_cheese/skills/mold/assets/{relative}"
            assert member in bundle.namelist()
            assert bundle.read(member) == asset.read_bytes()