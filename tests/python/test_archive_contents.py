"""Direct archive membership and cold execution contracts."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from easy_cheese.shared.bundle_command_index import COMMAND_BUNDLES
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import runtime_gates  # noqa: E402
import stage_release  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SKILLS = runtime_gates.SKILLS
COMMAND_HELP_CASES = tuple(
    (skill, command)
    for command, skills in COMMAND_BUNDLES.items()
    for skill in skills
)


_AUDITED_RUNNER = textwrap.dedent(
    """
    import runpy
    import sys

    def reject_network(event, args):
        if event in {"socket.__new__", "socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError(event)

    sys.addaudithook(reject_network)
    sys.argv = sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name="__main__")
    """
)


def test_skill_archive_uses_committed_path(
    skill_archive: Callable[[str], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EASY_CHEESE_PREBUILT_PYZ", str(tmp_path))
    assert skill_archive("mold") == ROOT / "skills" / "mold" / "scripts" / "mold.pyz"


@pytest.fixture(scope="module")
def staged(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return stage_release.stage(tmp_path_factory.mktemp("release") / "tree")


def archive(staged_root: Path, skill: str) -> Path:
    return staged_root / "skills" / skill / "scripts" / f"{skill}.pyz"


def isolated_archive_run(
    staged_root: Path, skill: str, args: tuple[str, ...], tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    cold = tmp_path / "cold"
    cold.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "SHIV_ROOT": str(tmp_path / "shiv"),
            "PYTHONPATH": "",
            "PATH": "/usr/bin:/bin",
        }
    )
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            _AUDITED_RUNNER,
            str(archive(staged_root, skill)),
            *args,
        ],
        cwd=cold,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


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
    result = isolated_archive_run(staged, skill, ("--help",), tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("skill", "command"),
    COMMAND_HELP_CASES,
)
def test_archive_command_executes_help_in_isolation(
    skill: str, command: str, staged: Path, tmp_path: Path
) -> None:
    result = isolated_archive_run(staged, skill, (command, "--help"), tmp_path)
    if (skill, command) == ("mold", "review"):
        assert result.returncode == 2
        assert result.stderr == "usage: review {serve|publish|poll|close} [args...]\n"
    else:
        assert result.returncode == 0, f"{skill} {command}: {result.stderr}"


def test_archive_fails_without_bundled_dependency(staged: Path, tmp_path: Path) -> None:
    isolated = tmp_path / "missing-dependency"
    broken = archive(isolated, "plate")
    broken.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive(staged, "plate")) as source, zipfile.ZipFile(
        broken, "w"
    ) as target:
        for member in source.infolist():
            if not member.filename.startswith("site-packages/fromargs/"):
                target.writestr(member, source.read(member))

    result = isolated_archive_run(
        isolated, "plate", ("validate-publication", "--help"), tmp_path
    )
    assert result.returncode != 0
    assert "No module named 'fromargs'" in result.stderr


def test_audited_runner_rejects_udp_socket_creation(tmp_path: Path) -> None:
    isolated = tmp_path / "network-control"
    target = archive(isolated, "plate")
    target.parent.mkdir(parents=True)
    with zipfile.ZipFile(target, "w") as bundle:
        bundle.writestr(
            "__main__.py",
            "import socket\n\nsocket.socket(socket.AF_INET, socket.SOCK_DGRAM).close()\n",
        )

    result = isolated_archive_run(isolated, "plate", (), tmp_path)

    assert result.returncode != 0
    assert result.stderr.splitlines()[-1] == "RuntimeError: socket.__new__"


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