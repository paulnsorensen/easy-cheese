"""`discovery_notes.find_cheese_dirs`: every `.cheese` dir with markdown
beneath it, agreeing across the rg and walk backends.

Every test points `EASY_CHEESE_SEARCH_ROOTS` at tmp_path so the real `~` is
never touched.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from easy_cheese.shared.wheypoint import discovery_notes

HAS_RG = shutil.which("rg") is not None


def _write(path: Path, text: str = "content\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def isolated_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("EASY_CHEESE_SEARCH_ROOTS", str(tmp_path / "unused-default-root"))
    return tmp_path


def test_finds_cheese_dir_holding_markdown(isolated_roots: Path) -> None:
    repo = isolated_roots / "repo"
    _ = _write(repo / ".cheese" / "notes" / "a.md")

    scan = discovery_notes.find_cheese_dirs([repo])

    assert scan.dirs == ((repo / ".cheese").resolve(),)


def test_ignores_cheese_dir_with_no_markdown(isolated_roots: Path) -> None:
    repo = isolated_roots / "repo"
    _ = _write(repo / ".cheese" / "notes" / "a.txt")

    scan = discovery_notes.find_cheese_dirs([repo])

    assert scan.dirs == ()


def test_skips_cheese_dir_nested_inside_another(isolated_roots: Path) -> None:
    repo = isolated_roots / "repo"
    _ = _write(repo / ".cheese" / "vendor" / ".cheese" / "nested.md")

    scan = discovery_notes.find_cheese_dirs([repo])

    assert scan.dirs == ((repo / ".cheese").resolve(),)


def test_dedupes_and_sorts_across_roots(isolated_roots: Path) -> None:
    repo_a = isolated_roots / "a-repo"
    repo_b = isolated_roots / "b-repo"
    _ = _write(repo_a / ".cheese" / "notes" / "x.md")
    _ = _write(repo_b / ".cheese" / "notes" / "y.md")

    scan = discovery_notes.find_cheese_dirs([repo_a, repo_b, repo_a])

    assert scan.dirs == (
        (repo_a / ".cheese").resolve(),
        (repo_b / ".cheese").resolve(),
    )


def test_prunes_build_directories(isolated_roots: Path) -> None:
    repo = isolated_roots / "repo"
    _ = _write(repo / ".cheese" / "notes" / "a.md")
    for pruned in ("node_modules/pkg", ".venv/lib", "target/x"):
        _ = _write(repo / pruned / ".cheese" / "notes" / "pruned.md")

    scan = discovery_notes.find_cheese_dirs([repo])

    assert scan.dirs == ((repo / ".cheese").resolve(),)


def test_uses_search_roots_env_by_default(
    isolated_roots: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = isolated_roots / "repo"
    _ = _write(repo / ".cheese" / "notes" / "a.md")
    monkeypatch.setenv("EASY_CHEESE_SEARCH_ROOTS", str(isolated_roots))

    scan = discovery_notes.find_cheese_dirs()

    assert scan.dirs == ((repo / ".cheese").resolve(),)


def test_walk_and_rg_backends_agree(
    isolated_roots: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo1 = isolated_roots / "repo1"
    repo2 = isolated_roots / "repo2"
    _ = _write(repo1 / ".cheese" / "notes" / "alpha.md")
    _ = _write(repo2 / ".cheese" / "artifacts" / "beta.md")
    _ = _write(repo1 / ".cheese" / "vendor" / ".cheese" / "nested.md")
    original_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", "")
    walk_scan = discovery_notes.find_cheese_dirs([repo1, repo2])

    assert walk_scan.backend == "walk"
    expected = {(repo1 / ".cheese").resolve(), (repo2 / ".cheese").resolve()}
    assert set(walk_scan.dirs) == expected

    if not HAS_RG:
        pytest.skip("rg is not installed; the walk fallback is already verified")
    rg_entries = [
        entry for entry in original_path.split(os.pathsep) if Path(entry).name != "shims"
    ]
    if not any((Path(entry) / "rg").is_file() for entry in rg_entries):
        pytest.skip("rg is only available through a shim")
    monkeypatch.setenv("PATH", os.pathsep.join(rg_entries))
    rg_scan = discovery_notes.find_cheese_dirs([repo1, repo2])

    assert rg_scan.backend == "rg"
    assert set(rg_scan.dirs) == expected
