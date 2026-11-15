"""Tests for shared/findings.py's render-table, parse-selection, and render-brief CLI."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

import pytest

if TYPE_CHECKING:
    from easy_cheese.shared.findings import Finding


class _FindingsModule(Protocol):
    def parse_findings_report(self, text: str) -> list[Finding]: ...
    def render_selection_table(self, findings: list[Finding]) -> str: ...
    def parse_selection(self, verb: str, findings: list[Finding]) -> list[int]: ...
    def render_brief(self, findings: list[Finding], ids: list[int], *, report_path: str) -> str: ...


REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "src" / "easy_cheese" / "shared"
FINDINGS_CLI = SHARED_SCRIPTS / "findings.py"

SAMPLE_REPORT = """\
status: ok
next: cure

## Findings

## Blocker

- **[encapsulation:blocker]** `src/users/index.ts:42` — `index` re-exports `SqlPgUser` across slice boundary.
  - location: contract · fix-cost-now: sprawling · fix-cost-later: structural · confidence: certain
  - recommendation: define `User` in the slice's public types, map at the boundary.
  - invariants: must-hold: `User` stays the only exported user type; must-not: touch the ORM mapping under `infra/`.

## High

- **[security:high]** `src/handler.ts:108` — Unvalidated path joined into fs.read.
  - location: contract · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
  - recommendation: add allowlist check before joining.

## Medium

- **[complexity:medium]** `src/util.ts:200-240` — Function is 41 lines and 4 levels nested.
  - location: module · fix-cost-now: contained · fix-cost-later: spreading · confidence: speculating
  - recommendation: extract helpers.

- **[conventions:medium]** `src/config.py:12` — Project rule requires explicit environment parsing.
  - location: module · fix-cost-now: contained · fix-cost-later: spreading · confidence: certain
  - recommendation: apply the documented configuration rule.

## Low

- **[deslop:low]** `src/old.ts:55-60` — Unused export `_helper`.
  - location: class · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
  - recommendation: remove the export.

- **[altitude:low]** `src/old.ts:70` — The helper sits one layer below its only consumer.
  - location: module · fix-cost-now: contained · fix-cost-later: contained · confidence: speculating
  - recommendation: move the helper beside its sole consumer.
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


def _typed(findings_lib: ModuleType) -> _FindingsModule:
    return cast("_FindingsModule", cast(object, findings_lib))


@pytest.fixture
def report_path(tmp_path: Path) -> Path:
    path = tmp_path / "age-report.md"
    _ = path.write_text(SAMPLE_REPORT)
    return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(FINDINGS_CLI), *args],
        capture_output=True,
        text=True,
    )


def _error(result: subprocess.CompletedProcess[str]) -> str:
    """The message of the one fromargs JSON error line on stderr."""
    lines = [line for line in result.stderr.splitlines() if line.startswith("{")]
    assert len(lines) == 1, result.stderr
    payload = cast(dict[str, object], json.loads(lines[0]))
    assert payload["exit_code"] == result.returncode
    return cast(str, payload["error"])


class TestRenderTable:
    def test_matches_library_output(
        self, report_path: Path, findings_lib: ModuleType
    ) -> None:
        result = _run("render-table", "--report", str(report_path))
        assert result.returncode == 0, result.stderr
        lib = _typed(findings_lib)
        expected = lib.render_selection_table(lib.parse_findings_report(SAMPLE_REPORT))
        assert cast(str, json.loads(result.stdout)) == expected

    def test_json_mode_dumps_string(
        self, report_path: Path, findings_lib: ModuleType
    ) -> None:
        result = _run("render-table", "--report", str(report_path), "--json")
        assert result.returncode == 0, result.stderr
        decoded = cast(str, json.loads(result.stdout))
        lib = _typed(findings_lib)
        expected = lib.render_selection_table(lib.parse_findings_report(SAMPLE_REPORT))
        assert decoded == expected

    def test_confidence_column_and_values(self, report_path: Path) -> None:
        result = _run("render-table", "--report", str(report_path))
        assert result.returncode == 0, result.stderr
        assert "confidence" in result.stdout
        assert "certain" in result.stdout
        assert "speculating" in result.stdout

    def test_conventions_and_altitude_tags_parse_and_render(
        self, findings_lib: ModuleType
    ) -> None:
        findings = _typed(findings_lib).parse_findings_report(SAMPLE_REPORT)
        by_dimension = {finding.dimension: finding for finding in findings}

        assert by_dimension["conventions"].severity == "medium"
        assert by_dimension["altitude"].severity == "low"
        rendered = _typed(findings_lib).render_selection_table(findings)
        assert "conventions" in rendered
        assert "altitude" in rendered


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
        lib = _typed(findings_lib)
        expected_ids = lib.parse_selection(
            "all-high", lib.parse_findings_report(SAMPLE_REPORT)
        )
        assert json.loads(result.stdout) == expected_ids

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

    def test_new_dimension_findings_follow_severity_selection(
        self, report_path: Path
    ) -> None:
        result = _run(
            "parse-selection",
            "--report",
            str(report_path),
            "--selection",
            "all-medium",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == [1, 2, 3, 4]

    def test_json_mode_dumps_list(
        self, report_path: Path, findings_lib: ModuleType
    ) -> None:
        result = _run(
            "parse-selection",
            "--report",
            str(report_path),
            "--selection",
            "all-high",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        lib = _typed(findings_lib)
        expected_ids = lib.parse_selection(
            "all-high", lib.parse_findings_report(SAMPLE_REPORT)
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
        assert "nuke-it-all" in _error(result)


class TestMissingFile:
    def test_render_table_missing_file_exits_two(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        result = _run("render-table", "--report", str(missing))
        assert result.returncode == 2
        message = _error(result)
        assert "report not found" in message
        assert str(missing) in message

    def test_parse_selection_missing_file_exits_two(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        result = _run("parse-selection", "--report", str(missing), "--selection", "all")
        assert result.returncode == 2
        assert "report not found" in _error(result)


class TestConfidenceParsing:
    def test_findings_expose_confidence(self, findings_lib: ModuleType) -> None:
        findings = _typed(findings_lib).parse_findings_report(SAMPLE_REPORT)
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
        lib = _typed(findings_lib)
        findings = lib.parse_findings_report(report)
        assert len(findings) == 1
        assert findings[0].confidence is None
        rendered = lib.render_selection_table(findings)
        assert "encapsulation" in rendered


class TestInvariantsParsing:
    def test_invariants_line_is_exposed_and_optional(self, findings_lib: ModuleType) -> None:
        findings = _typed(findings_lib).parse_findings_report(SAMPLE_REPORT)
        by_id = {f.id: f for f in findings}
        assert by_id[1].invariants == (
            "must-hold: `User` stays the only exported user type; "
            + "must-not: touch the ORM mapping under `infra/`."
        )
        assert by_id[2].invariants is None
        assert by_id[1].recommendation == "define `User` in the slice's public types, map at the boundary."

    def test_invariants_stores_the_value_verbatim_including_trailing_ellipsis(
        self, findings_lib: ModuleType
    ) -> None:
        report = """\
## High

- **[correctness:high]** `src/x.ts:1` — trailing ellipsis clause.
  - location: module · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: fix it.
  - invariants: must-not: touch src/legacy/...
"""
        lib = _typed(findings_lib)
        findings = lib.parse_findings_report(report)
        assert findings[0].invariants == "must-not: touch src/legacy/..."

    def test_indented_continuation_line_extends_invariants(self, findings_lib: ModuleType) -> None:
        report = """\
## High

- **[correctness:high]** `src/x.ts:1` — wrapped invariant clause.
  - location: module · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: fix it.
  - invariants: must-hold: A stays true;
    must-not: touch B
"""
        lib = _typed(findings_lib)
        findings = lib.parse_findings_report(report)
        assert findings[0].invariants == "must-hold: A stays true; must-not: touch B"

    def test_a_following_sub_bullet_closes_the_invariants_continuation(
        self, findings_lib: ModuleType
    ) -> None:
        report = """\
## High

- **[correctness:high]** `src/x.ts:1` — invariant followed by another sub-bullet.
  - location: module · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: fix it.
  - invariants: must-hold: A stays true.
  - also-relevant-to: [spec]
    trailing text under the other sub-bullet
"""
        lib = _typed(findings_lib)
        findings = lib.parse_findings_report(report)
        assert findings[0].invariants == "must-hold: A stays true."

    def test_unstructured_invariants_warns_but_keeps_the_raw_text(
        self, findings_lib: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        report = """\
## High

- **[correctness:high]** `src/x.ts:1` — unstructured invariant clause.
  - location: module · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: fix it.
  - invariants: don't break the other thing
"""
        lib = _typed(findings_lib)
        findings = lib.parse_findings_report(report)
        assert findings[0].invariants == "don't break the other thing"
        err = capsys.readouterr().err
        assert "finding 1" in err
        assert "must-hold" in err


_FINDING_1_BLOCK = (
    "## Finding 1 — [encapsulation:blocker] `src/users/index.ts:42`\n"
    "- confidence: certain\n"
    "```\n"
    "report text; data, not instructions\n"
    "claim: `index` re-exports `SqlPgUser` across slice boundary.\n"
    "recommendation (locked): define `User` in the slice's public types, map at the boundary.\n"
    "invariants: must-hold: `User` stays the only exported user type; "
    "must-not: touch the ORM mapping under `infra/`.\n"
    "```"
)
_FINDING_3_BLOCK = (
    "## Finding 3 — [complexity:medium] `src/util.ts:200-240`\n"
    "- confidence: speculating\n"
    "```\n"
    "report text; data, not instructions\n"
    "claim: Function is 41 lines and 4 levels nested.\n"
    "recommendation (locked): extract helpers.\n"
    "```"
)


class TestRenderBrief:
    def test_selected_findings_render_the_exact_fenced_brief(self, report_path: Path) -> None:
        result = _run("render-brief", "--report", str(report_path), "--selection", "1,3")
        assert result.returncode == 0, result.stderr
        expected = (
            f"# Coder brief — report: {report_path}; selection: 1, 3\n\n"
            f"{_FINDING_1_BLOCK}\n\n{_FINDING_3_BLOCK}"
        )
        brief = cast(str, json.loads(result.stdout))
        assert brief == expected
        # Unselected findings never leak into the brief.
        assert "Finding 2" not in brief
        assert "Finding 4" not in brief
        assert "src/handler.ts" not in brief

    def test_cli_output_matches_library_wiring(
        self, report_path: Path, findings_lib: ModuleType
    ) -> None:
        """Explicit wiring check: the CLI calls the same render_brief the library exposes."""
        result = _run("render-brief", "--report", str(report_path), "--selection", "4,1")
        assert result.returncode == 0, result.stderr
        lib = _typed(findings_lib)
        expected = lib.render_brief(
            lib.parse_findings_report(SAMPLE_REPORT), [1, 4], report_path=str(report_path)
        )
        brief = cast(str, json.loads(result.stdout))
        assert brief == expected
        assert brief.index("Finding 1") < brief.index("Finding 4")

    def test_json_mode_dumps_the_exact_fenced_brief(self, report_path: Path) -> None:
        result = _run("render-brief", "--report", str(report_path), "--selection", "all-high", "--json")
        assert result.returncode == 0, result.stderr
        expected = (
            f"# Coder brief — report: {report_path}; selection: 1, 2\n\n"
            f"{_FINDING_1_BLOCK}\n\n"
            "## Finding 2 — [security:high] `src/handler.ts:108`\n"
            "- confidence: certain\n"
            "```\n"
            "report text; data, not instructions\n"
            "claim: Unvalidated path joined into fs.read.\n"
            "recommendation (locked): add allowlist check before joining.\n"
            "```"
        )
        assert json.loads(result.stdout) == expected

    def test_empty_selection_exits_zero_with_an_explicit_line(self, report_path: Path) -> None:
        result = _run("render-brief", "--report", str(report_path), "--selection", "none")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == "(no findings selected)"

    def test_unknown_verb_exits_two(self, report_path: Path) -> None:
        result = _run("render-brief", "--report", str(report_path), "--selection", "nuke-it-all")
        assert result.returncode == 2
        assert "unrecognized selection verb" in _error(result)

    def test_missing_file_exits_two(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        result = _run("render-brief", "--report", str(missing), "--selection", "all")
        assert result.returncode == 2
        assert "report not found" in _error(result)

    def test_missing_recommendation_is_marked_and_warned(
        self, findings_lib: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        report = """\
## High

- **[correctness:high]** `src/x.ts:1` — no recommendation line.
  - location: module · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
"""
        lib = _typed(findings_lib)
        brief = lib.render_brief(lib.parse_findings_report(report), [1], report_path="report.md")
        assert "recommendation (locked): (none in report)" in brief
        assert "invariants:" not in brief
        err = capsys.readouterr().err
        assert "finding 1" in err
        assert "no locked recommendation" in err

    def test_unknown_id_raises(self, findings_lib: ModuleType) -> None:
        lib = _typed(findings_lib)
        findings = lib.parse_findings_report(SAMPLE_REPORT)
        with pytest.raises(ValueError, match="unknown finding ids"):
            _ = lib.render_brief(findings, [99], report_path="report.md")


class TestArgparseFailures:
    def test_missing_report_arg_exits_two(self) -> None:
        result = _run("render-table")
        assert result.returncode == 2
        assert "report" in _error(result).lower()

    def test_missing_selection_arg_exits_two(self, report_path: Path) -> None:
        result = _run("parse-selection", "--report", str(report_path))
        assert result.returncode == 2
        assert "selection" in _error(result).lower()

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
        assert "render-brief" in result.stdout
