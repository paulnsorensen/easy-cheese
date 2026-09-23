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
import sys

import tempfile
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from easy_cheese.shared import cli, html_report


def _command(*, in_path: Annotated[str, Parameter(name="--in")], title: str, out_name: Annotated[str, Parameter(name="--out-name")]) -> int:
    cli.reject_path_segment("--out-name", out_name)
    src = Path(in_path)
    if not src.is_file():
        raise cli.CliError(f"--in not found: {in_path}")
    document = html_report.render(src.read_text(encoding="utf-8"), title=title)
    out_path = Path(tempfile.gettempdir()) / f"{out_name}.html"
    _ = out_path.write_text(document, encoding="utf-8")
    print(out_path)
    return 0


app = App(name="render-html")
_ = app.default(_command)


def main(argv: list[str]) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))