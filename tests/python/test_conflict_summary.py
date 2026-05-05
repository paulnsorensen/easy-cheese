"""Tests for conflict-summary.

Covers summarize_file recommendation routing and both output formatters
(terse + verbose). Pure functions; no subprocess invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

CONFLICT = "<<<<<<< HEAD\nours-line\n=======\ntheirs-line\n>>>>>>> branch\n"


class TestSummarizeFile:
    def test_returns_error_for_missing_file(
        self, conflict_summary: ModuleType, tmp_path: Path
    ) -> None:
        result = conflict_summary.summarize_file(str(tmp_path / "nope.py"))
        assert "error" in result

    def test_supported_language_recommends_batch_resolve(
        self, conflict_summary: ModuleType, tmp_path: Path
    ) -> None:
        f = tmp_path / "foo.py"
        f.write_text(f"x = 1\n{CONFLICT}y = 2\n")
        result = conflict_summary.summarize_file(str(f))
        assert result["mergiraf_supported"] is True
        assert result["hunk_count"] == 1
        assert "batch-resolve" in result["recommendation"]

    def test_lockfile_recommends_lockfile_script(
        self, conflict_summary: ModuleType, tmp_path: Path
    ) -> None:
        f = tmp_path / "Cargo.lock"
        f.write_text(CONFLICT)
        result = conflict_summary.summarize_file(str(f))
        assert "lockfile-resolve" in result["recommendation"]

    def test_yaml_recommends_conflict_pick(
        self, conflict_summary: ModuleType, tmp_path: Path
    ) -> None:
        f = tmp_path / "config.yaml"
        f.write_text(CONFLICT)
        result = conflict_summary.summarize_file(str(f))
        assert "conflict-pick" in result["recommendation"]

    def test_unknown_extension_recommends_mergetool(
        self, conflict_summary: ModuleType, tmp_path: Path
    ) -> None:
        f = tmp_path / "data.bin"
        f.write_text(CONFLICT)
        result = conflict_summary.summarize_file(str(f))
        assert "mergetool" in result["recommendation"]


class TestFormatTerseOutput:
    def test_empty_returns_no_conflicts(self, conflict_summary: ModuleType) -> None:
        assert conflict_summary.format_terse_output([]) == "no conflicts"

    def test_emits_legend_header(self, conflict_summary: ModuleType, tmp_path: Path) -> None:
        f = tmp_path / "foo.py"
        f.write_text(CONFLICT)
        out = conflict_summary.format_terse_output([conflict_summary.summarize_file(str(f))])
        first_line = out.splitlines()[0]
        assert first_line == "# legend: +ours |base -theirs"

    def test_recommendation_uses_no_dry_run_flag(
        self, conflict_summary: ModuleType, tmp_path: Path
    ) -> None:
        # Regression: --dry-run flag was removed; recommendation must not mention it.
        f = tmp_path / "foo.py"
        f.write_text(CONFLICT)
        result = conflict_summary.summarize_file(str(f))
        assert result["recommendation"] == "batch-resolve.py"

    def test_includes_metadata_line(self, conflict_summary: ModuleType, tmp_path: Path) -> None:
        f = tmp_path / "foo.py"
        f.write_text(CONFLICT)
        summaries = [conflict_summary.summarize_file(str(f))]
        out = conflict_summary.format_terse_output(summaries)
        assert "hunks=1" in out
        assert "ext=py" in out
        assert "mergiraf=y" in out

    def test_caps_ours_at_five_lines(self, conflict_summary: ModuleType, tmp_path: Path) -> None:
        ours = "\n".join(f"o{i}" for i in range(10))
        content = f"<<<<<<< HEAD\n{ours}\n=======\nt0\n>>>>>>> branch\n"
        f = tmp_path / "foo.py"
        f.write_text(content)
        out = conflict_summary.format_terse_output([conflict_summary.summarize_file(str(f))])
        # Five "+ oN" lines should appear; the rest collapses to a count line.
        assert out.count("+ o") == 5
        assert "+(5 more)" in out

    def test_does_not_emit_markdown_headings(
        self, conflict_summary: ModuleType, tmp_path: Path
    ) -> None:
        f = tmp_path / "foo.py"
        f.write_text(CONFLICT)
        out = conflict_summary.format_terse_output([conflict_summary.summarize_file(str(f))])
        # Verbose markdown markers should be absent in terse output.
        assert "## " not in out
        assert "### " not in out
        assert "**Recommendation:**" not in out


class TestFormatVerboseOutput:
    def test_empty_returns_human_message(self, conflict_summary: ModuleType) -> None:
        assert conflict_summary.format_verbose_output([]) == "No conflicted files found."

    def test_emits_markdown_headings(self, conflict_summary: ModuleType, tmp_path: Path) -> None:
        f = tmp_path / "foo.py"
        f.write_text(CONFLICT)
        out = conflict_summary.format_verbose_output([conflict_summary.summarize_file(str(f))])
        assert "## " in out
        assert "### Hunk 1" in out
        assert "**Recommendation:**" in out


class TestSummarizeFileJsonShape:
    def test_serializable_to_json(self, conflict_summary: ModuleType, tmp_path: Path) -> None:
        f = tmp_path / "foo.py"
        f.write_text(CONFLICT)
        summary = conflict_summary.summarize_file(str(f))
        encoded = json.dumps(summary)
        assert "ours" in encoded
        assert "theirs" in encoded
