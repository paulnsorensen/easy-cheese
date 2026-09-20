"""Render a closed-subset Markdown report artifact into one self-contained,
offline, byte-deterministic themed HTML document (stdlib only).

Public API:
    render(markdown, *, title) -> str  -- a complete HTML document string.

The Markdown converter is a hand-rolled two-pass line scanner for a CLOSED
subset: ATX headings, bold/italic/inline-code, links, unordered/ordered lists
(one nesting level via a fixed 2-space indent unit), fenced code blocks, GFM
pipe tables, horizontal rules, blockquotes, and paragraphs. It is deliberately
NOT a CommonMark implementation.

Outside that subset -- setext headings, reference links, images, strikethrough,
definition lists, raw HTML -- input degrades to escaped literal text; nothing
raises. Raw HTML is ALWAYS escaped, never passed through, and link URLs are
restricted to the http/https/mailto allowlist, so model-authored report prose
cannot inject markup or a `javascript:` href into the document.

Why not a Markdown library (decided in #517, recorded in
`docs/adr/html-report-renderer-001.md`): the input is report artifacts our own
skills author against the subset above, not arbitrary Markdown, so CommonMark
fidelity buys nothing today -- while a dependency lands in every `.pyz` that
stages this module and puts committed-bundle bytes at the mercy of upstream
output changes. Revisit if externally authored Markdown ever reaches `render()`.
`TestClosedSubsetContract` in tests/shared/python/test_html_report.py pins the
boundary described above.

Determinism contract: output depends only on the input and is stable across
runs -- no timestamps, no randomness, no environment reads. CI diffs committed
bundles, so identical input MUST yield identical bytes.
"""
from __future__ import annotations

import html
import re

# Theme inlined verbatim (light + dark via prefers-color-scheme). A fixed string
# we own, so byte-output stability is guaranteed -- no CDN, no scan/JIT step.
# Token names and values follow the Easy Cheese Design System (tokens.json);
# frontend/mold-review/src/design/tokens.css derives the same values.
_CSS = """:root {
  --field: #f8f7f3; --field-sunk: #f0eee6; --panel: #fdfcfa;
  --text: #191512; --text-dim: #615953; --hairline: #140f0b24;
  --accent: #965300; --accent-low: #f9e4d0; --accent-high: #7a4c19;
  --sev-blocker: #b91c1c; --sev-high: #c2410c; --sev-medium: #a16207;
  --sev-low: #4b5563; --on-sev: #ffffff;
  --font-serif: Fraunces, Georgia, serif;
  --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --field: #140f0b; --field-sunk: #110c08; --panel: #1b1613;
    --text: #ecdfd3; --text-dim: #8c8177; --hairline: #ecdfd321;
    --accent: #dd8c33; --accent-low: #3a230c; --accent-high: #f8bd86;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0 auto; max-width: 860px; padding: 2.5rem 1.5rem;
  font: 16px/1.6 var(--font-sans);
  background: var(--field); color: var(--text);
}
h1, h2, h3 { line-height: 1.25; margin: 1.6em 0 0.6em; }
h1 {
  font: 560 2.625rem/1.1 var(--font-serif); letter-spacing: -0.035em;
  border-bottom: 1px solid var(--hairline); padding-bottom: .3em;
}
h2 { font-size: 1.375rem; letter-spacing: -0.025em; }
h3 { font-size: 1.0625rem; color: var(--text-dim); }
p, li { color: var(--text); }
a { color: var(--accent); text-underline-offset: 3px; }
a > code { background: var(--accent-low); color: var(--accent-high); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
::selection { background: var(--accent); color: var(--field); }
blockquote {
  margin: 1em 0; padding: .2em 1em; border: 1px solid var(--hairline);
  border-radius: 8px; color: var(--text-dim); background: var(--field-sunk);
}
hr { border: none; border-top: 1px solid var(--hairline); margin: 2em 0; }
code {
  font: 0.9em/1.4 var(--font-mono);
  background: var(--field-sunk); padding: .15em .4em; border-radius: 4px;
}
pre {
  background: var(--field-sunk); padding: 1em; border-radius: 8px;
  overflow-x: auto; border: 1px solid var(--hairline);
}
pre code { background: none; padding: 0; }
table { width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 0.95em; }
th, td { border-bottom: 1px solid var(--hairline); padding: .5em .75em; text-align: left; vertical-align: top; }
th {
  background: var(--field-sunk); color: var(--text-dim);
  font: 400 0.72rem/1.4 var(--font-mono); letter-spacing: 0.18em; text-transform: uppercase;
}"""

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
_LINK = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
_LINK_TOKEN = re.compile("\x00(\\d+)\x00")
_URL_SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")
_ALLOWED_SCHEMES = {"http", "https", "mailto"}


def render_document(
    body_html: str, *, title: str, extra_css: str = "", mermaid: bool = False
) -> str:
    """Wrap caller-supplied body HTML in the shared self-contained document shell.

    The shell owns `<head>`, the base theme CSS, and the offline/deterministic
    contract; the caller owns everything inside `<body>` and is responsible for
    escaping its own content. `extra_css` is appended to the base theme so a
    skill can style its own body markup; `mermaid` opts into the CDN mermaid
    bootstrap. This is the seam a skill uses to render its own template (e.g.
    /age's severity-grouped findings) without hand-rolling the document chrome.
    """
    css = _CSS if not extra_css else f"{_CSS}\n{extra_css}"
    scripts = _MERMAID_SCRIPTS if mermaid else ""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>\n{css}\n</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body_html}\n"
        f"{scripts}"
        "</body>\n"
        "</html>\n"
    )


def render(markdown: str, *, title: str) -> str:
    """Convert a closed-subset Markdown report into a complete HTML document."""
    blocks, has_mermaid = _parse(markdown.split("\n"))
    body = "\n".join(blocks)
    return render_document(body, title=title, mermaid=has_mermaid)


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
            items: list[str] = []
            while j < n and _LIST_ITEM.match(lines[j]):
                items.append(lines[j])
                j += 1
            out.append(_render_list(items))
            i = j
            continue
        if line.lstrip().startswith(">"):
            flush()
            j = i
            quoted: list[str] = []
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
    first_match = _LIST_ITEM.match(items[0])
    assert first_match is not None
    top_ordered = first_match.group(2).endswith(".")
    top_tag = "ol" if top_ordered else "ul"
    parts = [f"<{top_tag}>"]
    li_open = False
    nested_tag: str | None = None
    for item in items:
        m = _LIST_ITEM.match(item)
        assert m is not None
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
    text = text.replace("\x00", "\uFFFD")
    parts: list[str] = []
    for idx, seg in enumerate(_CODE_SPAN.split(text)):
        if idx % 2 == 1:
            parts.append(f"<code>{html.escape(seg)}</code>")
        else:
            parts.append(_inline_spans(seg))
    return "".join(parts)


def _emphasis(s: str) -> str:
    s = html.escape(s)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _ITALIC_STAR.sub(r"<em>\1</em>", s)
    return _ITALIC_UNDER.sub(r"<em>\1</em>", s)


def _url_is_safe(url: str) -> bool:
    """Allow http/https/mailto and relative URLs without ASCII controls."""
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in url):
        return False
    match = _URL_SCHEME.match(url.strip())
    return match is None or match.group(1).lower() in _ALLOWED_SCHEMES


def _render_link(anchor: str, url: str) -> str:
    if _url_is_safe(url):
        return f'<a href="{html.escape(url)}">{anchor}</a>'
    return anchor


def _inline_spans(seg: str) -> str:
    """Tokenize links out before emphasis so a URL's underscores/asterisks are never
    turned into <em>/<strong>; emphasis runs on link text and non-link text only.
    """
    links: list[tuple[str, str]] = []

    def _stash(m: re.Match[str]) -> str:
        links.append((m.group(1), m.group(2)))
        return f"\x00{len(links) - 1}\x00"

    s = _emphasis(_LINK.sub(_stash, seg))

    def _restore(m: re.Match[str]) -> str:
        text, url = links[int(m.group(1))]
        return _render_link(_emphasis(text), url)

    return _LINK_TOKEN.sub(_restore, s)
