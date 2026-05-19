"""Tests for shared/scripts/findings.py — parse, group, select."""

from __future__ import annotations

from types import ModuleType

import pytest

SAMPLE_REPORT = """\
status: ok
next: cure
artifact:
Reviewed the auth slice; 4 findings.

## Findings

### High

- **[correctness]** `src/auth.ts:42-50` — Token check uses `==` on bytes. Switch to constant-time compare.
- **[security]** `src/handler.ts:108` — Unvalidated path joined into fs.read. Add allowlist check.

### Medium

- **[complexity]** `src/util.ts:200-240` — Function is 41 lines and 4 levels nested. Extract helpers.
- **[deslop]** `src/old.ts:55-60` — Unused export `_helper`. Remove the export.
"""


class TestParseFindingsReport:
    def test_parses_four_findings(self, findings: ModuleType) -> None:
        result = findings.parse_findings_report(SAMPLE_REPORT)
        assert len(result) == 4

    def test_assigns_sequential_ids(self, findings: ModuleType) -> None:
        result = findings.parse_findings_report(SAMPLE_REPORT)
        assert [f.id for f in result] == [1, 2, 3, 4]

    def test_inherits_stake_from_section(self, findings: ModuleType) -> None:
        result = findings.parse_findings_report(SAMPLE_REPORT)
        assert [f.stake for f in result] == ["high", "high", "medium", "medium"]

    def test_extracts_dimension_location_summary(
        self, findings: ModuleType
    ) -> None:
        result = findings.parse_findings_report(SAMPLE_REPORT)
        assert result[0].dimension == "correctness"
        assert result[0].location == "src/auth.ts:42-50"
        assert "Token check" in result[0].summary
        assert result[0].recommendation is not None
        assert "constant-time" in result[0].recommendation

    def test_skips_bullets_before_first_stake_heading(
        self, findings: ModuleType
    ) -> None:
        text = (
            "- **[correctness]** `x:1` — Stray bullet.\n"
            "### High\n"
            "- **[security]** `y:1` — Real finding. Fix it.\n"
        )
        result = findings.parse_findings_report(text)
        assert len(result) == 1
        assert result[0].dimension == "security"


class TestGroupByStake:
    def test_high_before_medium(self, findings: ModuleType) -> None:
        items = [
            findings.Finding(id=1, stake="medium", dimension="x", location="a:1", summary="x."),
            findings.Finding(id=2, stake="high", dimension="y", location="b:1", summary="y."),
        ]
        ordered = findings.group_by_stake(items)
        assert [f.id for f in ordered] == [2, 1]


class TestRenderSelectionTable:
    def test_includes_header_and_all_rows(self, findings: ModuleType) -> None:
        items = findings.parse_findings_report(SAMPLE_REPORT)
        table = findings.render_selection_table(items)
        assert "| # | stake" in table
        for finding in items:
            assert finding.location in table
        # High-stake rows must appear before any medium-stake row.
        high_index = table.index("src/auth.ts:42-50")
        medium_index = table.index("src/util.ts:200-240")
        assert high_index < medium_index


class TestParseSelection:
    @pytest.fixture
    def sample(self, findings: ModuleType) -> list:
        return findings.parse_findings_report(SAMPLE_REPORT)

    def test_specific_ids(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("1,3", sample) == [1, 3]

    def test_range(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("2-4", sample) == [2, 3, 4]

    def test_all_high(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("all-high", sample) == [1, 2]

    def test_all(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("all", sample) == [1, 2, 3, 4]

    def test_none_returns_empty(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("none", sample) == []
        # Empty string also means no selection (matches cure default).
        assert findings.parse_selection("", sample) == []

    def test_skip(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("skip 2", sample) == [1, 3, 4]

    def test_unknown_id_raises(self, findings: ModuleType, sample: list) -> None:
        with pytest.raises(findings.SelectionError, match="unknown finding ids"):
            findings.parse_selection("1,9", sample)

    def test_unknown_verb_raises(self, findings: ModuleType, sample: list) -> None:
        with pytest.raises(findings.SelectionError, match="unrecognized"):
            findings.parse_selection("nuke-it-all", sample)

    def test_skip_unknown_raises(self, findings: ModuleType, sample: list) -> None:
        with pytest.raises(findings.SelectionError, match="skip target"):
            findings.parse_selection("skip 99", sample)

    def test_reversed_range_raises(self, findings: ModuleType, sample: list) -> None:
        with pytest.raises(findings.SelectionError, match="reversed"):
            findings.parse_selection("4-2", sample)

    def test_case_insensitive(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("ALL-HIGH", sample) == [1, 2]
        assert findings.parse_selection("SKIP 2", sample) == [1, 3, 4]
