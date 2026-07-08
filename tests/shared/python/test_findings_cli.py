"""Tests for shared/scripts/findings_cli.py — render-table + parse-selection CLI."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"
FINDINGS_CLI = SHARED_SCRIPTS / "findings_cli.py"

SAMPLE_REPORT = """\
status: ok
next: cure

## Findings

## Blocker

- **[encapsulation:blocker]** `src/users/index.ts:42` — `index` re-exports `SqlPgUser` across slice boundary.
  - location: contract · fix-cost-now: sprawling · fix-cost-later: structural · confidence: certain
  - recommendation: define `User` in the slice's public types, map at the boundary.

## High

- **[security:high]** `src/handler.ts:108` — Unvalidated path joined into fs.read.
  - location: contract · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
  - recommendation: add allowlist check before joining.

## Medium

- **[complexity:medium]** `src/util.ts:200-240` — Function is 41 lines and 4 levels nested.
  - location: module · fix-cost-now: contained · fix-cost-later: spreading · confidence: speculating
  - recommendation: extract helpers.

## Low

- **[deslop:low]** `src/old.ts:55-60` — Unused export `_helper`.
  - location: class · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
  - recommendation: remove the export.
"""


def _load(name: str, path: Path) -> ModuleType:
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def findings_lib() -> ModuleType:
    # Load via the same name conftest uses so cached instance is shared.
    return _load("findings", SHARED_SCRIPTS / "findings.py")


@pytest.fixture
def report_path(tmp_path: Path) -> Path:
    path = tmp_path / "age-report.md"
    path.write_text(SAMPLE_REPORT)
    return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(FINDINGS_CLI), *args],
        capture_output=True,
        text=True,
    )


class TestRenderTable:
    def test_matches_library_output(self, report_path: Path, findings_lib: ModuleType) -> None:
        result = _run("render-table", "--report", str(report_path))
        assert result.returncode == 0, result.stderr
        expected = findings_lib.render_selection_table(
            findings_lib.parse_findings_report(SAMPLE_REPORT)
        )
        assert result.stdout.rstrip("\n") == expected.rstrip("\n")

    def test_json_mode_dumps_string(self, report_path: Path, findings_lib: ModuleType) -> None:
        result = _run("render-table", "--report", str(report_path), "--json")
        assert result.returncode == 0, result.stderr
        decoded = json.loads(result.stdout)
        expected = findings_lib.render_selection_table(
            findings_lib.parse_findings_report(SAMPLE_REPORT)
        )
        assert decoded == expected

    def test_confidence_column_and_values(self, report_path: Path, findings_lib: ModuleType) -> None:
        result = _run("render-table", "--report", str(report_path))
        assert result.returncode == 0, result.stderr
        assert "confidence" in result.stdout
        assert "certain" in result.stdout
        assert "speculating" in result.stdout


class TestParseSelection:
    def test_all_high_ids(self, report_path: Path, findings_lib: ModuleType) -> None:
        result = _run(
            "parse-selection",
            "--report",
            str(report_path),
            "--selection",
            "all-high",
        )
        assert result.returncode == 0, result.stderr
        expected_ids = findings_lib.parse_selection(
            "all-high", findings_lib.parse_findings_report(SAMPLE_REPORT)
        )
        printed = [int(line) for line in result.stdout.splitlines() if line.strip()]
        assert printed == expected_ids

    def test_all_high_ids_literal_pin(self, report_path: Path) -> None:
        # SAMPLE_REPORT has blocker id=1, high id=2; all-high must return exactly [1, 2].
        result = _run(
            "parse-selection",
            "--report",
            str(report_path),
            "--selection",
            "all-high",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == [1, 2]

    def test_json_mode_dumps_list(self, report_path: Path, findings_lib: ModuleType) -> None:
        result = _run(
            "parse-selection",
            "--report",
            str(report_path),
            "--selection",
            "all-high",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        expected_ids = findings_lib.parse_selection(
            "all-high", findings_lib.parse_findings_report(SAMPLE_REPORT)
        )
        assert json.loads(result.stdout) == expected_ids

    def test_specific_ids(self, report_path: Path) -> None:
        result = _run(
            "parse-selection",
            "--report",
            str(report_path),
            "--selection",
            "1,3",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == [1, 3]

    def test_unknown_verb_exits_two(self, report_path: Path) -> None:
        result = _run(
            "parse-selection",
            "--report",
            str(report_path),
            "--selection",
            "nuke-it-all",
        )
        assert result.returncode == 2
        assert "ERROR:" in result.stderr


class TestMissingFile:
    def test_render_table_missing_file_exits_two(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        result = _run("render-table", "--report", str(missing))
        assert result.returncode == 2
        assert "report not found" in result.stderr
        assert str(missing) in result.stderr

    def test_parse_selection_missing_file_exits_two(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        result = _run(
            "parse-selection", "--report", str(missing), "--selection", "all"
        )
        assert result.returncode == 2
        assert "report not found" in result.stderr


class TestConfidenceParsing:
    def test_findings_expose_confidence(self, findings_lib: ModuleType) -> None:
        findings = findings_lib.parse_findings_report(SAMPLE_REPORT)
        by_id = {f.id: f for f in findings}
        assert by_id[1].confidence == "certain"
        assert by_id[3].confidence == "speculating"

    def test_missing_confidence_parses_as_none(self, findings_lib: ModuleType) -> None:
        report = """\
## Blocker

- **[encapsulation:blocker]** `src/x.ts:1` — missing confidence label.
  - location: contract · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: fix it.
"""
        findings = findings_lib.parse_findings_report(report)
        assert len(findings) == 1
        assert findings[0].confidence is None
        rendered = findings_lib.render_selection_table(findings)
        assert "encapsulation" in rendered


class TestArgparseFailures:
    def test_missing_report_arg_exits_two(self) -> None:
        result = _run("render-table")
        assert result.returncode == 2
        assert "report" in result.stderr.lower()

    def test_missing_selection_arg_exits_two(self, report_path: Path) -> None:
        result = _run("parse-selection", "--report", str(report_path))
        assert result.returncode == 2
        assert "selection" in result.stderr.lower()

    def test_missing_subcommand_exits_two(self) -> None:
        result = _run()
        assert result.returncode == 2


class TestHelp:
    def test_top_level_help_lists_both_subcommands(self) -> None:
        result = subprocess.run(
            [sys.executable, str(FINDINGS_CLI), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "render-table" in result.stdout
        assert "parse-selection" in result.stdout
