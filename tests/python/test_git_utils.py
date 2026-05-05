"""Pure-function tests for git_utils. Subprocess paths are mocked."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest


def make_completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestGetFileExtension:
    def test_returns_extension_without_dot(self, git_utils: ModuleType) -> None:
        assert git_utils.get_file_extension("src/foo.py") == "py"

    def test_handles_no_extension(self, git_utils: ModuleType) -> None:
        assert git_utils.get_file_extension("Makefile") == ""

    def test_handles_multi_dot(self, git_utils: ModuleType) -> None:
        assert git_utils.get_file_extension("archive.tar.gz") == "gz"


class TestIsMergirafSupported:
    @pytest.mark.parametrize("path", ["foo.rs", "bar.go", "baz.py", "x.tsx", "y.md"])
    def test_supported_extensions(self, git_utils: ModuleType, path: str) -> None:
        assert git_utils.is_mergiraf_supported(path) is True

    @pytest.mark.parametrize("path", ["foo.lock", "bar.yaml", "Cargo.toml", "shell.sh", "no_ext"])
    def test_unsupported_extensions(self, git_utils: ModuleType, path: str) -> None:
        assert git_utils.is_mergiraf_supported(path) is False

    def test_case_insensitive(self, git_utils: ModuleType) -> None:
        assert git_utils.is_mergiraf_supported("Foo.PY") is True


class TestDetectLockfileType:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("Cargo.lock", "cargo"),
            ("nested/dir/Cargo.lock", "cargo"),
            ("package-lock.json", "npm"),
            ("yarn.lock", "yarn"),
            ("pnpm-lock.yaml", "pnpm"),
            ("poetry.lock", "poetry"),
            ("Pipfile.lock", "pipenv"),
            ("uv.lock", "uv"),
            ("Gemfile.lock", "bundler"),
            ("go.sum", "go"),
        ],
    )
    def test_known_lockfiles(self, git_utils: ModuleType, path: str, expected: str) -> None:
        assert git_utils.detect_lockfile_type(path) == expected

    def test_returns_none_for_unknown(self, git_utils: ModuleType) -> None:
        assert git_utils.detect_lockfile_type("requirements.txt") is None

    def test_case_insensitive_filename(self, git_utils: ModuleType) -> None:
        assert git_utils.detect_lockfile_type("CARGO.LOCK") == "cargo"


class TestParseConflictHunks:
    def test_no_conflicts_returns_empty(self, git_utils: ModuleType) -> None:
        assert git_utils.parse_conflict_hunks("just some\nplain text\n") == []

    def test_single_standard_hunk(self, git_utils: ModuleType) -> None:
        content = "before\n<<<<<<< HEAD\nours-line\n=======\ntheirs-line\n>>>>>>> branch\nafter\n"
        hunks = git_utils.parse_conflict_hunks(content)
        assert len(hunks) == 1
        assert hunks[0]["ours"] == ["ours-line"]
        assert hunks[0]["theirs"] == ["theirs-line"]
        assert hunks[0]["base"] == []
        assert hunks[0]["start_line"] == 2
        assert hunks[0]["end_line"] == 6

    def test_diff3_hunk_captures_base(self, git_utils: ModuleType) -> None:
        content = "<<<<<<< HEAD\nours\n||||||| merged\nbase\n=======\ntheirs\n>>>>>>> other\n"
        hunks = git_utils.parse_conflict_hunks(content)
        assert hunks[0]["base"] == ["base"]
        assert hunks[0]["ours"] == ["ours"]
        assert hunks[0]["theirs"] == ["theirs"]

    def test_multiple_hunks(self, git_utils: ModuleType) -> None:
        content = (
            "<<<<<<< HEAD\nA1\n=======\nB1\n>>>>>>> x\n"
            "middle\n"
            "<<<<<<< HEAD\nA2\n=======\nB2\n>>>>>>> x\n"
        )
        hunks = git_utils.parse_conflict_hunks(content)
        assert len(hunks) == 2
        assert hunks[0]["ours"] == ["A1"]
        assert hunks[1]["ours"] == ["A2"]


class TestGetSurroundingContext:
    def test_returns_lines_before_and_after(self, git_utils: ModuleType) -> None:
        content = "\n".join(f"line{i}" for i in range(1, 11))
        before, after = git_utils.get_surrounding_context(
            content, start_line=5, end_line=6, context_lines=2
        )
        assert before == ["3: line3", "4: line4"]
        assert after == ["7: line7", "8: line8"]

    def test_skips_conflict_marker_lines(self, git_utils: ModuleType) -> None:
        content = "a\nb\n<<<<<<< HEAD\nc\n=======\nd\n>>>>>>> x\ne\nf\n"
        before, after = git_utils.get_surrounding_context(
            content, start_line=3, end_line=7, context_lines=2
        )
        assert all("<<<<<<" not in line and "======" not in line for line in before + after)

    def test_handles_start_at_top(self, git_utils: ModuleType) -> None:
        content = "a\nb\n"
        before, _after = git_utils.get_surrounding_context(
            content, start_line=1, end_line=2, context_lines=3
        )
        assert before == []


class TestRunGit:
    def test_invokes_git_with_args(self, git_utils: ModuleType) -> None:
        with patch.object(
            git_utils.subprocess, "run", return_value=make_completed(stdout="ok")
        ) as run_mock:
            result = git_utils.run_git(["status"])
        assert result.stdout == "ok"
        run_mock.assert_called_once_with(["git", "status"], capture_output=True, text=True)


class TestGetConflictedFiles:
    def test_parses_newline_list(self, git_utils: ModuleType) -> None:
        with patch.object(git_utils, "run_git", return_value=make_completed(stdout="a.py\nb.rs\n")):
            assert git_utils.get_conflicted_files() == ["a.py", "b.rs"]

    def test_empty_output(self, git_utils: ModuleType) -> None:
        with patch.object(git_utils, "run_git", return_value=make_completed(stdout="")):
            assert git_utils.get_conflicted_files() == []

    def test_git_failure_returns_empty(self, git_utils: ModuleType) -> None:
        with patch.object(git_utils, "run_git", return_value=make_completed(returncode=128)):
            assert git_utils.get_conflicted_files() == []


class TestExtractStages:
    def test_returns_three_stages(self, git_utils: ModuleType) -> None:
        responses = [
            make_completed(stdout="BASE"),
            make_completed(stdout="OURS"),
            make_completed(stdout="THEIRS"),
        ]
        with patch.object(git_utils, "run_git", side_effect=responses):
            assert git_utils.extract_stages("foo.py") == ("BASE", "OURS", "THEIRS")

    def test_missing_base_returns_none_for_base(self, git_utils: ModuleType) -> None:
        responses = [
            make_completed(returncode=128),
            make_completed(stdout="OURS"),
            make_completed(stdout="THEIRS"),
        ]
        with patch.object(git_utils, "run_git", side_effect=responses):
            base, ours, theirs = git_utils.extract_stages("foo.py")
        assert base is None
        assert ours == "OURS"
        assert theirs == "THEIRS"


class TestHasConflictMarkers:
    def test_returns_true_when_markers_present(self, git_utils: ModuleType, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("<<<<<<< HEAD\na\n=======\nb\n>>>>>>> x\n")
        assert git_utils.has_conflict_markers(str(f)) is True

    def test_returns_false_when_clean(self, git_utils: ModuleType, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("clean\n")
        assert git_utils.has_conflict_markers(str(f)) is False

    def test_returns_false_when_missing(self, git_utils: ModuleType, tmp_path: Path) -> None:
        assert git_utils.has_conflict_markers(str(tmp_path / "missing.txt")) is False
