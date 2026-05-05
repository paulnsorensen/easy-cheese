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
