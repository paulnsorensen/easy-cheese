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
        _ = check_bundles.bundle_manifest(_non_shiv_zipapp())


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


def test_parse_against_accepts_standard_option_form() -> None:
    assert check_bundles._parse_against(["--against=index"]) == "index"  # pyright: ignore[reportPrivateUsage]


def test_parse_against_help_exits_successfully(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        _ = check_bundles._parse_against(["--help"])  # pyright: ignore[reportPrivateUsage]
    assert raised.value.code == 0
    assert "--against" in capsys.readouterr().out


def test_site_packages_hashes_read_each_member_once() -> None:
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("site-packages/bin/demo", b"#!/usr/bin/python\n")
        archive.writestr("site-packages/easy_cheese/demo.py", b"VALUE = 1\n")
    _ = data.seek(0)
    with zipfile.ZipFile(data) as archive:
        infos = tuple(archive.infolist())
        reads: list[str] = []

        def read(info: zipfile.ZipInfo) -> bytes:
            reads.append(info.filename)
            return archive.read(info)

        _ = check_bundles._site_packages_hashes(infos, read)  # pyright: ignore[reportPrivateUsage]

    assert reads == ["site-packages/bin/demo", "site-packages/easy_cheese/demo.py"]


def test_baseline_blobs_use_one_git_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = [
        Path("skills/demo/scripts/demo.pyz"),
        Path("skills/other/scripts/other.pyz"),
    ]
    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)
    calls: list[tuple[list[str], bytes]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        input: bytes,
        capture_output: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        assert cwd == tmp_path
        assert capture_output
        calls.append((command, input))
        body = b"demo"
        output = b"0" * 40 + b" blob 4\n" + body + b"\n"
        body = b"other"
        output += b"1" * 40 + b" blob 5\n" + body + b"\n"
        return subprocess.CompletedProcess(command, 0, stdout=output)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert check_bundles._baseline_blobs("head", paths) == {  # pyright: ignore[reportPrivateUsage]
        paths[0]: b"demo",
        paths[1]: b"other",
    }
    assert calls == [
        (
            ["git", "cat-file", "--batch"],
            b"HEAD:skills/demo/scripts/demo.pyz\nHEAD:skills/other/scripts/other.pyz\n",
        )
    ]


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
        + "root = Path(__file__).resolve().parents[1]\n"
        + "text = (root / 'source.txt').read_text()\n"
        + "(root / 'skills' / 'demo' / 'scripts' / 'demo.pyz').write_bytes(text.encode())\n"
    )
    for command in (
        ["git", "init", "--quiet"],
        ["git", "config", "user.email", "t@t.example"],
        ["git", "config", "user.name", "t"],
    ):
        _ = subprocess.run(command, cwd=root, check=True)
    _ = subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    _ = subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=root, check=True)
    return source, bundle


def test_staged_index_rebuild_yields_isolated_worktree_and_leaves_the_real_tree_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, bundle = _init_index_rebuild_fixture(tmp_path)

    # source.txt is fully staged; a different tracked file, other.txt, has
    # an unstaged edit, to prove the rebuild uses the staged content while
    # never touching the real working tree at all.
    _ = source.write_text("staged\n")
    _ = subprocess.run(["git", "add", "source.txt"], cwd=tmp_path, check=True)
    other = tmp_path / "other.txt"
    _ = other.write_text("work in progress\n")

    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)
    with check_bundles._staged_index_rebuild() as worktree:  # pyright: ignore[reportPrivateUsage]
        rebuilt_bundle = worktree / "skills" / "demo" / "scripts" / "demo.pyz"
        assert rebuilt_bundle.read_bytes() == b"staged\n"
        assert bundle.read_bytes() == b"committed-bytes"
        assert other.read_text() == "work in progress\n"

    assert not worktree.exists()
    assert bundle.read_bytes() == b"committed-bytes"
    assert other.read_text() == "work in progress\n"


def test_check_bundles_against_index_survives_a_bundle_already_rebuilt_unstaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bundle already rebuilt-but-unstaged before the run (exactly what a
    dev's own `build_pyz.py` invocation leaves behind) must not strand the
    real tree: the check flags staleness without stashing, and the unstaged
    bundle edit survives untouched afterward.
    """
    source, bundle = _init_index_rebuild_fixture(tmp_path)

    _ = source.write_text("staged-source-change\n")
    _ = subprocess.run(["git", "add", "source.txt"], cwd=tmp_path, check=True)
    _ = bundle.write_bytes(b"unstaged-local-rebuild")

    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    assert check_bundles.main(["--against", "index"]) == 1
    output = capsys.readouterr().out
    assert ".pyz bundles are invalid or stale" in output

    assert bundle.read_bytes() == b"unstaged-local-rebuild"
    stash_list = subprocess.run(
        ["git", "stash", "list"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert stash_list.stdout == ""


def test_check_bundles_against_index_flags_staged_source_without_restaged_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source, bundle = _init_index_rebuild_fixture(tmp_path)

    _ = source.write_text("staged-source-change\n")
    _ = subprocess.run(["git", "add", "source.txt"], cwd=tmp_path, check=True)
    # demo.pyz is left stale: never restaged after the source change.

    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    assert check_bundles.main(["--against", "index"]) == 1
    output = capsys.readouterr().out
    assert ".pyz bundles are invalid or stale" in output
    assert "demo.pyz" in output
    assert bundle.read_bytes() == b"committed-bytes"


def test_check_pyz_references_flags_a_website_doc_naming_a_foreign_skill_pyz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs_dir = tmp_path / "website" / "content" / "docs" / "skills"
    docs_dir.mkdir(parents=True)
    doc = docs_dir / "mold.md"
    _ = doc.write_text("Mold hands its plan to Cook by running cook.pyz.\n")
    monkeypatch.setattr(check_bundles, "REPO_ROOT", tmp_path)

    violations = check_bundles.check_pyz_references()

    assert violations == [
        "website/content/docs/skills/mold.md: references cook.pyz, not its own mold.pyz"
    ]
