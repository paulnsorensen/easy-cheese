"""Tests for lockfile-resolve.resolve_lockfile.

git/subprocess interactions are mocked. We exercise: success, dry-run,
unknown lockfile type, missing manifest, manifest with conflict markers,
git-show failure, regen failure, go.mod also-staged path, staging failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


def make_completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["x"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def write_clean_manifest(tmp_path: Path, name: str = "Cargo.toml") -> Path:
    manifest = tmp_path / name
    manifest.write_text("[package]\nname = 'a'\n")
    return manifest


class TestResolveLockfile:
    def test_unknown_lockfile_type(self, lockfile_resolve: ModuleType) -> None:
        result = lockfile_resolve.resolve_lockfile("requirements.txt")
        assert result["resolved"] is False
        assert "Unknown lockfile type" in result["message"]

    def test_missing_manifest(self, lockfile_resolve: ModuleType, tmp_path: Path) -> None:
        result = lockfile_resolve.resolve_lockfile(str(tmp_path / "Cargo.lock"))
        assert result["resolved"] is False
        assert "Manifest not found" in result["message"]

    def test_manifest_with_conflict_markers_is_rejected(
        self, lockfile_resolve: ModuleType, tmp_path: Path
    ) -> None:
        manifest = tmp_path / "Cargo.toml"
        manifest.write_text("<<<<<<< HEAD\nname='a'\n=======\nname='b'\n>>>>>>> x\n")
        result = lockfile_resolve.resolve_lockfile(str(tmp_path / "Cargo.lock"))
        assert result["resolved"] is False
        assert "conflict markers" in result["message"]

    def test_dry_run_does_not_invoke_subprocess(
        self, lockfile_resolve: ModuleType, tmp_path: Path
    ) -> None:
        write_clean_manifest(tmp_path)
        with (
            patch.object(lockfile_resolve.subprocess, "run") as run_mock,
            patch.object(lockfile_resolve, "run_git") as git_mock,
        ):
            result = lockfile_resolve.resolve_lockfile(str(tmp_path / "Cargo.lock"), dry_run=True)
        assert result["resolved"] is True
        assert "would take" in result["message"]
        run_mock.assert_not_called()
        git_mock.assert_not_called()

    def test_apply_takes_theirs_regenerates_and_stages(
        self, lockfile_resolve: ModuleType, tmp_path: Path
    ) -> None:
        write_clean_manifest(tmp_path)
        lockfile = tmp_path / "Cargo.lock"
        lockfile.write_text("<<<<<<< HEAD\nold\n=======\nnew\n>>>>>>> x\n")

        with (
            patch.object(lockfile_resolve, "run_git") as git_mock,
            patch.object(
                lockfile_resolve.subprocess, "run", return_value=make_completed()
            ) as run_mock,
        ):
            git_mock.side_effect = [
                make_completed(stdout="theirs-content\n"),  # git show :3:
                make_completed(),  # git add
            ]
            result = lockfile_resolve.resolve_lockfile(str(lockfile), strategy="theirs")

        assert result["resolved"] is True
        assert "theirs" in result["message"]
        assert lockfile.read_text() == "theirs-content\n"
        # Regen command was the cargo regen command; staged via run_git add
        assert run_mock.call_args.args[0] == ["cargo", "generate-lockfile"]
        assert git_mock.call_args_list[-1].args[0] == ["add", str(lockfile)]

    def test_git_show_failure(self, lockfile_resolve: ModuleType, tmp_path: Path) -> None:
        write_clean_manifest(tmp_path)
        lockfile = tmp_path / "Cargo.lock"
        lockfile.write_text("doesnt matter")

        with patch.object(lockfile_resolve, "run_git", return_value=make_completed(returncode=1)):
            result = lockfile_resolve.resolve_lockfile(str(lockfile), strategy="ours")

        assert result["resolved"] is False
        assert "could not extract" in result["message"]

    def test_regen_failure(self, lockfile_resolve: ModuleType, tmp_path: Path) -> None:
        write_clean_manifest(tmp_path)
        lockfile = tmp_path / "Cargo.lock"
        lockfile.write_text("ignored")

        with (
            patch.object(lockfile_resolve, "run_git", return_value=make_completed(stdout="ok")),
            patch.object(
                lockfile_resolve.subprocess,
                "run",
                return_value=make_completed(returncode=1, stderr="boom"),
            ),
        ):
            result = lockfile_resolve.resolve_lockfile(str(lockfile), strategy="theirs")

        assert result["resolved"] is False
        assert "regen failed" in result["message"]

    def test_strategy_regen_skips_git_show(
        self, lockfile_resolve: ModuleType, tmp_path: Path
    ) -> None:
        write_clean_manifest(tmp_path)
        lockfile = tmp_path / "Cargo.lock"
        lockfile.write_text("untouched")

        with (
            patch.object(lockfile_resolve, "run_git") as git_mock,
            patch.object(lockfile_resolve.subprocess, "run", return_value=make_completed()),
        ):
            git_mock.return_value = make_completed()
            result = lockfile_resolve.resolve_lockfile(str(lockfile), strategy="regen")

        assert result["resolved"] is True
        # Only the staging call should have happened — no git show.
        for call in git_mock.call_args_list:
            assert call.args[0][0] == "add"

    def test_go_also_stages_go_mod(self, lockfile_resolve: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module x\n")
        lockfile = tmp_path / "go.sum"
        lockfile.write_text("ignored")

        with (
            patch.object(lockfile_resolve, "run_git") as git_mock,
            patch.object(lockfile_resolve.subprocess, "run", return_value=make_completed()),
        ):
            git_mock.side_effect = [
                make_completed(stdout="theirs"),  # git show
                make_completed(),  # git add lockfile
                make_completed(),  # git add go.mod
            ]
            result = lockfile_resolve.resolve_lockfile(str(lockfile), strategy="theirs")

        assert result["resolved"] is True
        staged = [c.args[0] for c in git_mock.call_args_list if c.args[0][0] == "add"]
        assert ["add", str(lockfile)] in staged
        assert any("go.mod" in path for cmd in staged for path in cmd if isinstance(path, str))

    def test_staging_failure(self, lockfile_resolve: ModuleType, tmp_path: Path) -> None:
        write_clean_manifest(tmp_path)
        lockfile = tmp_path / "Cargo.lock"
        lockfile.write_text("ignored")

        with (
            patch.object(lockfile_resolve, "run_git") as git_mock,
            patch.object(lockfile_resolve.subprocess, "run", return_value=make_completed()),
        ):
            git_mock.side_effect = [
                make_completed(stdout="theirs"),
                make_completed(returncode=1, stderr="lock"),
            ]
            result = lockfile_resolve.resolve_lockfile(str(lockfile), strategy="theirs")

        assert result["resolved"] is False
        assert "staging failed" in result["message"]
