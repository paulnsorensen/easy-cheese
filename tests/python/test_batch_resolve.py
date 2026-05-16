"""Tests for batch-resolve.

Mocks subprocess.run for mergiraf invocations and run_git for staging.
Covers: unsupported file, missing stages, mergiraf success, conflicts remain,
mergiraf failure, dry-run vs apply, formatters.
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


def _merged_path(cmd: list[str]) -> str:
    """Locate mergiraf's `-o <merged>` argument without depending on flag order."""
    return cmd[cmd.index("-o") + 1]


class TestResolveFile:
    def test_unsupported_extension(self, batch_resolve: ModuleType) -> None:
        result = batch_resolve.resolve_file("Cargo.lock")
        assert result["resolved"] is False
        assert result["supported"] is False
        assert "unsupported" in result["message"]

    def test_missing_stages(self, batch_resolve: ModuleType) -> None:
        with patch.object(batch_resolve, "extract_stages", return_value=(None, None, None)):
            result = batch_resolve.resolve_file("foo.py")
        assert result["resolved"] is False
        assert "stages" in result["message"]

    def test_clean_merge_dry_run(self, batch_resolve: ModuleType) -> None:
        # Mergiraf writes a clean merged file; dry_run means we don't touch the working tree.
        def fake_run(cmd, **kwargs):  # noqa: ANN001 — match subprocess.run signature
            Path(_merged_path(cmd)).write_text("clean-merged-output\n")
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

    def test_clean_merge_apply_stages_file(self, batch_resolve: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "foo.py"
        target.write_text("# original\n")

        def fake_run(cmd, **kwargs):  # noqa: ANN001
            Path(_merged_path(cmd)).write_text("merged-content\n")
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

    def test_apply_staging_failure(self, batch_resolve: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "foo.py"
        target.write_text("orig")

        def fake_run(cmd, **kwargs):  # noqa: ANN001
            Path(_merged_path(cmd)).write_text("merged\n")
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

    def test_conflicts_remain_after_mergiraf(self, batch_resolve: ModuleType) -> None:
        def fake_run(cmd, **kwargs):  # noqa: ANN001
            Path(_merged_path(cmd)).write_text("<<<<<<< x\nA\n=======\nB\n>>>>>>> y\n")
            return make_completed()

        with (
            patch.object(batch_resolve, "extract_stages", return_value=("B", "O", "T")),
            patch.object(batch_resolve.subprocess, "run", side_effect=fake_run),
        ):
            result = batch_resolve.resolve_file("foo.py", dry_run=True)
        assert result["resolved"] is False
        assert "conflicts remain" in result["message"]

    def test_mergiraf_command_failure(self, batch_resolve: ModuleType) -> None:
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

    def test_partial_resolve_with_nonzero_exit(self, batch_resolve: ModuleType) -> None:
        # Real mergiraf behavior: exits non-zero when conflicts remain, but still
        # writes a merged file. Script should classify as 'conflicts remain', not
        # 'mergiraf failed'.
        def fake_run(cmd, **kwargs):  # noqa: ANN001
            Path(_merged_path(cmd)).write_text("a\n<<<<<<< ours\nx\n=======\ny\n>>>>>>> theirs\n")
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
    def test_unsupported_extension_returns_message(self, batch_resolve: ModuleType) -> None:
        result = batch_resolve.debug_file("Cargo.lock")
        assert result["supported"] is False
        assert result["tempdir"] is None
        assert "unsupported" in result["message"]

    def test_missing_stages_returns_message(self, batch_resolve: ModuleType) -> None:
        with patch.object(batch_resolve, "extract_stages", return_value=(None, None, None)):
            result = batch_resolve.debug_file("foo.py")
        assert result["tempdir"] is None
        assert "stages" in result["message"]

    def test_clean_merge_captures_artifacts_and_passes_debug_env(
        self, batch_resolve: ModuleType, tmp_path: Path
    ) -> None:
        seen = {}

        def fake_run(cmd, **kwargs):  # noqa: ANN001
            seen["env"] = kwargs.get("env") or {}
            Path(_merged_path(cmd)).write_text("clean\n")
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
        assert Path(result["log_path"]).read_text() == "debug log line\n"
        assert Path(result["merged_path"]).read_text() == "clean\n"
        # Tempdir is NOT cleaned up — caller can inspect.
        assert Path(result["tempdir"]).exists()

    def test_conflicts_remain_reports_marker_count(
        self, batch_resolve: ModuleType, tmp_path: Path
    ) -> None:
        body = "<<<<<<< a\nx\n=======\ny\n>>>>>>> b\n<<<<<<< c\np\n=======\nq\n>>>>>>> d\n"

        def fake_run(cmd, **kwargs):  # noqa: ANN001
            Path(_merged_path(cmd)).write_text(body)
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
        self, batch_resolve: ModuleType, tmp_path: Path
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

    def test_format_debug_includes_inspect_block(self, batch_resolve: ModuleType) -> None:
        d = {
            "path": "foo.py",
            "supported": True,
            "tempdir": "/tmp/dbg",
            "merged_path": "/tmp/dbg/merged",
            "log_path": "/tmp/dbg/mergiraf.log",
            "conflict_markers": 0,
            "exit_code": 0,
            "message": "clean merge",
        }
        out = batch_resolve.format_debug(d)
        assert "tempdir: /tmp/dbg" in out
        assert "merged:" in out
        assert "log:" in out
        assert "inspect:" in out
        assert "cat /tmp/dbg/merged" in out

    def test_format_debug_short_circuits_for_unsupported(
        self, batch_resolve: ModuleType
    ) -> None:
        out = batch_resolve.format_debug(
            {"path": "x.lock", "supported": False, "message": "unsupported file type"}
        )
        assert "result: unsupported file type" in out
        assert "inspect:" not in out

    def test_format_debug_short_circuits_when_tempdir_none(
        self, batch_resolve: ModuleType
    ) -> None:
        d = {
            "path": "foo.py",
            "supported": True,
            "tempdir": None,
            "merged_path": None,
            "log_path": None,
            "conflict_markers": None,
            "exit_code": None,
            "message": "could not extract all three stages",
        }
        out = batch_resolve.format_debug(d)
        assert "result: could not extract all three stages" in out
        assert "inspect:" not in out
        assert "cat None" not in out

    def test_format_debug_shows_log_but_not_diff_when_merged_path_none(
        self, batch_resolve: ModuleType
    ) -> None:
        d = {
            "path": "foo.py",
            "supported": True,
            "tempdir": "/tmp/dbg",
            "merged_path": None,
            "log_path": "/tmp/dbg/mergiraf.log",
            "conflict_markers": None,
            "exit_code": 2,
            "message": "mergiraf produced no merged file (exit 2)",
        }
        out = batch_resolve.format_debug(d)
        assert "inspect:" in out
        assert "cat /tmp/dbg/mergiraf.log" in out
        assert "cat None" not in out
        assert "diff" not in out


class TestFormatters:
    def test_terse_includes_status_and_summary(self, batch_resolve: ModuleType) -> None:
        results = [
            {
                "path": "a.py",
                "resolved": True,
                "supported": True,
                "message": "would resolve cleanly",
            },
            {"path": "b.py", "resolved": False, "supported": True, "message": "conflicts remain"},
        ]
        out = batch_resolve.format_terse(results, dry_run=True)
        assert "ok a.py" in out
        assert "-- b.py" in out
        assert "1/2 resolved (dry-run)" in out
        assert "##" not in out  # No markdown headings.

    def test_terse_empty_results(self, batch_resolve: ModuleType) -> None:
        assert batch_resolve.format_terse([], dry_run=False) == "no conflicts"

    def test_verbose_emits_markdown_sections(self, batch_resolve: ModuleType) -> None:
        results = [
            {"path": "a.py", "resolved": True, "supported": True, "message": "ok"},
            {"path": "b.py", "resolved": False, "supported": True, "message": "fail"},
        ]
        out = batch_resolve.format_verbose(results, dry_run=True)
        assert "## Resolved" in out
        assert "## Needs Manual Resolution" in out
        assert "Run with --apply" in out
        assert "✓" not in out
        assert "✗" not in out
        assert "  ok a.py" in out
        assert "  -- b.py" in out
