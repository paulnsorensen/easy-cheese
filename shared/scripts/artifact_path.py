#!/usr/bin/env python3
"""Resolve a durable-corpus artifact path for a prose-driven skill.

Thin CLI over ``paths.py`` so a skill can ask for the on-disk home of an
artifact without knowing the project key or XDG routing. Prints the resolved
path on stdout (absolute for the durable phases — specs, research — it is called with).

  research -> project_corpus_root(); the caller composes
              <root>/research/<slug>/<slug>.md + raw/ (the nested layout
              paths.artifact_path deliberately does not own). The slug is
              ignored and not validated for research.
  else     -> paths.artifact_path(phase, slug); specs -> <corpus>/specs/<slug>.md.

Exit 2 on bad args; nonzero on a paths validation error (unknown phase, or a bad
slug on non-research phases).

Shared source: build_pyz.py registers this one file as the ``artifact-path``
subcommand across the skills that need it (mold, briesearch, cook,
cheese-factory) and auto-vendors ``paths`` alongside it.
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
    parser.add_argument("slug", help="Kebab-case artifact slug (ignored for research).")
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
