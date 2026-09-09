"""Build-time command-surface and closure gates: AC-7's 'built' clause."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from easy_cheese.shared import bundle_commands
from easy_cheese.shared.bundle_commands import (
    Command,
    CommandHandler,
    bundle_command,
    derive_command,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402
import check_bundles  # noqa: E402

COMMITTED_PRESS = REPO_ROOT / "skills" / "press" / "scripts" / "press.pyz"
BROKEN_MODULE = "site-packages/easy_cheese/skills/press/broken.py"
UNRESOLVED_IMPORT = "easy_cheese.skills.nowhere"


def _install_fixture_manifest(
    monkeypatch: pytest.MonkeyPatch,
    *,
    declared: tuple[str, ...],
    referenced: tuple[str, ...],
) -> None:
    """Register `fixture-skill` with the given decorator and manifest surfaces."""
    module = ModuleType("easy_cheese.skills.fixture_skill.commands")
    handlers: dict[str, CommandHandler] = {}
    for name in declared:

        def handler(_argv: list[str]) -> int:
            return 0

        handler.__module__ = module.__name__
        handlers[name] = bundle_command(name)(handler)
        setattr(module, name.replace("-", "_"), handlers[name])
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
        f"ERROR: bundle build failed: fixture-skill: {message}"
        in capsys.readouterr().err
    )
    assert not (tmp_path / "fixture-skill.pyz").exists()


def test_build_rejects_a_manifest_that_cannot_be_imported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An import failure inside a skill's `commands.py` is a build error, not a traceback."""
    monkeypatch.setitem(sys.modules, "easy_cheese.skills.fixture_skill.commands", None)
    monkeypatch.setattr(build_pyz, "SKILLS", (*build_pyz.SKILLS, "fixture-skill"))

    status = build_pyz.main(
        ["build_pyz.py", "--out-dir", str(tmp_path), "fixture-skill"]
    )

    assert status == 1
    err = capsys.readouterr().err
    assert "ERROR: bundle build failed: fixture-skill: " in err
    assert "easy_cheese.skills.fixture_skill.commands" in err
    assert "Traceback" not in err


def test_build_gate_validates_every_packaged_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str] = []
    real = bundle_commands.validate_command_surface

    def spy(module: ModuleType, commands: Sequence[Command]) -> None:
        visited.append(module.__name__)
        real(module, commands)

    monkeypatch.setattr(bundle_commands, "validate_command_surface", spy)

    build_pyz.validate_command_surfaces(build_pyz.SKILLS)

    assert visited == [
        f"easy_cheese.skills.{skill.replace('-', '_')}.commands"
        for skill in build_pyz.SKILLS
    ]
    assert "easy_cheese.skills.press.commands" in visited


def test_build_gate_refuses_an_easy_cheese_outside_src(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setattr(build_pyz, "SRC_ROOT", elsewhere)

    with pytest.raises(
        RuntimeError, match=rf"easy_cheese resolved from .* not {elsewhere}"
    ):
        build_pyz.validate_command_surfaces(("press",))


def _stub_wheelhouse(monkeypatch: pytest.MonkeyPatch, archive_bytes: bytes) -> None:
    """Skip wheel building and have the Shiv step emit `archive_bytes` verbatim."""

    def _no_wheelhouse(_wheelhouse: Path, _skills: Iterable[str] | None = None) -> None:
        return None

    def _write_archive(_skill: str, target: Path, _wheelhouse: Path) -> Path:
        _ = target.write_bytes(archive_bytes)
        return target

    monkeypatch.setattr(build_pyz, "build_wheelhouse", _no_wheelhouse)
    monkeypatch.setattr(build_pyz, "_build_from_wheelhouse", _write_archive)


def _non_shiv_zipapp() -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("__main__.py", "print('not Shiv')\n")
    return data.getvalue()


def _press_archive_with_unresolved_import(tmp_path: Path) -> Path:
    """The committed press archive plus one module whose import cannot resolve.

    Shiv's `build_id` is recomputed the way `check_bundles` does, so the
    archive is layout-valid and only the closure gate can reject it.
    """
    broken = tmp_path / "press.pyz"
    source_text = f"import {UNRESOLVED_IMPORT}\n"
    with (
        zipfile.ZipFile(COMMITTED_PRESS) as source,
        zipfile.ZipFile(broken, "w") as target,
    ):
        environment = cast(
            dict[str, object], json.loads(source.read("environment.json"))
        )
        for info in source.infolist():
            if info.filename != "environment.json":
                target.writestr(info, source.read(info))
        target.writestr(BROKEN_MODULE, source_text)
    with zipfile.ZipFile(broken) as target:
        raw_build_id, _ = check_bundles._site_packages_hashes(  # pyright: ignore[reportPrivateUsage]
            target.infolist(), target.read
        )
    environment["build_id"] = raw_build_id
    hashes = cast(dict[str, str], environment.get("hashes") or {})
    if hashes:
        relative = BROKEN_MODULE.removeprefix("site-packages/")
        hashes[relative] = hashlib.sha256(source_text.encode()).hexdigest()
    with zipfile.ZipFile(broken, "a") as target:
        target.writestr("environment.json", json.dumps(environment))
    return broken


def test_verify_archive_rejects_an_unresolved_import_in_a_valid_shiv_archive(
    tmp_path: Path,
) -> None:
    broken = _press_archive_with_unresolved_import(tmp_path)

    assert check_bundles.verify_archive(broken) == [
        f"unresolved import {UNRESOLVED_IMPORT!r} in {BROKEN_MODULE}"
    ]


def test_build_rejects_an_archive_with_an_unresolved_import_unstubbed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real closure gate runs on the staged archive and the target never lands."""
    broken = _press_archive_with_unresolved_import(tmp_path)
    _stub_wheelhouse(monkeypatch, broken.read_bytes())
    out_dir = tmp_path / "out"

    status = build_pyz.main(["build_pyz.py", "--out-dir", str(out_dir), "press"])

    assert status == 1
    expected = "ERROR: bundle build failed: press archive failed the closure gate:\n"
    expected += f"  ! unresolved import {UNRESOLVED_IMPORT!r} in {BROKEN_MODULE}"
    assert expected in capsys.readouterr().err
    assert not (out_dir / "press.pyz").exists()


def test_build_rejects_a_malformed_archive_as_a_problem_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_wheelhouse(monkeypatch, _non_shiv_zipapp())

    status = build_pyz.main(["build_pyz.py", "--out-dir", str(tmp_path), "press"])

    assert status == 1
    err = capsys.readouterr().err
    expected = "ERROR: bundle build failed: press archive failed the closure gate:\n"
    expected += "  ! bundle metadata invalid: not a Shiv archive: missing _bootstrap/"
    assert expected in err
    assert "Traceback" not in err
    assert not (tmp_path / "press.pyz").exists()


def test_build_reports_every_closure_problem_and_keeps_the_target_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_wheelhouse(monkeypatch, b"")
    problems = [
        "unresolved deferred import: easy_cheese.skills.other.commands",
        "native member: site-packages/fast.so",
    ]

    def _reject(_pyz: Path) -> list[str]:
        return list(problems)

    monkeypatch.setattr(check_bundles, "verify_archive", _reject)

    status = build_pyz.main(["build_pyz.py", "--out-dir", str(tmp_path), "press"])

    assert status == 1
    expected = "ERROR: bundle build failed: press archive failed the closure gate:\n"
    expected += f"  ! {problems[0]}\n  ! {problems[1]}"
    assert expected in capsys.readouterr().err
    assert not (tmp_path / "press.pyz").exists()


def test_verify_archive_passes_the_committed_press_bundle(tmp_path: Path) -> None:
    staged = Path(shutil.copy2(COMMITTED_PRESS, tmp_path / "press.pyz"))

    assert check_bundles.verify_archive(staged) == []
