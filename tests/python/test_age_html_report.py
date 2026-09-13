"""Tests for age_html_report.py -- deterministic HTML rendering of a ReviewResult.

The HTML generator now reads a canonical ReviewResult JSON document (the payload
/age publishes to /cure) and renders each finding's summary verbatim, grouped by
severity. It never re-parses a Markdown report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import override

REPO_ROOT = Path(__file__).resolve().parents[2]
HTML_REPORT = REPO_ROOT / "src" / "easy_cheese" / "skills" / "age" / "age_html_report.py"

REVIEW_RESULT_WITH_FINDINGS = json.dumps(
    {
        "review_id": "demo",
        "disposition": "findings",
        "findings": [
            {
                "finding_id": "demo/finding/1",
                "severity": "medium",
                "summary": "Medium summary with <em>markup</em> & ampersand.\nsecond line stays visible.",
                "location": {"path": "src/medium.ts", "start_line": 3, "end_line": 3},
            },
            {
                "finding_id": "demo/finding/2",
                "severity": "low",
                "summary": "Low summary.",
                "location": {"path": "src/low.ts", "start_line": 4, "end_line": 4},
            },
            {
                "finding_id": "demo/finding/3",
                "severity": "high",
                "summary": "High summary with <strong>unsafe</strong> HTML.",
                "location": {"path": "src/high.ts", "start_line": 2, "end_line": 2},
            },
            {
                "finding_id": "demo/finding/4",
                "severity": "critical",
                "summary": "Critical summary with <script>alert(1)</script> and <angle>.",
                "location": {"path": "src/crit.ts", "start_line": 1, "end_line": 1},
            },
        ],
        "coverage": [{"target": "security", "disposition": "covered"}],
    }
)

REVIEW_RESULT_WITHOUT_FINDINGS = json.dumps(
    {"review_id": "empty", "disposition": "clean", "findings": [], "coverage": []}
)


@dataclass
class _Node:
    """An HTML node in document order, collected for structural assertions."""

    tag: str
    attrs: dict[str, str | None]
    text: str = ""
    text_parts: list[str] = field(default_factory=list)


class _HTMLNodes(HTMLParser):
    """Collect HTML nodes in document order for structural assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[_Node] = []
        self._stack: list[_Node] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag=tag, attrs=dict(attrs))
        self.nodes.append(node)
        self._stack.append(node)

    @override
    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1].text_parts.append(data)

    @override
    def handle_endtag(self, tag: str) -> None:
        del tag
        if not self._stack:
            return
        node = self._stack.pop()
        node.text = "".join(node.text_parts).strip()
        if self._stack:
            self._stack[-1].text_parts.append(node.text)


def _run_html_report(tmp_path: Path, review_result_json: str, slug: str = "demo") -> tuple[Path, str]:
    report = tmp_path / f"{slug}.json"
    _ = report.write_text(review_result_json, encoding="utf-8")
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
        html_path, html = _run_html_report(tmp_path, REVIEW_RESULT_WITH_FINDINGS)
        parser = _HTMLNodes()
        parser.feed(html)

        severity_headings = [
            node.text
            for node in parser.nodes
            if node.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}
            and node.text in {"Critical", "High", "Medium", "Low"}
        ]
        assert severity_headings == ["Critical", "High", "Medium", "Low"]

        for severity in ("Critical", "High", "Medium", "Low"):
            badge_nodes = [
                node
                for node in parser.nodes
                if node.text == severity and node.attrs.get("class")
            ]
            assert badge_nodes, f"{severity} label was not rendered with badge-like markup/classes"

        assert "whitespace-pre-wrap" in html
        assert "&lt;strong&gt;unsafe&lt;/strong&gt;" in html
        assert "&lt;em&gt;markup&lt;/em&gt;" in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "&lt;angle&gt;" in html
        assert "second line stays visible." in html
        assert "<script>" not in html
        assert "<strong>unsafe</strong>" not in html
        assert html_path.name == "age-demo.html"

    def test_empty_report_gets_friendly_empty_state_and_no_mermaid_pie(self, tmp_path: Path) -> None:
        _, html = _run_html_report(tmp_path, REVIEW_RESULT_WITHOUT_FINDINGS, slug="empty")

        assert "No findings" in html
        assert "class=\"mermaid\"" not in html
        assert "pie title" not in html
        assert "Critical" not in html
        assert "Blocker" not in html
        assert "High" not in html
        assert "Medium" not in html
        assert "Low" not in html

    def test_malformed_review_result_exits_nonzero(self, tmp_path: Path) -> None:
        report = tmp_path / "bad.json"
        _ = report.write_text("not json", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                str(HTML_REPORT),
                "--report",
                str(report),
                "--slug",
                "bad",
                "--out-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "ERROR:" in result.stderr