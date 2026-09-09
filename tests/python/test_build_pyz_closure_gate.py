"""Build-time command-surface and closure gates: AC-7's 'built' clause."""

from __future__ import annotations

import sys
import zipfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from easy_cheese.shared.bundle_commands import bundle_command, derive_command

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402
import check_bundles  # noqa: E402

_Handler = Callable[[list[str]], int]


def _install_fixture_manifest(
    monkeypatch: pytest.MonkeyPatch,
    *,
    declared: tuple[str, ...],
    referenced: tuple[str, ...],
) -> None:
    """Register `fixture-skill` with the given decorator and manifest surfaces."""
    module = ModuleType("easy_cheese.skills.fixture_skill.commands")
    handlers: dict[str, _Handler] = {}
    for name in declared:

        def handler(_argv: list[str]) -> int:
            return 0

        handler.__module__ = module.__name__
        handler.__qualname__ = name.replace("-", "_")
        handlers[name] = bundle_command(name)(handler)
        setattr(module, handler.__qualname__, handlers[name])
    setattr(
        module,
        "COMMANDS",
        tuple(derive_command(handlers[name], f"Run {name}") for name in referenced),
    )
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(build_pyz, "SKILLS", (*build_pyz.SKILLS, "fixture-skill"))


@pytest.mark.parametrize(
    ("declared", "referenced", "message"),
    [
        (
            ("go", "orphan"),
            ("go",),
            "easy_cheese.skills.fixture_skill.commands declares unreferenced"
            + " bundle command(s): orphan",
        ),
        (("go",), ("go", "go"), "duplicate bundle command: go"),
    ],
    ids=["unreferenced-declaration", "duplicate-manifest-entry"],
)
def test_build_rejects_a_broken_command_surface_before_building_anything(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    declared: tuple[str, ...],
    referenced: tuple[str, ...],
    message: str,
) -> None:
    _install_fixture_manifest(monkeypatch, declared=declared, referenced=referenced)

    status = build_pyz.main(
        ["build_pyz.py", "--out-dir", str(tmp_path), "fixture-skill"]
    )

    assert status == 1
    assert (
        f"ERROR: bundle build failed for fixture-skill: {message}"
        in capsys.readouterr().err
    )
    assert not (tmp_path / "fixture-skill.pyz").exists()


def test_every_packaged_skill_surface_passes_the_build_gate() -> None:
    """The shipped manifests, including press, all sit on the decorator surface."""
    assert "press" in build_pyz.SKILLS
    build_pyz.validate_command_surfaces(build_pyz.SKILLS)


def _stub_wheelhouse(monkeypatch: pytest.MonkeyPatch, archive_bytes: bytes) -> None:
    """Skip wheel building and have the Shiv step emit `archive_bytes` verbatim."""

    def _no_wheelhouse(_wheelhouse: Path, _skills: object = None) -> None:
        return None

    def _write_archive(_skill: str, target: Path, _wheelhouse: Path) -> Path:
        _ = target.write_bytes(archive_bytes)
        return target

    monkeypatch.setattr(build_pyz, "build_wheelhouse", _no_wheelhouse)
    monkeypatch.setattr(build_pyz, "_build_from_wheelhouse", _write_archive)


def _non_shiv_zipapp(tmp_path: Path) -> bytes:
    scratch = tmp_path / "scratch.zip"
    with zipfile.ZipFile(scratch, "w") as archive:
        archive.writestr("__main__.py", "print('not Shiv')\n")
    return scratch.read_bytes()


def test_build_rejects_an_archive_the_closure_gate_rejects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real verifier runs on the staged archive; a rejected one never lands."""
    _stub_wheelhouse(monkeypatch, _non_shiv_zipapp(tmp_path))

    status = build_pyz.main(["build_pyz.py", "--out-dir", str(tmp_path), "press"])

    assert status == 1
    assert (
        "ERROR: bundle build failed for press: not a Shiv archive: missing _bootstrap/"
        in capsys.readouterr().err
    )
    assert not (tmp_path / "press.pyz").exists()


def test_build_reports_every_closure_problem_and_keeps_the_target_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_wheelhouse(monkeypatch, _non_shiv_zipapp(tmp_path))
    problems = [
        "unresolved deferred import: easy_cheese.skills.other.commands",
        "native member: site-packages/fast.so",
    ]

    def _reject(_pyz: Path) -> list[str]:
        return list(problems)

    monkeypatch.setattr(check_bundles, "verify_archive", _reject)

    status = build_pyz.main(["build_pyz.py", "--out-dir", str(tmp_path), "press"])

    assert status == 1
    expected = "ERROR: bundle build failed for press: press archive failed the closure gate:\n"
    expected += f"  ! {problems[0]}\n  ! {problems[1]}"
    assert expected in capsys.readouterr().err
    assert not (tmp_path / "press.pyz").exists()


def test_verify_archive_passes_a_committed_bundle() -> None:
    committed = REPO_ROOT / "skills" / "press" / "scripts" / "press.pyz"

    assert check_bundles.verify_archive(committed) == []
