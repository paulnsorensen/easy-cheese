"""Tests for src/age/html-report.py — deterministic HTML rendering of /age reports.

These are black-box tests for the future HTML report generator: the script should
turn a markdown age report into a styled standalone HTML file, preserving the
findings contract without depending on repo-local state.
"""

import os
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
HTML_REPORT = REPO_ROOT / "src" / "age" / "html-report.py"

REPORT_WITH_FINDINGS = """\
status: ok
next: cure
artifact: .cheese/age/demo.md
HTML report smoke test

## Medium
- **[complexity:medium]** `src/medium.ts:3` — Medium summary with <em>markup</em> & ampersand.
  second line stays visible.
  - location: module · fix-cost-now: moderate · fix-cost-later: spreading
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
            cast(list[str], self._stack[-1]["text_parts"]).append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        node = self._stack.pop()
        text_parts = cast(list[str], node.pop("text_parts"))
        node["text"] = "".join(text_parts).strip()
        if self._stack:
            cast(list[str], self._stack[-1]["text_parts"]).append(cast(str, node["text"]))


def _run_html_report(tmp_path: Path, report_body: str, slug: str = "demo") -> tuple[Path, str]:
    report = tmp_path / f"{slug}.md"
    report.write_text(report_body, encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    env = os.environ.copy()
    pythonpath = [str(REPO_ROOT / "shared" / "scripts")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
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
        env=env,
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
            str(node["text"]).lower()
            for node in parser.nodes
            if node["tag"] in {"h1", "h2", "h3", "h4", "h5", "h6"}
            and str(node.get("text")).lower() in {"blocker", "high", "medium", "low"}
        ]
        assert severity_headings == ["blocker", "high", "medium", "low"]

        for severity in ("blocker", "high", "medium", "low"):
            badge_nodes = [
                node
                for node in parser.nodes
                if str(node.get("text")).lower() == severity and node["attrs"].get("class")
            ]
            assert badge_nodes, f"{severity} label was not rendered with badge-like markup/classes"

        assert "whitespace-pre-wrap" in html
        assert "Medium summary with &lt;em&gt;markup&lt;/em&gt; &amp; ampersand." in html
        assert "second line stays visible." in html
        assert "First line with &lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "second line with &amp; and &lt;angle&gt;." in html
        assert "<script>" not in html
        assert "<strong>unsafe</strong>" not in html
        assert html_path.name == "age-demo.html"

    def test_empty_report_gets_friendly_empty_state_and_no_mermaid_pie(self, tmp_path: Path) -> None:
        _, html = _run_html_report(tmp_path, REPORT_WITHOUT_FINDINGS, slug="empty")

        assert "No findings" in html
        assert "class=\"mermaid\"" not in html
        assert "pie title" not in html
        assert "Blocker" not in html
        assert "High" not in html
        assert "Medium" not in html
        assert "Low" not in html
