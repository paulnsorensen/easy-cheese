"""Tests for shared/scripts/html_report.py -- the stdlib-only Markdown->HTML renderer.

Assertions encode WHY each behaviour matters: the inline-order gotcha keeps a
code span opaque so bold markup inside it is not mangled; html-escaping guards
against stray markup from report prose leaking into the document; determinism
matters because CI diffs committed HTML bundles, so a non-deterministic renderer
would fail CI on every unrelated rebuild.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hr() -> ModuleType:
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    return _load("html_report", SHARED_SCRIPTS / "html_report.py")


class TestBlockTypes:
    def test_atx_heading_levels(self, hr: ModuleType) -> None:
        out = hr.render("# One\n\n### Three", title="t")
        assert "<h1>One</h1>" in out
        assert "<h3>Three</h3>" in out

    def test_hash_without_space_is_not_a_heading(self, hr: ModuleType) -> None:
        # ATX headings require '#' + space; '#foo' is prose, not a heading.
        out = hr.render("#foo", title="t")
        assert "<h1>" not in out
        assert "<p>#foo</p>" in out

    def test_paragraph(self, hr: ModuleType) -> None:
        assert "<p>hello world</p>" in hr.render("hello world", title="t")

    def test_unordered_list(self, hr: ModuleType) -> None:
        out = hr.render("- alpha\n- beta", title="t")
        assert "<ul><li>alpha</li><li>beta</li></ul>" in out

    def test_ordered_list(self, hr: ModuleType) -> None:
        out = hr.render("1. first\n2. second", title="t")
        assert "<ol><li>first</li><li>second</li></ol>" in out

    def test_nested_list_one_level(self, hr: ModuleType) -> None:
        # A fixed 2-space indent unit nests the sub-item inside its parent <li>.
        out = hr.render("- top\n  - child", title="t")
        assert "<ul><li>top<ul><li>child</li></ul></li></ul>" in out

    def test_blockquote(self, hr: ModuleType) -> None:
        assert "<blockquote>quoted</blockquote>" in hr.render("> quoted", title="t")

    def test_horizontal_rule(self, hr: ModuleType) -> None:
        assert "<hr>" in hr.render("---", title="t")

    def test_fenced_code_block(self, hr: ModuleType) -> None:
        out = hr.render("```\nx = 1\n```", title="t")
        assert "<pre><code>x = 1</code></pre>" in out

    def test_fenced_code_content_is_not_block_processed(self, hr: ModuleType) -> None:
        # A '# ' line inside a fence is literal text, never an <h1>.
        out = hr.render("```\n# not a heading\n- not a list\n```", title="t")
        assert "<pre><code># not a heading\n- not a list</code></pre>" in out
        assert "<h1>" not in out
        assert "<ul>" not in out

    def test_pipe_table(self, hr: ModuleType) -> None:
        md = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        out = hr.render(md, title="t")
        assert "<table><thead><tr><th>A</th><th>B</th></tr></thead>" in out
        assert "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>" in out


class TestInline:
    def test_bold_italic_link_code(self, hr: ModuleType) -> None:
        out = hr.render("**b** *i* _j_ [t](http://x) `c`", title="t")
        assert "<strong>b</strong>" in out
        assert "<em>i</em>" in out
        assert "<em>j</em>" in out
        assert '<a href="http://x">t</a>' in out
        assert "<code>c</code>" in out

    def test_code_span_first_keeps_bold_literal(self, hr: ModuleType) -> None:
        # The inline-order gotcha: bold markup inside a code span must stay literal,
        # not become <strong> -- code spans are resolved before bold.
        out = hr.render("`**x**`", title="t")
        assert "<code>**x**</code>" in out
        assert "<strong>" not in out


class TestEscaping:
    def test_prose_angle_and_amp_escaped(self, hr: ModuleType) -> None:
        out = hr.render("a < b & c > d", title="t")
        assert "a &lt; b &amp; c &gt; d" in out
        # Raw, unescaped angle brackets from source must never pass through.
        assert "a < b" not in out

    def test_code_span_content_escaped(self, hr: ModuleType) -> None:
        out = hr.render("`<script>&`", title="t")
        assert "<code>&lt;script&gt;&amp;</code>" in out

    def test_emitted_tags_not_escaped(self, hr: ModuleType) -> None:
        # We escape source text, never the tags we emit ourselves.
        assert "<h1>Title</h1>" in hr.render("# Title", title="t")


class TestTablePipes:
    def test_escaped_pipe_is_literal_cell_content(self, hr: ModuleType) -> None:
        # '\|' is a literal pipe inside a cell, not a column delimiter.
        md = "| A | B |\n| --- | --- |\n| x \\| y | z |"
        out = hr.render(md, title="t")
        assert "<td>x | y</td>" in out
        assert "<td>z</td>" in out


class TestMermaid:
    def test_mermaid_fence_emits_pre_and_one_script(self, hr: ModuleType) -> None:
        out = hr.render("```mermaid\ngraph TD; A-->B;\n```", title="t")
        assert '<pre class="mermaid">graph TD; A--&gt;B;</pre>' in out
        assert out.count('<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>') == 1
        assert out.count("mermaid.initialize") == 1

    def test_no_mermaid_fence_emits_no_script(self, hr: ModuleType) -> None:
        # A report with no mermaid stays fully offline: zero script tags.
        out = hr.render("# heading\n\n```\ncode\n```", title="t")
        assert "<script" not in out
        assert "cdn.jsdelivr" not in out


class TestDeterminism:
    def test_same_input_yields_identical_bytes(self, hr: ModuleType) -> None:
        # Determinism matters because CI diffs committed HTML bundles; a
        # non-deterministic renderer would fail CI on every unrelated rebuild.
        md = "# Report\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```mermaid\ngraph TD;\n```\n"
        first = hr.render(md, title="Report").encode("utf-8")
        second = hr.render(md, title="Report").encode("utf-8")
        assert first == second


class TestDocumentShape:
    def test_complete_self_contained_document(self, hr: ModuleType) -> None:
        out = hr.render("# Hi", title="My <Report>")
        assert out.startswith("<!DOCTYPE html>\n")
        assert out.rstrip().endswith("</html>")
        assert "<style>" in out and "prefers-color-scheme" in out
        # Title is escaped in the document head.
        assert "<title>My &lt;Report&gt;</title>" in out
