"""Render a closed-subset Markdown report artifact into one self-contained,
offline, byte-deterministic themed HTML document (stdlib only).

Public API:
    render(markdown, *, title) -> str  -- a complete HTML document string.

The Markdown converter is a hand-rolled two-pass line scanner for a CLOSED
subset: ATX headings, bold/italic/inline-code, links, unordered/ordered lists
(one nesting level via a fixed 2-space indent unit), fenced code blocks, GFM
pipe tables, horizontal rules, blockquotes, and paragraphs. It is deliberately
NOT a CommonMark implementation.

Determinism contract: output depends only on the input and is stable across
runs -- no timestamps, no randomness, no environment reads. CI diffs committed
bundles, so identical input MUST yield identical bytes.
"""
from __future__ import annotations

import html
import re

# Theme inlined verbatim (light + dark via prefers-color-scheme). A fixed string
# we own, so byte-output stability is guaranteed -- no CDN, no scan/JIT step.
_CSS = """:root {
  --bg: #ffffff; --fg: #1a1a1a; --muted: #6b7280;
  --border: #e5e7eb; --code-bg: #f3f4f6; --link: #2563eb;
  --accent: #f9fafb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1115; --fg: #e5e7eb; --muted: #9ca3af;
    --border: #2a2e37; --code-bg: #1a1d24; --link: #60a5fa;
    --accent: #161a21;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0 auto; max-width: 860px; padding: 2.5rem 1.5rem;
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg); color: var(--fg);
}
h1, h2, h3 { line-height: 1.25; margin: 1.6em 0 0.6em; }
h1 { font-size: 1.75rem; border-bottom: 1px solid var(--border); padding-bottom: .3em; }
h2 { font-size: 1.35rem; }
h3 { font-size: 1.1rem; color: var(--muted); }
p, li { color: var(--fg); }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
blockquote {
  margin: 1em 0; padding: .2em 1em; border-left: 3px solid var(--border);
  color: var(--muted); background: var(--accent);
}
hr { border: none; border-top: 1px solid var(--border); margin: 2em 0; }
code {
  font: 0.9em/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: var(--code-bg); padding: .15em .4em; border-radius: 4px;
}
pre {
  background: var(--code-bg); padding: 1em; border-radius: 6px;
  overflow-x: auto; border: 1px solid var(--border);
}
pre code { background: none; padding: 0; }
table { width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 0.95em; }
th, td { border: 1px solid var(--border); padding: .5em .75em; text-align: left; }
th { background: var(--accent); font-weight: 600; }
tr:nth-child(even) td { background: color-mix(in srgb, var(--accent) 50%, transparent); }"""

_MERMAID_SCRIPTS = (
    '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>\n'
    "<script>mermaid.initialize({ startOnLoad: true });</script>\n"
)

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.+)$")
_HR = re.compile(r"^-{3,}$")
_SEP_CELL = re.compile(r"^\s*:?-+:?\s*$")
_CODE_SPAN = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_STAR = re.compile(r"\*([^*]+)\*")
_ITALIC_UNDER = re.compile(r"_([^_]+)_")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def render(markdown: str, *, title: str) -> str:
    """Convert a closed-subset Markdown report into a complete HTML document."""
    blocks, has_mermaid = _parse(markdown.split("\n"))
    body = "\n".join(blocks)
    scripts = _MERMAID_SCRIPTS if has_mermaid else ""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>\n{_CSS}\n</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        f"{scripts}"
        "</body>\n"
        "</html>\n"
    )


def _parse(lines: list[str]) -> tuple[list[str], bool]:
    """Pass 1: split into blocks (blank-line-delimited) with fence-state tracking."""
    out: list[str] = []
    has_mermaid = False
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        if raw.lstrip().startswith("```"):
            lang = raw.lstrip()[3:].strip()
            body: list[str] = []
            i += 1
            while i < n and not lines[i].lstrip().startswith("```"):
                body.append(lines[i])
                i += 1
            if i < n:
                i += 1  # consume the closing fence
            code = html.escape("\n".join(body))
            if lang == "mermaid":
                has_mermaid = True
                out.append(f'<pre class="mermaid">{code}</pre>')
            else:
                out.append(f"<pre><code>{code}</code></pre>")
            continue
        if raw.strip() == "":
            i += 1
            continue
        chunk: list[str] = []
        while i < n and lines[i].strip() != "" and not lines[i].lstrip().startswith("```"):
            chunk.append(lines[i])
            i += 1
        out.extend(_render_chunk(chunk))
    return out, has_mermaid


def _render_chunk(lines: list[str]) -> list[str]:
    """Dispatch the lines of one blank-delimited chunk to block handlers."""
    out: list[str] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(f"<p>{_inline(chr(10).join(para))}</p>")
            para.clear()

    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        heading = _HEADING.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            i += 1
            continue
        if _HR.match(line.strip()):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if "|" in line and i + 1 < n and _is_table_sep(lines[i + 1]):
            flush()
            j = i + 2
            rows = [line, lines[i + 1]]
            while j < n and "|" in lines[j]:
                rows.append(lines[j])
                j += 1
            out.append(_render_table(rows))
            i = j
            continue
        if _LIST_ITEM.match(line):
            flush()
            j = i
            items = []
            while j < n and _LIST_ITEM.match(lines[j]):
                items.append(lines[j])
                j += 1
            out.append(_render_list(items))
            i = j
            continue
        if line.lstrip().startswith(">"):
            flush()
            j = i
            quoted = []
            while j < n and lines[j].lstrip().startswith(">"):
                content = lines[j].lstrip()[1:]
                if content.startswith(" "):
                    content = content[1:]
                quoted.append(content)
                j += 1
            out.append(f"<blockquote>{_inline(chr(10).join(quoted))}</blockquote>")
            i = j
            continue
        para.append(line)
        i += 1
    flush()
    return out


def _render_list(items: list[str]) -> str:
    """One nesting level via a fixed 2-space indent unit (not CommonMark width-matching)."""
    top_ordered = _LIST_ITEM.match(items[0]).group(2).endswith(".")
    top_tag = "ol" if top_ordered else "ul"
    parts = [f"<{top_tag}>"]
    li_open = False
    nested_tag: str | None = None
    for item in items:
        m = _LIST_ITEM.match(item)
        indent = len(m.group(1))
        ordered = m.group(2).endswith(".")
        text = _inline(m.group(3))
        if indent >= 2:
            if nested_tag is None:
                nested_tag = "ol" if ordered else "ul"
                parts.append(f"<{nested_tag}>")
            parts.append(f"<li>{text}</li>")
        else:
            if nested_tag is not None:
                parts.append(f"</{nested_tag}>")
                nested_tag = None
            if li_open:
                parts.append("</li>")
            parts.append(f"<li>{text}")  # left open in case a nested list follows
            li_open = True
    if nested_tag is not None:
        parts.append(f"</{nested_tag}>")
    if li_open:
        parts.append("</li>")
    parts.append(f"</{top_tag}>")
    return "".join(parts)


def _split_cells(row: str) -> list[str]:
    """Split a table row on UNESCAPED pipes; treat backslash-pipe as a literal pipe."""
    cells: list[str] = []
    cur: list[str] = []
    k, n = 0, len(row)
    while k < n:
        ch = row[k]
        if ch == "\\" and k + 1 < n and row[k + 1] == "|":
            cur.append("|")
            k += 2
            continue
        if ch == "|":
            cells.append("".join(cur))
            cur = []
            k += 1
            continue
        cur.append(ch)
        k += 1
    cells.append("".join(cur))
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return cells


def _is_table_sep(line: str) -> bool:
    if "-" not in line:
        return False
    cells = _split_cells(line)
    return bool(cells) and all(_SEP_CELL.match(c) for c in cells)


def _render_table(rows: list[str]) -> str:
    header = _split_cells(rows[0])
    parts = ["<table>", "<thead>", "<tr>"]
    parts += [f"<th>{_inline(c.strip())}</th>" for c in header]
    parts += ["</tr>", "</thead>", "<tbody>"]
    for row in rows[2:]:
        cells = _split_cells(row)
        parts.append("<tr>")
        parts += [f"<td>{_inline(c.strip())}</td>" for c in cells]
        parts.append("</tr>")
    parts += ["</tbody>", "</table>"]
    return "".join(parts)


def _inline(text: str) -> str:
    """Pass 2: inline spans. Code spans first (opaque), then bold, italic, links.

    Code content is escaped once and never re-processed, so `` `**x**` `` inside a
    code span stays literal instead of turning into <strong>.
    """
    parts = []
    for idx, seg in enumerate(_CODE_SPAN.split(text)):
        if idx % 2 == 1:
            parts.append(f"<code>{html.escape(seg)}</code>")
        else:
            parts.append(_inline_spans(seg))
    return "".join(parts)


def _inline_spans(seg: str) -> str:
    s = html.escape(seg)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _ITALIC_STAR.sub(r"<em>\1</em>", s)
    s = _ITALIC_UNDER.sub(r"<em>\1</em>", s)
    s = _LINK.sub(r'<a href="\2">\1</a>', s)
    return s
