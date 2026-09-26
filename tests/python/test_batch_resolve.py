"""Tests for batch-resolve.

Mocks subprocess.run for mergiraf invocations and run_git for staging.
Covers: unsupported file, missing stages, mergiraf success, conflicts remain,
mergiraf failure, dry-run vs apply.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType
from typing import Protocol, TypedDict, cast
from unittest.mock import patch


class _ResolveResult(TypedDict):
    path: str
    supported: bool
    resolved: bool
    message: str


class _DebugResult(TypedDict):
    path: str
    supported: bool
    tempdir: str | None
    merged_path: str | None
    log_path: str | None
    conflict_markers: int | None
    exit_code: int | None
    message: str


class _BatchResolveModule(Protocol):
    subprocess: ModuleType
    tempfile: ModuleType

    def resolve_file(
        self, path: str, dry_run: bool = ..., verbose: bool = ...
    ) -> _ResolveResult: ...

    def debug_file(self, path: str, keep_dir: str | None = ...) -> _DebugResult: ...

    def extract_stages(self, path: str) -> tuple[str | None, str | None, str | None]: ...

    def run_git(
        self,
        args: list[str],
        capture_output: bool = ...,
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]: ...


def make_completed(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["x"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _merged_path(cmd: list[str]) -> str:
    """Locate mergiraf's `-o <merged>` argument without depending on flag order."""
    return cmd[cmd.index("-o") + 1]


class TestResolveFile:
    def test_unsupported_extension(self, batch_resolve: _BatchResolveModule) -> None:
        result = batch_resolve.resolve_file("Cargo.lock")
        assert result["resolved"] is False
        assert result["supported"] is False
        assert "unsupported" in result["message"]

    def test_generated_pyz_recommends_source_rebuild(
        self, batch_resolve: _BatchResolveModule
    ) -> None:
        result = batch_resolve.resolve_file("bundle.pyz")
        assert result["resolved"] is False
        assert result["supported"] is False
        assert "source conflicts" in result["message"]
        assert "rebuild" in result["message"]

    def test_missing_stages(self, batch_resolve: _BatchResolveModule) -> None:
        with patch.object(batch_resolve, "extract_stages", return_value=(None, None, None)):
            result = batch_resolve.resolve_file("foo.py")
        assert result["resolved"] is False
        assert "stages" in result["message"]

    def test_clean_merge_dry_run(self, batch_resolve: _BatchResolveModule) -> None:
        # Mergiraf writes a clean merged file; dry_run means we don't touch the working tree.
        def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            _ = Path(_merged_path(cmd)).write_text("clean-merged-output\n")
            return make_completed()

        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(batch_resolve.subprocess, "run", side_effect=fake_run),
            patch.object(batch_resolve, "run_git") as git_mock,
        ):
            result = batch_resolve.resolve_file("foo.py", dry_run=True)
        assert result["resolved"] is True
        assert result["message"] == "would resolve cleanly"
        git_mock.assert_not_called()

    def test_clean_merge_apply_stages_file(
        self, batch_resolve: _BatchResolveModule, tmp_path: Path
    ) -> None:
        target = tmp_path / "foo.py"
        _ = target.write_text("# original\n")

        def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            _ = Path(_merged_path(cmd)).write_text("merged-content\n")
            return make_completed()

        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(batch_resolve.subprocess, "run", side_effect=fake_run),
            patch.object(batch_resolve, "run_git", return_value=make_completed()),
        ):
            result = batch_resolve.resolve_file(str(target), dry_run=False)

        assert result["resolved"] is True
        assert "resolved and staged" in result["message"]
        assert target.read_text() == "merged-content\n"

    def test_apply_staging_failure(self, batch_resolve: _BatchResolveModule, tmp_path: Path) -> None:
        target = tmp_path / "foo.py"
        _ = target.write_text("orig")

        def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            _ = Path(_merged_path(cmd)).write_text("merged\n")
            return make_completed()

        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(batch_resolve.subprocess, "run", side_effect=fake_run),
            patch.object(
                batch_resolve, "run_git", return_value=make_completed(returncode=1, stderr="locked")
            ),
        ):
            result = batch_resolve.resolve_file(str(target), dry_run=False)
        assert result["resolved"] is False
        assert "staging failed" in result["message"]

    def test_conflicts_remain_after_mergiraf(self, batch_resolve: _BatchResolveModule) -> None:
        def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            _ = Path(_merged_path(cmd)).write_text("<<<<<<< x\nA\n=======\nB\n>>>>>>> y\n")
            return make_completed()

        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(batch_resolve.subprocess, "run", side_effect=fake_run),
        ):
            result = batch_resolve.resolve_file("foo.py", dry_run=True)
        assert result["resolved"] is False
        assert "conflicts remain" in result["message"]

    def test_mergiraf_command_failure(self, batch_resolve: _BatchResolveModule) -> None:
        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(
                batch_resolve.subprocess,
                "run",
                return_value=make_completed(returncode=2, stderr="boom"),
            ),
        ):
            result = batch_resolve.resolve_file("foo.py", dry_run=True)
        assert result["resolved"] is False
        assert "mergiraf failed" in result["message"]
        assert "boom" in result["message"]

    def test_partial_resolve_with_nonzero_exit(self, batch_resolve: _BatchResolveModule) -> None:
        # Real mergiraf behavior: exits non-zero when conflicts remain, but still
        # writes a merged file. Script should classify as 'conflicts remain', not
        # 'mergiraf failed'.
        def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            _ = Path(_merged_path(cmd)).write_text("a\n<<<<<<< ours\nx\n=======\ny\n>>>>>>> theirs\n")
            return make_completed(returncode=1)

        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(batch_resolve.subprocess, "run", side_effect=fake_run),
        ):
            result = batch_resolve.resolve_file("foo.py", dry_run=True)
        assert result["resolved"] is False
        assert "conflicts remain" in result["message"]
        assert "mergiraf failed" not in result["message"]


class TestDebugFile:
    def test_unsupported_extension_returns_message(self, batch_resolve: _BatchResolveModule) -> None:
        result = batch_resolve.debug_file("Cargo.lock")
        assert result["supported"] is False
        assert result["tempdir"] is None
        assert "unsupported" in result["message"]

    def test_generated_pyz_returns_rebuild_guidance(
        self, batch_resolve: _BatchResolveModule
    ) -> None:
        result = batch_resolve.debug_file("bundle.pyz")
        assert result["supported"] is False
        assert result["tempdir"] is None
        assert "source conflicts" in result["message"]
        assert "rebuild" in result["message"]

    def test_missing_stages_returns_message(self, batch_resolve: _BatchResolveModule) -> None:
        with patch.object(batch_resolve, "extract_stages", return_value=(None, None, None)):
            result = batch_resolve.debug_file("foo.py")
        assert result["tempdir"] is None
        assert "stages" in result["message"]

    def test_clean_merge_captures_artifacts_and_passes_debug_env(
        self, batch_resolve: _BatchResolveModule, tmp_path: Path
    ) -> None:
        seen: dict[str, dict[str, str]] = {}

        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            seen["env"] = cast(dict[str, str], kwargs.get("env") or {})
            _ = Path(_merged_path(cmd)).write_text("clean\n")
            return make_completed(stderr="debug log line\n")

        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(batch_resolve.subprocess, "run", side_effect=fake_run),
            patch.object(
                batch_resolve.tempfile, "mkdtemp", return_value=str(tmp_path / "dbg")
            ),
        ):
            (tmp_path / "dbg").mkdir()
            result = batch_resolve.debug_file("foo.py")

        assert seen["env"].get("RUST_LOG") == "mergiraf=debug"
        assert result["supported"] is True
        assert result["conflict_markers"] == 0
        assert result["message"] == "clean merge"
        assert Path(cast(str, result["log_path"])).read_text() == "debug log line\n"
        assert Path(cast(str, result["merged_path"])).read_text() == "clean\n"
        # Tempdir is NOT cleaned up — caller can inspect.
        assert Path(cast(str, result["tempdir"])).exists()

    def test_conflicts_remain_reports_marker_count(
        self, batch_resolve: _BatchResolveModule, tmp_path: Path
    ) -> None:
        body = "<<<<<<< a\nx\n=======\ny\n>>>>>>> b\n<<<<<<< c\np\n=======\nq\n>>>>>>> d\n"

        def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            _ = Path(_merged_path(cmd)).write_text(body)
            return make_completed(returncode=1, stderr="")

        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(batch_resolve.subprocess, "run", side_effect=fake_run),
            patch.object(
                batch_resolve.tempfile, "mkdtemp", return_value=str(tmp_path / "dbg")
            ),
        ):
            (tmp_path / "dbg").mkdir()
            result = batch_resolve.debug_file("foo.py")

        assert result["conflict_markers"] == 2
        assert "2 conflict marker(s) remain" in result["message"]

    def test_mergiraf_missing_output_file(
        self, batch_resolve: _BatchResolveModule, tmp_path: Path
    ) -> None:
        # mergiraf fails hard and writes no output.
        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(
                batch_resolve.subprocess, "run", return_value=make_completed(returncode=2)
            ),
            patch.object(
                batch_resolve.tempfile, "mkdtemp", return_value=str(tmp_path / "dbg")
            ),
        ):
            (tmp_path / "dbg").mkdir()
            result = batch_resolve.debug_file("foo.py")

        assert result["merged_path"] is None
        assert "no merged file" in result["message"]
        assert result["exit_code"] == 2

class TestBinaryFiles:
    """A binary file with a mergiraf extension must never reach the text merge path."""

    def test_resolve_file_refuses_binary_content_before_stage_extraction(
        self, batch_resolve: _BatchResolveModule, tmp_path: Path
    ) -> None:
        path = tmp_path / "blob.py"
        _ = path.write_bytes(b"\x89PNG\x00\xff\xfe")
        with patch.object(batch_resolve, "extract_stages") as stages:
            result = batch_resolve.resolve_file(str(path), dry_run=False)
        stages.assert_not_called()
        assert result["resolved"] is False
        assert result["supported"] is False
        assert "binary file" in result["message"]
        assert path.read_bytes() == b"\x89PNG\x00\xff\xfe"

    def test_debug_file_refuses_binary_content(
        self, batch_resolve: _BatchResolveModule, tmp_path: Path
    ) -> None:
        path = tmp_path / "blob.py"
        _ = path.write_bytes(b"\x00\x01\x02")
        with patch.object(batch_resolve, "extract_stages") as stages:
            result = batch_resolve.debug_file(str(path))
        stages.assert_not_called()
        assert result["supported"] is False
        assert result["tempdir"] is None
        assert "binary file" in result["message"]
