"""Shared YAML/JSON loading helpers for fan-out engine scripts."""

from __future__ import annotations

import sys
from pathlib import Path

from easy_cheese_schemas.io import ManifestLoadError, parse_mapping

__all__ = [
    "ManifestLoadError",
    "parse_mapping",
    "read_mapping_arg_or_stdin",
    "read_mapping_file",
]

def read_mapping_file(path: Path) -> dict[str, object]:
    """Read and parse one mapping document; a missing file is a `ManifestLoadError`."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManifestLoadError(f"manifest not found: {path}") from exc
    except OSError as exc:
        raise ManifestLoadError(f"cannot read manifest {path}: {exc}") from exc
    return parse_mapping(text, str(path))


def read_mapping_arg_or_stdin(argv: list[str], usage: str) -> dict[str, object]:
    """Read one optional path argument or stdin, returning a parsed mapping."""
    # A flag is never a manifest path.
    if len(argv) > 1 or (argv and argv[0].startswith("-")):
        raise ManifestLoadError(usage)
    if argv:
        return read_mapping_file(Path(argv[0]))
    return parse_mapping(sys.stdin.read())

