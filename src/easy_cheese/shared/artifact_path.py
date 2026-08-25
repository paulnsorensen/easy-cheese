"""Zip-safe artifact-path command delegating to the canonical path producer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import paths as _paths

PHASES = _paths.PHASES
XDG_PHASES = _paths.XDG_PHASES
PHASE_DIRS = _paths.PHASE_DIRS
KEBAB_SLUG = _paths.KEBAB_SLUG
_sanitize_segment = _paths._sanitize_segment
_slug_from_remote = _paths._slug_from_remote
_git_identity = _paths._git_identity
_corpus_home = _paths.corpus_home


def _project_key() -> str:
    """Compatibility alias for the canonical producer's project key."""
    return _paths.project_key()


def project_corpus_root() -> Path:
    """Compatibility alias for the canonical producer's corpus root."""
    return _paths.project_corpus_root()


def artifact_path(phase: str, slug: str) -> Path:
    """Compatibility alias for the canonical producer's artifact path."""
    return _paths.artifact_path(phase, slug)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase")
    parser.add_argument("slug")
    args = parser.parse_args(argv)
    try:
        resolved = (
            project_corpus_root()
            if args.phase == "research"
            else artifact_path(args.phase, args.slug)
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(resolved)
    return 0
