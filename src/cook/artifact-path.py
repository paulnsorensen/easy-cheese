#!/usr/bin/env python3
"""Resolve a durable-corpus artifact path for this skill.

Thin shim over ``shared/scripts/paths.py`` so a prose-driven skill can ask for
the on-disk home of an artifact without knowing the project key or XDG routing.
Prints one absolute path on stdout.

  research -> project_corpus_root(); the caller composes
              <root>/research/<slug>/<slug>.md + raw/ (the nested layout
              paths.artifact_path deliberately does not own).
  else     -> paths.artifact_path(phase, slug); specs -> <corpus>/specs/<slug>.md.

Exit 2 on bad args; nonzero on a paths validation error (unknown phase, bad slug).

This file is identical across the skills that ship it (mold, briesearch, cook,
cheese-factory) and is auto-vendored with ``paths`` by build_pyz.py.
"""

from __future__ import annotations

import argparse
import sys

import paths


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").splitlines()[0],
    )
    parser.add_argument("phase", help="Corpus phase, e.g. specs or research.")
    parser.add_argument("slug", help="Kebab-case artifact slug.")
    args = parser.parse_args(argv)

    try:
        if args.phase == "research":
            resolved = paths.project_corpus_root()
        else:
            resolved = paths.artifact_path(args.phase, args.slug)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(resolved)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
