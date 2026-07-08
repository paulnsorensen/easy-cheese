"""Tests for src/age/age-html-report.py — deterministic HTML rendering of /age reports.

These are black-box tests for the future HTML report generator: the script should
turn a markdown age report into a styled standalone HTML file, preserving the
findings contract without depending on repo-local state.
"""

from __future__ import annotations

import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HTML_REPORT = REPO_ROOT / "src" / "age" / "age-html-report.py"

REPORT_WITH_FINDINGS = """\
status: ok
next: cure
artifact: .cheese/age/demo.md
HTML report smoke test

## Medium
- **[complexity:medium]** `src/medium.ts:3` — Medium summary with <em>markup</em> & ampersand.
  second line stays visible.
  - location: module · fix-cost-now: moderate · fix-cost-later: spreading · confidence: speculating
  - recommendation: First line with <script>alert(1)</script>
    second line with & and <angle>.

## Low
- **[deslop:low]** `src/low.ts:4` — Low summary.
  - location: class · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: Remove the helper.

## High
- **[security:high]** `src/high.ts:2` — High summary with <strong>unsafe</strong> HTML.
  - location: contract · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: Tighten the boundary.

## Blocker
- **[encapsulation:blocker]** `src/blocker.ts:1` — Blocker summary.
  - location: contract · fix-cost-now: sprawling · fix-cost-later: structural
  - recommendation: Extract the slice boundary.
"""

REPORT_WITHOUT_FINDINGS = """\
status: ok
next: done
artifact: .cheese/age/empty.md
HTML report smoke test

## Findings

"""

# A real /age report always ends with `## Confidence` and `## Next step`
# (skills/age/SKILL.md § Output). Neither is a severity heading, so they must
# terminate the last finding rather than being swallowed into its body.
REPORT_WITH_TRAILING_SECTIONS = """\
status: ok
next: cure
artifact: .cheese/age/tail.md
Trailing-section guard

## High
- **[security:high]** `src/high.ts:2` — High summary.
  - location: contract · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: Tighten the boundary.

## Confidence
certain — verified by reading the diff.

## Next step
Auto-fixing the recommended set via /cure.
"""


class _HTMLNodes(HTMLParser):
    """Collect HTML nodes in document order for structural assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[dict[str, object]] = []
        self._stack: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = {"tag": tag, "attrs": dict(attrs), "text_parts": []}
        self.nodes.append(node)
        self._stack.append(node)

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1]["text_parts"].append(data)  # type: ignore[index]

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        node = self._stack.pop()
        node["text"] = "".join(node.pop("text_parts")).strip()  # type: ignore[arg-type]
        if self._stack:
            self._stack[-1]["text_parts"].append(node["text"])  # type: ignore[index]


def _run_html_report(tmp_path: Path, report_body: str, slug: str = "demo") -> tuple[Path, str]:
    report = tmp_path / f"{slug}.md"
    report.write_text(report_body, encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(HTML_REPORT),
            "--report",
            str(report),
            "--slug",
            slug,
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    html_path = out_dir / f"age-{slug}.html"
    assert result.stdout.strip() == str(html_path)
    assert html_path.exists(), f"missing HTML output: {html_path}"
    return html_path, html_path.read_text(encoding="utf-8")


class TestAgeHtmlReport:
    def test_groups_findings_by_severity_and_uses_badge_markup(self, tmp_path: Path) -> None:
        html_path, html = _run_html_report(tmp_path, REPORT_WITH_FINDINGS)
        parser = _HTMLNodes()
        parser.feed(html)

        severity_headings = [
            node["text"]
            for node in parser.nodes
            if node["tag"] in {"h1", "h2", "h3", "h4", "h5", "h6"}
            and node.get("text") in {"Blocker", "High", "Medium", "Low"}
        ]
        assert severity_headings == ["Blocker", "High", "Medium", "Low"]

        for severity in ("Blocker", "High", "Medium", "Low"):
            badge_nodes = [
                node
                for node in parser.nodes
                if node.get("text") == severity and node["attrs"].get("class")
            ]
            assert badge_nodes, f"{severity} label was not rendered with badge-like markup/classes"

        assert "whitespace-pre-wrap" in html
        assert "&lt;strong&gt;unsafe&lt;/strong&gt;" in html
        assert "&lt;em&gt;markup&lt;/em&gt;" in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "confidence: speculating" in html
        assert "&lt;angle&gt;" in html
        assert "<script>" not in html
        assert "<strong>unsafe</strong>" not in html
        assert html_path.name == "age-demo.html"

    def test_trailing_sections_do_not_leak_into_finding_body(self, tmp_path: Path) -> None:
        _, html = _run_html_report(tmp_path, REPORT_WITH_TRAILING_SECTIONS, slug="tail")
        parser = _HTMLNodes()
        parser.feed(html)

        finding_bodies = [
            node["text"]
            for node in parser.nodes
            if node["tag"] == "pre" and "whitespace-pre-wrap" in str(node["attrs"].get("class", ""))
        ]
        assert finding_bodies, "no finding <pre> rendered"
        for body in finding_bodies:
            assert "## Confidence" not in body
            assert "## Next step" not in body
            assert "Auto-fixing the recommended set" not in body

    def test_empty_report_gets_friendly_empty_state_and_no_mermaid_pie(self, tmp_path: Path) -> None:
        _, html = _run_html_report(tmp_path, REPORT_WITHOUT_FINDINGS, slug="empty")

        assert "No findings" in html
        assert "class=\"mermaid\"" not in html
        assert "pie title" not in html
        assert "Blocker" not in html
        assert "High" not in html
        assert "Medium" not in html
        assert "Low" not in html
