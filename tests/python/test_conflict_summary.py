"""Tests for conflict-summary.

Covers summarize_file recommendation routing. Pure functions; no subprocess
invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, TypedDict, cast


class _Summary(TypedDict):
    path: str
    extension: str
    mergiraf_supported: bool
    hunk_count: int
    hunks: list[object]
    recommendation: str


class _ErrorSummary(TypedDict):
    path: str
    error: str


class _ConflictSummaryModule(Protocol):
    def summarize_file(self, path: str, context_lines: int = ...) -> _Summary | _ErrorSummary: ...


CONFLICT = "<<<<<<< HEAD\nours-line\n=======\ntheirs-line\n>>>>>>> branch\n"


class TestSummarizeFile:
    def test_returns_error_for_missing_file(
        self, conflict_summary: _ConflictSummaryModule, tmp_path: Path
    ) -> None:
        result = conflict_summary.summarize_file(str(tmp_path / "nope.py"))
        assert "error" in result

    def test_generated_pyz_recommends_source_rebuild(
        self, conflict_summary: _ConflictSummaryModule, tmp_path: Path
    ) -> None:
        f = tmp_path / "bundle.pyz"
        _ = f.write_bytes(b"not text")
        result = cast(_Summary, conflict_summary.summarize_file(str(f)))
        assert result["hunk_count"] == 0
        assert "source conflicts" in result["recommendation"]
        assert "rebuild" in result["recommendation"]

    def test_supported_language_recommends_batch_resolve(
        self, conflict_summary: _ConflictSummaryModule, tmp_path: Path
    ) -> None:
        f = tmp_path / "foo.py"
        _ = f.write_text(f"x = 1\n{CONFLICT}y = 2\n")
        result = cast(_Summary, conflict_summary.summarize_file(str(f)))
        assert result["mergiraf_supported"] is True
        assert result["hunk_count"] == 1
        assert "batch-resolve" in result["recommendation"]

    def test_lockfile_recommends_lockfile_script(
        self, conflict_summary: _ConflictSummaryModule, tmp_path: Path
    ) -> None:
        f = tmp_path / "Cargo.lock"
        _ = f.write_text(CONFLICT)
        result = cast(_Summary, conflict_summary.summarize_file(str(f)))
        assert "lockfile-resolve" in result["recommendation"]

    def test_yaml_recommends_conflict_pick(
        self, conflict_summary: _ConflictSummaryModule, tmp_path: Path
    ) -> None:
        f = tmp_path / "config.yaml"
        _ = f.write_text(CONFLICT)
        result = cast(_Summary, conflict_summary.summarize_file(str(f)))
        assert "conflict-pick" in result["recommendation"]

    def test_unknown_extension_recommends_mergetool(
        self, conflict_summary: _ConflictSummaryModule, tmp_path: Path
    ) -> None:
        f = tmp_path / "data.bin"
        _ = f.write_text(CONFLICT)
        result = cast(_Summary, conflict_summary.summarize_file(str(f)))
        assert "mergetool" in result["recommendation"]


class TestSummarizeFileJsonShape:
    def test_serializable_to_json(self, conflict_summary: _ConflictSummaryModule, tmp_path: Path) -> None:
        f = tmp_path / "foo.py"
        _ = f.write_text(CONFLICT)
        summary = conflict_summary.summarize_file(str(f))
        encoded = json.dumps(summary)
        assert "ours" in encoded
        assert "theirs" in encoded


class TestBinaryFiles:
    def test_binary_content_recommends_side_selection_without_decoding(
        self, conflict_summary: _ConflictSummaryModule, tmp_path: Path
    ) -> None:
        f = tmp_path / "logo.png"
        _ = f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        summary = conflict_summary.summarize_file(str(f))
        assert "error" not in summary
        assert summary["extension"] == "png"
        assert summary["mergiraf_supported"] is False
        assert summary["hunk_count"] == 0
        assert "binary file" in summary["recommendation"]
        assert "git checkout --ours|--theirs" in summary["recommendation"]

    def test_binary_content_with_a_text_extension_is_not_routed_to_text_tools(
        self, conflict_summary: _ConflictSummaryModule, tmp_path: Path
    ) -> None:
        f = tmp_path / "data.json"
        _ = f.write_bytes(b"<<<<<<< HEAD\n\x00\x01\n=======\n\x02\n>>>>>>> b\n")
        summary = cast(_Summary, conflict_summary.summarize_file(str(f)))
        assert summary["recommendation"] != "conflict-pick.py"
        assert "binary file" in summary["recommendation"]
