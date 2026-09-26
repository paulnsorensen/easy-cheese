"""CLI wrapper for shared/scripts/html_report.py.

Converts an already-written Markdown report artifact into ONE self-contained,
offline, byte-deterministic themed HTML file in the OS temp dir.

    python3 .../<skill>.pyz render_html \\
        --in <md-file> --title <str> --out-name <name>

Reads ``--in`` (the source Markdown artifact), renders it via
``html_report.render``, and writes ``<tempdir>/<out-name>.html``. Emits the
output path on stdout. ``--out-name`` is the filename stem only; path-traversal
segments (``..`` / ``/`` / ``\\``) and Windows drive/path designators (``:``)
are rejected. Phase/slug-agnostic: path math and slug are the caller's concern,
not this helper's.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

import cyclopts
import fromargs

from easy_cheese.shared import html_report, paths


def render(
    *,
    in_path: Annotated[str, cyclopts.Parameter(name="--in")],
    title: str,
    out_name: str,
) -> str:
    """Render a Markdown report artifact into a self-contained HTML file.

    Parameters
    ----------
    in_path
        Source markdown artifact.
    title
        Document title.
    out_name
        Output filename stem.
    """
    paths.reject_path_segment("--out-name", out_name)
    src = Path(in_path)
    if not src.is_file():
        raise fromargs.CliError(f"--in not found: {in_path}")
    document = html_report.render(src.read_text(encoding="utf-8"), title=title)
    out_path = Path(tempfile.gettempdir()) / f"{out_name}.html"
    _ = out_path.write_text(document, encoding="utf-8")
    return str(out_path)


def build_app() -> fromargs.App:
    return fromargs.App(
        "render-html",
        help="Render a Markdown report artifact into a self-contained HTML file.",
        help_formatter="plain",
        default_command=render,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())