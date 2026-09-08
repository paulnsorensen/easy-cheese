"""Shared YAML/JSON loading helpers for fan-out engine scripts."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from easy_cheese_schemas.io import ManifestLoadError, parse_mapping
from easy_cheese_schemas.validate import require_exact_keys

__all__ = [
    "ManifestLoadError",
    "parse_mapping",
    "read_mapping_arg_or_stdin",
    "read_mapping_file",
    "json_command",
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
    if len(argv) > 1:
        raise ManifestLoadError(usage)
    if argv:
        return read_mapping_file(Path(argv[0]))
    return parse_mapping(sys.stdin.read())


def json_command(
    func: Callable[..., object], usage: str, *, keys: Sequence[str] | None = None
) -> Callable[[list[str]], int]:
    """Build a `main(argv)` that reads a JSON mapping, calls `func`, and prints JSON.

    Exit codes and the "ERROR: " stderr prefix match the previously hand-written
    wrappers: 2 for a manifest-load failure, 1 for a `func` rejection, 0 on success.
    With `keys`, the payload must carry exactly those keys; a mismatch names the
    missing and unknown ones and exits 1 before `func` runs.
    """

    def main(argv: list[str]) -> int:
        try:
            payload = read_mapping_arg_or_stdin(argv, usage)
        except ManifestLoadError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        try:
            if keys is not None:
                require_exact_keys(payload, keys, "request")
            result = func(**payload)
        except (TypeError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        json.dump(result, sys.stdout, indent=2)
        _ = sys.stdout.write("\n")
        return 0

    return main
