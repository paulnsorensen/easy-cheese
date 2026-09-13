#!/usr/bin/env python3
"""Render a canonical ReviewResult into one self-contained, offline HTML file.

Findings are grouped by severity (critical -> high -> medium -> low); each
finding's summary is rendered verbatim and HTML-escaped inside a
`whitespace-pre-wrap` container, prefixed by its location, so multi-line
summaries stay readable. A pure-CSS count bar summarises the distribution --
no CDN, no JavaScript, no mermaid.

The input is the ReviewResult JSON document /age publishes to /cure behind a
HandoffPointer; this script never re-parses a Markdown report. The document
shell (head, base theme, offline/deterministic contract) comes from the shared
`html_report.render_document`; this script owns only the age *body* template.

    html-report --report <review-result.json> --slug <slug> [--out-dir <dir>]

Writes `<out-dir>/age-<slug>.html` (out-dir defaults to the OS temp dir) and
prints the path on stdout.
"""
from __future__ import annotations

import argparse
import html
import tempfile
from pathlib import Path
from typing import TextIO, cast

from easy_cheese.shared import cli, html_report
from easy_cheese.shared import findings as findings_mod

# Badge + distribution-bar styling for the age body. Selectors stay lowercase so
# an empty report never leaks a capitalised severity word into the document.
_EXTRA_CSS = """.dist { display: flex; gap: 2px; margin: 1.5em 0; border-radius: 6px; overflow: hidden; }
.seg { padding: .4em .6em; font-size: .85em; font-weight: 600; color: #fff; white-space: nowrap; }
.sev-critical { background: #b91c1c; }
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


def _finding_text(finding: findings_mod.Finding) -> str:
    """The verbatim block rendered for one finding: location line then summary."""
    if finding.location:
        return f"{finding.location}\n{finding.summary}"
    return finding.summary


def _build_body(slug: str, findings: list[findings_mod.Finding]) -> str:
    title = f"Age report — {html.escape(slug)}"
    by_sev: dict[str, list[findings_mod.Finding]] = {sev: [] for sev in findings_mod.SEVERITIES}
    for finding in findings_mod.group_by_severity(findings):
        if finding.severity in by_sev:
            by_sev[finding.severity].append(finding)

    present = [sev for sev in findings_mod.SEVERITIES if by_sev[sev]]
    if not present:
        return f"<h1>{title}</h1>\n<p class=\"empty\">No findings.</p>"

    segments = "".join(
        f'<div class="seg sev-{sev}" style="flex:{len(by_sev[sev])}">'
        + f"{sev.capitalize()} {len(by_sev[sev])}</div>"
        for sev in present
    )
    sections: list[str] = []
    for sev in present:
        items = "".join(
            '<div class="finding"><pre class="body whitespace-pre-wrap">'
            + f"{html.escape(_finding_text(finding))}</pre></div>"
            for finding in by_sev[sev]
        )
        sections.append(
            f'<section class="sev-section"><h2 class="sev sev-{sev}">'
            + f"{sev.capitalize()}</h2>{items}</section>"
        )
    return f'<h1>{title}</h1>\n<div class="dist">{segments}</div>\n{"".join(sections)}'


def _cmd_html_report(args: argparse.Namespace) -> None:
    report_arg = cast(str, args.report)
    slug = cast(str, args.slug)
    out_dir_arg = cast(str, args.out_dir)
    stdout = cast("TextIO | None", args.stdout)

    cli.reject_path_segment("--slug", slug)
    out_dir = Path(out_dir_arg) if out_dir_arg else Path(tempfile.gettempdir())
    if not out_dir.is_dir():
        raise cli.CliError(f"--out-dir is not a directory: {out_dir}")

    result = findings_mod.load_review_result(report_arg)
    findings = findings_mod.findings_from_review_result(result)
    body = _build_body(slug, findings)
    document = html_report.render_document(
        body, title=f"Age report — {slug}", extra_css=_EXTRA_CSS
    )
    out_path = out_dir / f"age-{slug}.html"
    _ = out_path.write_text(document, encoding="utf-8")
    cli.emit(str(out_path), stdout=stdout)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Render a canonical ReviewResult JSON into a self-contained HTML file."
    _ = parser.add_argument("--report", required=True, help="path to a canonical ReviewResult JSON document")
    _ = parser.add_argument("--slug", required=True, help="slug for the output filename and title")
    _ = parser.add_argument(
        "--out-dir", default="", help="output directory (defaults to the OS temp dir)"
    )
    parser.set_defaults(func=_cmd_html_report)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))