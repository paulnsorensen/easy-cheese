#!/usr/bin/env python3
"""Print the slug-aware `research/<slug>/` layout as JSON.

This module owns the nested Briesearch layout. Callers use the JSON returned by
the `research-layout` command instead of rebuilding report, raw, or manifest
paths themselves.

JSON is the only output format: the consumer is an agent reading the result, and
a second serialization would be a knob nothing asked for.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict, cast

from easy_cheese.shared.paths import project_corpus_root, validate_slug

RESEARCH_RAW_DIRNAME = "raw"
RESEARCH_MANIFEST_NAME = "manifest.json"


class ResearchLayout(TypedDict):
    """These absolute paths define one `/briesearch` research artifact."""

    slug: str
    corpus_root: str
    dir: str
    report: str
    raw_dir: str
    manifest: str


def research_layout(slug: str, *, root: Path | str | None = None) -> ResearchLayout:
    """Return all absolute paths in the nested `research/<slug>/` layout."""
    err = validate_slug(slug)
    if err is not None:
        raise ValueError(err)
    corpus_root = Path(root) if root is not None else project_corpus_root()
    directory = corpus_root / "research" / slug
    return {
        "slug": slug,
        "corpus_root": str(corpus_root),
        "dir": str(directory),
        "report": str(directory / f"{slug}.md"),
        "raw_dir": str(directory / RESEARCH_RAW_DIRNAME),
        "manifest": str(directory / RESEARCH_MANIFEST_NAME),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    _ = parser.add_argument("slug", help="Kebab-case research slug (4-6 words).")
    args = parser.parse_args(argv)
    try:
        layout = research_layout(cast(str, args.slug))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(layout, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
