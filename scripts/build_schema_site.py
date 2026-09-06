#!/usr/bin/env python3
"""Render the static site served at https://schemas.easy-cheese.dev.

Every URI in ``REGISTERED_CONTRACT_SCHEMA_URIS`` is namespaced under
``SCHEMA_ROOT``; the bytes behind each one are produced in-process by
``schema_bytes()``. This script projects that catalogue onto disk at the
extensionless paths the URIs already claim (``/curd-plan``,
``/review-request``, ...), so the published document at a URI is the same
document the installed ``easy-cheese-schemas`` package validates against.
Nothing here is hand-maintained: adding a contract to the catalogue adds a
served path on the next deploy.

Emits, under ``--out``:

* one file per registered URI, holding exactly ``schema_bytes(uri)``;
* ``_headers``, giving each of those extensionless paths the
  ``application/schema+json`` content type (plus open CORS, so browser-based
  JSON Schema tooling can dereference them);
* ``index.html``, listing the catalogue and the package version it came from.

``_headers`` is a Cloudflare Pages convention. GitHub Pages cannot set a
content type for extensionless files, and this repository's one GitHub Pages
site already serves the Starlight docs, so the schema host is a separate
Cloudflare Pages project (see ``.github/workflows/schemas-site.yml``).
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]

for _extra in (REPO_ROOT / "vendor", REPO_ROOT / "src"):
    _path = str(_extra)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from easy_cheese_schemas import REGISTERED_CONTRACT_SCHEMA_URIS, __version__  # noqa: E402
from easy_cheese_schemas.schema_runtime import schema_bytes  # noqa: E402

SCHEMA_CONTENT_TYPE = "application/schema+json; charset=utf-8"
HEADERS_FILENAME = "_headers"
INDEX_FILENAME = "index.html"


def schema_paths() -> dict[str, str]:
    """Map each registered schema URI to the site-relative path it is served at."""
    paths: dict[str, str] = {}
    for uri in sorted(REGISTERED_CONTRACT_SCHEMA_URIS):
        slug = uri.rsplit("/", 1)[-1]
        if not slug or slug in {HEADERS_FILENAME, INDEX_FILENAME}:
            raise SystemExit(f"build_schema_site: unusable served path for {uri}")
        paths[uri] = slug
    return paths


def render_headers(paths: dict[str, str]) -> str:
    """Render the Cloudflare Pages ``_headers`` rules for the served schemas."""
    rules = "\n".join(
        f"/{slug}\n  Content-Type: {SCHEMA_CONTENT_TYPE}\n  Access-Control-Allow-Origin: *"
        for slug in sorted(paths.values())
    )
    return f"{rules}\n"


def render_index(paths: dict[str, str]) -> str:
    """Render the ``/`` landing page listing the catalogue and its version."""
    rows = "\n".join(
        f'      <li><a href="/{slug}"><code>{html.escape(uri)}</code></a></li>'
        for uri, slug in sorted(paths.items())
    )
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>easy-cheese contract schemas</title>
    <style>
      body {{ font-family: system-ui, sans-serif; margin: 0 auto; max-width: 46rem;
             padding: 2rem 1rem; line-height: 1.6; }}
      code {{ font-size: 0.95rem; }}
      ul {{ padding-left: 1.2rem; }}
    </style>
  </head>
  <body>
    <h1>🧀 easy-cheese contract schemas</h1>
    <p>
      JSON Schema (draft 2020-12) documents for the easy-cheese workflow
      contracts, generated from
      <a href="https://pypi.org/project/easy-cheese-schemas/">easy-cheese-schemas</a>
      <code>{html.escape(__version__)}</code>. Each URI below dereferences to the
      exact bytes that release validates against.
    </p>
    <ul>
{rows}
    </ul>
    <p>
      Source:
      <a href="https://github.com/paulnsorensen/easy-cheese">github.com/paulnsorensen/easy-cheese</a>
    </p>
  </body>
</html>
"""


def build(out: Path) -> Path:
    """Write the deployable site tree into ``out``. Returns ``out``."""
    paths = schema_paths()
    out.mkdir(parents=True, exist_ok=True)

    for uri, slug in paths.items():
        _ = (out / slug).write_bytes(schema_bytes(uri))
    _ = (out / HEADERS_FILENAME).write_text(render_headers(paths), encoding="utf-8")
    _ = (out / INDEX_FILENAME).write_text(render_index(paths), encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the schemas.easy-cheese.dev site.")
    _ = parser.add_argument("--out", type=Path, required=True, help="Output directory.")
    args = parser.parse_args(argv[1:])
    out = build(cast(Path, args.out))
    print(f"built {len(REGISTERED_CONTRACT_SCHEMA_URIS)} schema documents at {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
