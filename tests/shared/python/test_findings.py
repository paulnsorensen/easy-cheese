"""Tests for shared/scripts/findings.py — parse, group, select.

The fixture report mirrors the severity-grouped shape /age emits (see
skills/age/SKILL.md § Output). One finding per severity tier exercises
the full ladder.
"""

from __future__ import annotations

from types import ModuleType

import pytest

SAMPLE_REPORT = """\
status: ok
next: cure
artifact:
Reviewed the auth slice; 4 findings.

## Findings

## Blocker

- **[encapsulation:blocker]** `src/users/index.ts:42` — `index` re-exports `SqlPgUser` across slice boundary.
  - location: contract · fix-cost-now: sprawling · fix-cost-later: structural
  - recommendation: define `User` in the slice's public types, map at the boundary.

## High

- **[security:high]** `src/handler.ts:108` — Unvalidated path joined into fs.read.
  - location: contract · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: add allowlist check before joining.

## Medium

- **[complexity:medium]** `src/util.ts:200-240` — Function is 41 lines and 4 levels nested.
  - location: module · fix-cost-now: contained · fix-cost-later: spreading
  - recommendation: extract helpers.

## Low

- **[deslop:low]** `src/old.ts:55-60` — Unused export `_helper`.
  - location: class · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: remove the export.
"""


class TestParseFindingsReport:
    def test_parses_four_findings(self, findings: ModuleType) -> None:
        result = findings.parse_findings_report(SAMPLE_REPORT)
        assert len(result) == 4

    def test_assigns_sequential_ids(self, findings: ModuleType) -> None:
        result = findings.parse_findings_report(SAMPLE_REPORT)
        assert [f.id for f in result] == [1, 2, 3, 4]

    def test_severity_from_inline_tag(self, findings: ModuleType) -> None:
        result = findings.parse_findings_report(SAMPLE_REPORT)
        assert [f.severity for f in result] == ["blocker", "high", "medium", "low"]

    def test_severity_falls_back_to_heading(self, findings: ModuleType) -> None:
        # Bullet without an inline `:severity` tag inherits from `## High`.
        text = "## High\n- **[security]** `x:1` — Inherits from heading.\n"
        result = findings.parse_findings_report(text)
        assert result[0].severity == "high"

    def test_extracts_subfields(self, findings: ModuleType) -> None:
        result = findings.parse_findings_report(SAMPLE_REPORT)
        first = result[0]
        assert first.dimension == "encapsulation"
        assert first.location == "src/users/index.ts:42"
        assert first.location_tier == "contract"
        assert first.fix_cost_now == "sprawling"
        assert first.fix_cost_later == "structural"
        assert first.recommendation is not None
        assert "public types" in first.recommendation

    def test_bullet_without_subfields(self, findings: ModuleType) -> None:
        # Sub-fields are optional — the parser tolerates lean bullets.
        text = "## Medium\n- **[deslop:medium]** `y:1` — Bare bullet.\n"
        result = findings.parse_findings_report(text)
        assert result[0].location_tier is None
        assert result[0].fix_cost_now is None
        assert result[0].fix_cost_later is None
        assert result[0].recommendation is None

    def test_skips_bullets_before_first_heading(self, findings: ModuleType) -> None:
        text = (
            "- **[correctness]** `x:1` — Stray, no severity context.\n"
            "## High\n"
            "- **[security:high]** `y:1` — Real finding.\n"
        )
        result = findings.parse_findings_report(text)
        assert len(result) == 1
        assert result[0].dimension == "security"


class TestGroupBySeverity:
    def test_orders_blocker_first(self, findings: ModuleType) -> None:
        items = [
            findings.Finding(id=1, severity="low", dimension="x", location="a:1", summary="x."),
            findings.Finding(id=2, severity="blocker", dimension="y", location="b:1", summary="y."),
            findings.Finding(id=3, severity="medium", dimension="z", location="c:1", summary="z."),
            findings.Finding(id=4, severity="high", dimension="w", location="d:1", summary="w."),
        ]
        ordered = findings.group_by_severity(items)
        assert [f.id for f in ordered] == [2, 4, 3, 1]


class TestRenderSelectionTable:
    def test_includes_header_and_all_rows(self, findings: ModuleType) -> None:
        items = findings.parse_findings_report(SAMPLE_REPORT)
        table = findings.render_selection_table(items)
        assert "| # | severity" in table
        for finding in items:
            assert finding.location in table
        # Blocker row must precede the high row.
        blocker_index = table.index("src/users/index.ts:42")
        high_index = table.index("src/handler.ts:108")
        assert blocker_index < high_index


class TestParseSelection:
    @pytest.fixture
    def sample(self, findings: ModuleType) -> list:
        return findings.parse_findings_report(SAMPLE_REPORT)

    def test_specific_ids(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("1,3", sample) == [1, 3]

    def test_range(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("2-4", sample) == [2, 3, 4]

    def test_all_blocker(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("all-blocker", sample) == [1]

    def test_all_high_includes_blocker(self, findings: ModuleType, sample: list) -> None:
        # Path B: all-high is a floor at high, so it picks up blocker too.
        assert findings.parse_selection("all-high", sample) == [1, 2]

    def test_cheap_picks_contained(self, findings: ModuleType, sample: list) -> None:
        # Findings 2, 3, 4 all have fix-cost-now: contained.
        assert findings.parse_selection("cheap", sample) == [2, 3, 4]

    def test_cheap_empty_when_no_subfields(self, findings: ModuleType) -> None:
        text = "## High\n- **[security:high]** `x:1` — Bullet without sub-fields.\n"
        items = findings.parse_findings_report(text)
        # No findings have fix-cost-now → cheap resolves empty per selection.md.
        assert findings.parse_selection("cheap", items) == []

    def test_all(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("all", sample) == [1, 2, 3, 4]

    def test_none_returns_empty(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("none", sample) == []
        assert findings.parse_selection("", sample) == []

    def test_skip(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("skip 2", sample) == [1, 3, 4]

    def test_composition_union(self, findings: ModuleType, sample: list) -> None:
        # all-blocker ∪ cheap = {1} ∪ {2, 3, 4} = {1, 2, 3, 4}.
        assert findings.parse_selection("all-blocker, cheap", sample) == [1, 2, 3, 4]

    def test_composition_with_skip(self, findings: ModuleType, sample: list) -> None:
        # all-blocker ∪ cheap, skip 4 = {1, 2, 3, 4} − {4}.
        assert findings.parse_selection("all-blocker, cheap, skip 4", sample) == [1, 2, 3]

    def test_composition_with_explicit_id(
        self, findings: ModuleType, sample: list
    ) -> None:
        # all-high (which now includes blocker) ∪ {3} = {1, 2, 3}.
        assert findings.parse_selection("all-high, 3", sample) == [1, 2, 3]

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

    def test_all_mutually_exclusive(self, findings: ModuleType, sample: list) -> None:
        with pytest.raises(findings.SelectionError, match="mutually exclusive"):
            findings.parse_selection("all, 3", sample)

    def test_case_insensitive(self, findings: ModuleType, sample: list) -> None:
        assert findings.parse_selection("ALL-HIGH", sample) == [1, 2]
        assert findings.parse_selection("SKIP 2", sample) == [1, 3, 4]
