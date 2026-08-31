from __future__ import annotations

import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from scripts import check_bundles


def _non_shiv_zipapp() -> bytes:
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("__main__.py", b"print('not Shiv')\n")
    return data.getvalue()


def test_bundle_manifest_rejects_non_shiv_zipapp() -> None:
    with pytest.raises(ValueError, match=r"not a Shiv archive: missing _bootstrap/"):
        _ = check_bundles._manifest(_non_shiv_zipapp())  # pyright: ignore[reportPrivateUsage]


def test_bundle_checker_rejects_new_non_shiv_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = tmp_path / "skills" / "demo" / "scripts" / "demo.pyz"
    bundle.parent.mkdir(parents=True)
    _ = bundle.write_bytes(_non_shiv_zipapp())
    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    assert check_bundles.main() == 1
    output = capsys.readouterr().out
    assert ".pyz bundles are invalid or stale" in output
    assert "not a Shiv archive" in output


def test_parse_against_defaults_to_head() -> None:
    assert check_bundles._parse_against(()) == "head"  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("mode", ["head", "index"])
def test_parse_against_accepts_declared_modes(mode: str) -> None:
    assert check_bundles._parse_against(["--against", mode]) == mode  # pyright: ignore[reportPrivateUsage]


def test_parse_against_rejects_unknown_mode() -> None:
    with pytest.raises(SystemExit):
        _ = check_bundles._parse_against(["--against", "bogus"])  # pyright: ignore[reportPrivateUsage]


def _init_index_rebuild_fixture(root: Path) -> tuple[Path, Path]:
    """A tiny committed repo whose fake build_pyz.py stamps source.txt's
    content into demo.pyz, for exercising _staged_index_rebuild end to end.
    """
    (root / "scripts").mkdir()
    source = root / "source.txt"
    _ = source.write_text("committed\n")
    other = root / "other.txt"
    _ = other.write_text("other committed\n")
    bundle_dir = root / "skills" / "demo" / "scripts"
    bundle_dir.mkdir(parents=True)
    bundle = bundle_dir / "demo.pyz"
    _ = bundle.write_bytes(b"committed-bytes")
    build_script = root / "scripts" / "build_pyz.py"
    _ = build_script.write_text(
        "from pathlib import Path\n"
        "root = Path(__file__).resolve().parents[1]\n"
        "text = (root / 'source.txt').read_text()\n"
        "(root / 'skills' / 'demo' / 'scripts' / 'demo.pyz').write_bytes(text.encode())\n"
    )
    for command in (
        ["git", "init", "--quiet"],
        ["git", "config", "user.email", "t@t.example"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(command, cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=root, check=True)
    return source, bundle


def test_staged_index_rebuild_reflects_staged_content_and_restores_working_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, bundle = _init_index_rebuild_fixture(tmp_path)

    # source.txt is fully staged; a different tracked file, other.txt, has
    # an unstaged edit, to prove the rebuild uses the staged content and
    # the restore never touches an in-progress edit elsewhere in the tree.
    _ = source.write_text("staged\n")
    subprocess.run(["git", "add", "source.txt"], cwd=tmp_path, check=True)
    other = tmp_path / "other.txt"
    _ = other.write_text("work in progress\n")

    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)
    with check_bundles._staged_index_rebuild([bundle]):  # pyright: ignore[reportPrivateUsage]
        assert bundle.read_bytes() == b"staged\n"

    assert bundle.read_bytes() == b"committed-bytes"
    assert other.read_text() == "work in progress\n"


def test_check_bundles_against_index_flags_staged_source_without_restaged_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source, bundle = _init_index_rebuild_fixture(tmp_path)

    _ = source.write_text("staged-source-change\n")
    subprocess.run(["git", "add", "source.txt"], cwd=tmp_path, check=True)
    # demo.pyz is left stale: never restaged after the source change.

    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    assert check_bundles.main(["--against", "index"]) == 1
    output = capsys.readouterr().out
    assert ".pyz bundles are invalid or stale" in output
    assert "demo.pyz" in output
    assert bundle.read_bytes() == b"committed-bytes"
