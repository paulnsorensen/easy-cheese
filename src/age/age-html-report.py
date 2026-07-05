#!/usr/bin/env python3
"""Render an /age markdown report into one self-contained, offline HTML file.

Findings are grouped by severity (blocker → high → medium → low); each finding's
full text block is preserved verbatim and HTML-escaped inside a
`whitespace-pre-wrap` container, so multi-line summaries and recommendations stay
readable. A pure-CSS count bar summarises the distribution — no CDN, no
JavaScript, no mermaid.

The document shell (head, base theme, offline/deterministic contract) comes from
the shared `html_report.render_document`; this script owns only the age *body*
template. It is the reference example of a skill supplying its own body to the
shared renderer.

    html-report --report <md> --slug <slug> [--out-dir <dir>]

Writes `<out-dir>/age-<slug>.html` (out-dir defaults to the OS temp dir) and
prints the path on stdout.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import tempfile
from pathlib import Path

# Standalone runs (outside the bundle) need shared/scripts on sys.path; inside
# the .pyz these modules are flat siblings and this dir simply won't exist. The
# imports below therefore come after the path bootstrap (E402 is expected).
_SHARED = Path(__file__).resolve().parents[2] / "shared" / "scripts"
if _SHARED.is_dir() and str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

import cli  # noqa: E402
import findings as findings_mod  # noqa: E402
import html_report  # noqa: E402

# Reuse /age's canonical severity-heading + bullet matchers so this consumer
# stays in lockstep with the emit format findings.py already tracks.
_SEVERITY_HEADING_RE = findings_mod._SEVERITY_HEADING_RE
_BULLET_RE = findings_mod._BULLET_RE
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s")

# Badge + distribution-bar styling for the age body. Selectors stay lowercase so
# an empty report never leaks a capitalised severity word into the document.
_EXTRA_CSS = """.dist { display: flex; gap: 2px; margin: 1.5em 0; border-radius: 6px; overflow: hidden; }
.seg { padding: .4em .6em; font-size: .85em; font-weight: 600; color: #fff; white-space: nowrap; }
.sev-blocker { background: #b91c1c; }
.sev-high { background: #c2410c; }
.sev-medium { background: #a16207; }
.sev-low { background: #4b5563; }
h2.sev { display: inline-block; padding: .15em .6em; border-radius: 5px;
  color: #fff; font-size: 1rem; border: none; }
.finding { border: 1px solid var(--border); border-radius: 6px;
  padding: .75em 1em; margin: .6em 0; background: var(--accent); }
.body.whitespace-pre-wrap { white-space: pre-wrap; font: 0.9em/1.5 ui-monospace,
  SFMono-Regular, Menlo, Consolas, monospace; margin: 0; }
.empty { color: var(--muted); font-style: italic; }"""


def _finding_blocks(text: str) -> list[tuple[str, str]]:
    """Split a report into (severity, raw_block) pairs, one per finding bullet.

    Severity comes from the enclosing `## <severity>` heading; an inline
    `[dim:severity]` tag on the bullet overrides it. A block runs from its bullet
    line through every following line until the next bullet or severity heading,
    so multi-line summaries, sub-fields, and wrapped recommendations survive.
    """
    current: str | None = None
    blocks: list[tuple[str, list[str]]] = []
    pending: tuple[str, list[str]] | None = None  # (severity, lines)

    def close() -> None:
        nonlocal pending
        if pending is not None:
            blocks.append(pending)
        pending = None

    for raw in text.splitlines():
        stripped = raw.strip()
        if _ANY_HEADING_RE.match(stripped):
            # Any heading closes the open block; only a severity heading opens a
            # new scope. Trailing sections (## Confidence, ## Next step) thus end
            # the last finding instead of being swallowed into its body.
            close()
            severity_heading = _SEVERITY_HEADING_RE.match(stripped)
            current = severity_heading.group("severity").lower() if severity_heading else None
            continue
        bullet = _BULLET_RE.match(raw)
        if bullet:
            close()
            severity = bullet.group("sev").lower() if bullet.group("sev") else current
            if severity is not None:  # a bullet before any heading/tag is unscoped — skip
                pending = (severity, [raw])
            continue
        if pending is not None:
            pending[1].append(raw)
    close()
    return [(sev, "\n".join(lines).rstrip()) for sev, lines in blocks]


def _build_body(slug: str, blocks: list[tuple[str, str]]) -> str:
    title = f"Age report — {html.escape(slug)}"
    by_sev: dict[str, list[str]] = {sev: [] for sev in findings_mod.SEVERITIES}
    for severity, block in blocks:
        if severity in by_sev:
            by_sev[severity].append(block)

    present = [sev for sev in findings_mod.SEVERITIES if by_sev[sev]]
    if not present:
        return f"<h1>{title}</h1>\n<p class=\"empty\">No findings.</p>"

    segments = "".join(
        f'<div class="seg sev-{sev}" style="flex:{len(by_sev[sev])}">'
        f"{sev.capitalize()} {len(by_sev[sev])}</div>"
        for sev in present
    )
    sections = []
    for sev in present:
        items = "".join(
            f'<div class="finding"><pre class="body whitespace-pre-wrap">'
            f"{html.escape(block)}</pre></div>"
            for block in by_sev[sev]
        )
        sections.append(
            f'<section class="sev-section"><h2 class="sev sev-{sev}">'
            f"{sev.capitalize()}</h2>{items}</section>"
        )
    return f'<h1>{title}</h1>\n<div class="dist">{segments}</div>\n{"".join(sections)}'


def _cmd_html_report(args: argparse.Namespace) -> None:
    report = Path(args.report)
    if not report.is_file():
        raise cli.CliError(f"--report not found: {args.report}")
    if any(sep in args.slug for sep in ("..", "/", "\\", ":")):
        raise cli.CliError(f"--slug rejects path traversal: {args.slug!r}")
    out_dir = Path(args.out_dir) if args.out_dir else Path(tempfile.gettempdir())
    if not out_dir.is_dir():
        raise cli.CliError(f"--out-dir is not a directory: {out_dir}")

    blocks = _finding_blocks(report.read_text(encoding="utf-8"))
    body = _build_body(args.slug, blocks)
    document = html_report.render_document(
        body, title=f"Age report — {args.slug}", extra_css=_EXTRA_CSS
    )
    out_path = out_dir / f"age-{args.slug}.html"
    out_path.write_text(document, encoding="utf-8")
    cli.emit(str(out_path))


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Render an /age markdown report into a self-contained HTML file."
    parser.add_argument("--report", required=True, help="source /age markdown report")
    parser.add_argument("--slug", required=True, help="slug for the output filename and title")
    parser.add_argument(
        "--out-dir", default="", help="output directory (defaults to the OS temp dir)"
    )
    parser.set_defaults(func=_cmd_html_report)


if __name__ == "__main__":
    cli.run(_setup)
