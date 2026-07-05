"""CLI wrapper for shared/scripts/html_report.py.

Converts an already-written Markdown report artifact into ONE self-contained,
offline, byte-deterministic themed HTML file in the OS temp dir.

    python3 .../common.pyz render_html \\
        --in <md-file> --title <str> --out-name <name>

Reads ``--in`` (the source Markdown artifact), renders it via
``html_report.render``, and writes ``<tempdir>/<out-name>.html``. Emits the
output path on stdout. ``--out-name`` is the filename stem only; path-traversal
segments (``..`` / ``/`` / ``\\``) are rejected. Phase/slug-agnostic: path math
and slug are the caller's concern, not this helper's.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

import cli
import html_report


def _reject_traversal(field: str, value: str) -> None:
    if ".." in value or "/" in value or "\\" in value:
        raise cli.CliError(f"{field} rejects path traversal: {value!r}")


def _cmd_render(args: argparse.Namespace) -> None:
    _reject_traversal("--out-name", args.out_name)
    src = Path(args.in_path)
    if not src.is_file():
        raise cli.CliError(f"--in not found: {args.in_path}")
    document = html_report.render(src.read_text(encoding="utf-8"), title=args.title)
    out_path = Path(os.path.join(tempfile.gettempdir(), f"{args.out_name}.html"))
    out_path.write_text(document, encoding="utf-8")
    cli.emit(str(out_path))


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Render a Markdown report artifact into a self-contained HTML file."
    parser.add_argument("--in", dest="in_path", required=True, help="source markdown artifact")
    parser.add_argument("--title", required=True, help="document title")
    parser.add_argument("--out-name", dest="out_name", required=True, help="output filename stem")
    parser.set_defaults(func=_cmd_render)


if __name__ == "__main__":
    cli.run(_setup)
