"""The sdist guard blocks an upload that carries files outside the package."""

from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sdist_contents_check  # noqa: E402

ALLOWED = "src/pkg/ README.md"


def _sdist(root: Path, members: list[str]) -> None:
    dist = root / "dist"
    dist.mkdir()
    with tarfile.open(dist / "pkg-1.0.tar.gz", "w:gz") as tar:
        for member in ["pkg-1.0/PKG-INFO", *(f"pkg-1.0/{m}" for m in members)]:
            info = tarfile.TarInfo(member)
            tar.addfile(info, io.BytesIO(b""))


def _check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, members: list[str]) -> int:
    _sdist(tmp_path, members)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALLOWED", ALLOWED)
    return sdist_contents_check.main()


def test_package_only_sdist_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    members = ["src/pkg/__init__.py", "README.md", "LICENSE", "pyproject.toml"]
    assert _check(tmp_path, monkeypatch, members) == 0
    assert "sdist is package-only (5 members)." in capsys.readouterr().out


def test_stray_file_fails_and_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    members = ["src/pkg/__init__.py", "tests/test_pkg.py", "src/other/x.py"]
    assert _check(tmp_path, monkeypatch, members) == 1
    out = capsys.readouterr().out
    assert "::error::" in out
    assert "['src/other/x.py', 'tests/test_pkg.py']" in out


def test_exact_entry_does_not_allow_a_longer_path() -> None:
    assert sdist_contents_check.stray_members(["README.md.bak"], ["README.md"]) == ["README.md.bak"]


def test_prefix_entry_does_not_allow_a_sibling_with_the_same_stem() -> None:
    assert sdist_contents_check.stray_members(["src/pkg_extra/x.py"], ["src/pkg/"]) == ["src/pkg_extra/x.py"]
