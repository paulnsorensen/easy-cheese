#!/usr/bin/env python3
"""Render a deterministic static HTML report from an /age markdown report."""

from __future__ import annotations

import argparse
import html
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from findings import SEVERITIES, Finding, parse_findings_report

SEVERITY_STYLES: dict[str, dict[str, str]] = {
    "blocker": {
        "badge": "bg-red-950 text-red-50 ring-red-300/40",
        "panel": "border-red-300 bg-red-50/80",
        "accent": "bg-red-600",
    },
    "high": {
        "badge": "bg-orange-900 text-orange-50 ring-orange-300/40",
        "panel": "border-orange-300 bg-orange-50/80",
        "accent": "bg-orange-500",
    },
    "medium": {
        "badge": "bg-amber-800 text-amber-50 ring-amber-300/40",
        "panel": "border-amber-300 bg-amber-50/80",
        "accent": "bg-amber-500",
    },
    "low": {
        "badge": "bg-slate-800 text-slate-50 ring-slate-300/40",
        "panel": "border-slate-300 bg-slate-50/80",
        "accent": "bg-slate-500",
    },
}


def _escape(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def _slug_from_report(report: Path) -> str:
    stem = report.stem
    return stem[:-4] if stem.endswith(".md") else stem


def _severity_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {severity: 0 for severity in SEVERITIES}
    for finding in findings:
        if finding.severity in counts:
            counts[finding.severity] += 1
    return counts


def _mermaid_chart(counts: dict[str, int]) -> str:
    rows = [f'    "{severity}" : {count}' for severity, count in counts.items() if count]
    if not rows:
        return ""
    return "\n".join(["pie title Findings by severity", *rows])


def _badge(severity: str) -> str:
    style = SEVERITY_STYLES.get(severity, SEVERITY_STYLES["low"])["badge"]
    return (
        f'<span class="inline-flex items-center rounded-full px-3 py-1 text-xs font-black uppercase '
        f'tracking-[0.22em] shadow-sm ring-1 {style}">{_escape(severity)}</span>'
    )


def _metadata_pill(label: str, value: str | None) -> str:
    if not value:
        return ""
    return (
        '<span class="rounded-full border border-slate-200 bg-white/80 px-2.5 py-1 text-xs '
        'font-semibold text-slate-600 shadow-sm">'
        f'{_escape(label)}: <span class="text-slate-950">{_escape(value)}</span></span>'
    )


def _finding_card(finding: Finding) -> str:
    pills = "".join(
        pill
        for pill in (
            _metadata_pill("tier", finding.location_tier),
            _metadata_pill("now", finding.fix_cost_now),
            _metadata_pill("later", finding.fix_cost_later),
        )
        if pill
    )
    recommendation = ""
    if finding.recommendation:
        recommendation = (
            '<div class="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">'
            '<div class="mb-1 text-xs font-black uppercase tracking-[0.2em] text-slate-500">Recommendation</div>'
            f'<p class="whitespace-pre-wrap text-sm leading-6 text-slate-800">{_escape(finding.recommendation)}</p>'
            '</div>'
        )
    before_after = ""
    before = finding.extra.get("before") if finding.extra else None
    after = finding.extra.get("after") if finding.extra else None
    if before or after:
        before_after = (
            '<div class="mt-4 grid gap-3 md:grid-cols-2">'
            '<div class="rounded-xl border border-rose-200 bg-rose-50 p-4">'
            '<div class="mb-1 text-xs font-black uppercase tracking-[0.2em] text-rose-700">Before</div>'
            f'<pre class="whitespace-pre-wrap text-sm leading-6 text-rose-950">{_escape(before)}</pre>'
            '</div>'
            '<div class="rounded-xl border border-emerald-200 bg-emerald-50 p-4">'
            '<div class="mb-1 text-xs font-black uppercase tracking-[0.2em] text-emerald-700">After</div>'
            f'<pre class="whitespace-pre-wrap text-sm leading-6 text-emerald-950">{_escape(after)}</pre>'
            '</div>'
            '</div>'
        )
    return (
        '<article class="rounded-2xl border border-slate-200 bg-white/95 p-5 shadow-sm shadow-slate-200/70">'
        '<div class="flex flex-wrap items-start justify-between gap-3">'
        '<div>'
        f'<div class="font-mono text-xs font-bold text-slate-500">#{finding.id} · {_escape(finding.dimension)}</div>'
        f'<h3 class="mt-1 text-lg font-black leading-tight text-slate-950">{_escape(finding.location)}</h3>'
        '</div>'
        f'{_badge(finding.severity)}'
        '</div>'
        f'<p class="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-800">{_escape(finding.summary)}</p>'
        f'<div class="mt-4 flex flex-wrap gap-2">{pills}</div>'
        f'{recommendation}'
        f'{before_after}'
        '</article>'
    )


def _section(severity: str, findings: list[Finding]) -> str:
    if not findings:
        return ""
    style = SEVERITY_STYLES.get(severity, SEVERITY_STYLES["low"])
    cards = "\n".join(_finding_card(finding) for finding in findings)
    plural = "" if len(findings) == 1 else "s"
    return (
        f'<section class="rounded-3xl border p-5 shadow-sm {style["panel"]}">'
        '<div class="mb-4 flex items-center justify-between gap-4">'
        '<div class="flex items-center gap-3">'
        f'<span class="h-10 w-2 rounded-full {style["accent"]}"></span>'
        f'<h2 class="text-2xl font-black capitalize tracking-tight text-slate-950">{_escape(severity)}</h2>'
        '</div>'
        f'<span class="font-mono text-sm font-bold text-slate-600">{len(findings)} finding{plural}</span>'
        '</div>'
        f'<div class="grid gap-4">{cards}</div>'
        '</section>'
    )


def render_html(report_text: str, *, slug: str) -> str:
    findings = parse_findings_report(report_text)
    by_severity: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_severity[finding.severity].append(finding)

    counts = _severity_counts(findings)
    total = sum(counts.values())
    chart = _mermaid_chart(counts)
    chart_html = (
        '<div class="mermaid rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">\n'
        f"{chart}\n"
        "</div>"
        if chart
        else '<div class="rounded-2xl border border-dashed border-slate-300 bg-white/80 p-8 text-center text-slate-500 shadow-sm">No findings.</div>'
    )
    sections = "\n".join(_section(severity, by_severity[severity]) for severity in SEVERITIES if by_severity[severity])
    if not sections:
        sections = (
            '<section class="rounded-3xl border border-dashed border-slate-300 bg-white/85 p-10 text-center shadow-sm">'
            '<h2 class="text-2xl font-black text-slate-950">No findings</h2>'
            '<p class="mt-2 text-slate-600">The markdown age report did not contain blocker, high, medium, or low findings.</p>'
            '</section>'
        )
    count_cards = "\n".join(
        '<div class="rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-sm">'
        f'<div class="text-xs font-black uppercase tracking-[0.22em] text-slate-500">{_escape(severity)}</div>'
        f'<div class="mt-2 text-3xl font-black text-slate-950">{count}</div>'
        '</div>'
        for severity, count in counts.items()
    )
    safe_slug = _escape(slug)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Age Report — {safe_slug}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="module">import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"; mermaid.initialize({{ startOnLoad: true, theme: "neutral" }});</script>
</head>
<body class="min-h-screen bg-[radial-gradient(circle_at_top_left,#fee2e2,transparent_28rem),radial-gradient(circle_at_top_right,#dbeafe,transparent_24rem),linear-gradient(135deg,#f8fafc,#eef2ff)] text-slate-900">
  <main class="mx-auto max-w-6xl px-6 py-10">
    <header class="mb-8 overflow-hidden rounded-[2rem] border border-slate-200 bg-slate-950 p-8 text-white shadow-2xl shadow-slate-300/60">
      <p class="font-mono text-xs font-black uppercase tracking-[0.32em] text-cyan-200">/age findings</p>
      <div class="mt-3 flex flex-wrap items-end justify-between gap-4">
        <h1 class="text-4xl font-black tracking-tight md:text-6xl">{safe_slug}</h1>
        <div class="rounded-2xl bg-white/10 px-5 py-3 text-right ring-1 ring-white/15">
          <div class="text-xs font-black uppercase tracking-[0.22em] text-slate-300">Total</div>
          <div class="text-4xl font-black">{total}</div>
        </div>
      </div>
    </header>

    <section class="mb-8 grid gap-4 md:grid-cols-4">
      {count_cards}
    </section>

    <section class="mb-8">
      {chart_html}
    </section>

    <div class="grid gap-6">
      {sections}
    </div>
  </main>
</body>
</html>
"""


def write_html_report(report: Path, *, slug: str | None = None, out_dir: Path | None = None) -> Path:
    report_text = report.read_text(encoding="utf-8")
    resolved_slug = slug or _slug_from_report(report)
    destination = out_dir or Path(tempfile.gettempdir())
    destination.mkdir(parents=True, exist_ok=True)
    html_path = destination / f"age-{resolved_slug}.html"
    html_path.write_text(render_html(report_text, slug=resolved_slug), encoding="utf-8")
    return html_path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render a static HTML /age findings report.")
    parser.add_argument("--report", required=True, type=Path, help="Path to the markdown /age report.")
    parser.add_argument("--slug", default=None, help="Slug for the HTML title and age-<slug>.html filename.")
    parser.add_argument("--out-dir", default=None, type=Path, help="Output directory; defaults to the OS temp directory.")
    args = parser.parse_args(argv[1:])

    if not args.report.exists():
        print(f"ERROR: report not found: {args.report}", file=sys.stderr)
        return 2
    html_path = write_html_report(args.report, slug=args.slug, out_dir=args.out_dir)
    print(html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
