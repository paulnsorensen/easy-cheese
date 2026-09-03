"""Resolve durable and transient artifact paths for packaged skills.

Thin CLI wrapper over ``paths.py`` -- phase tables, the slug regex, and the
root-resolution math live there as the single source of truth. See
``paths.artifact_path`` / ``paths.project_corpus_root``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from easy_cheese.shared import paths

PHASES = paths.PHASES
XDG_PHASES = paths.XDG_PHASES
PHASE_DIRS = paths.PHASE_DIRS
KEBAB_SLUG = paths.KEBAB_SLUG


def project_corpus_root() -> Path:
    return paths.project_corpus_root()


def artifact_path(phase: str, slug: str) -> Path:
    # paths.validate_slug reports an empty slug as "must be a non-empty
    # string"; this shim's long-standing CLI contract folds that case into
    # the same kebab-case message as every other invalid slug, so it is
    # special-cased here rather than delegated.
    if not isinstance(slug, str) or not slug:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError(
            f"slug {slug!r} must be kebab-case, 1-64 chars, [a-z0-9-], "
            + "no leading/trailing hyphen, no double hyphens"
        )
    return paths.artifact_path(phase, slug)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("phase")
    _ = parser.add_argument("slug")
    args = parser.parse_args(argv)
    phase = cast(str, args.phase)
    slug = cast(str, args.slug)
    try:
        resolved = artifact_path(phase, slug)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(resolved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))