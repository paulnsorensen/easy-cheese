"""Shared YAML/JSON loading helpers for fan-out engine scripts."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from easy_cheese_schemas.io import ManifestLoadError, parse_mapping
from easy_cheese_schemas.validate import require_exact_keys

__all__ = [
    "ManifestLoadError",
    "parse_mapping",
    "read_mapping_arg_or_stdin",
    "json_command",
]

def read_mapping_arg_or_stdin(argv: list[str], usage: str) -> dict[str, object]:
    """Read one optional path argument or stdin, returning a parsed mapping."""
    if len(argv) > 1:
        raise ManifestLoadError(usage)
    if argv:
        path = Path(argv[0])
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ManifestLoadError(f"manifest not found: {path}") from exc
        return parse_mapping(text, str(path))
    return parse_mapping(sys.stdin.read())


def json_command(
    func: Callable[..., object], usage: str, *, keys: Iterable[str] | None = None
) -> Callable[[list[str]], int]:
    """Build a `main(argv)` that reads a JSON mapping, calls `func`, and prints JSON.

    Exit codes and the "ERROR: " stderr prefix match the previously hand-written
    wrappers: 2 for a manifest-load failure, 1 for a `func` rejection, 0 on success.
    With `keys`, the payload must carry exactly those keys; a mismatch names the
    missing and unknown ones and exits 1 before `func` runs.
    """
    expected = None if keys is None else tuple(keys)

    def main(argv: list[str]) -> int:
        try:
            payload = read_mapping_arg_or_stdin(argv, usage)
        except ManifestLoadError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        try:
            if expected is not None:
                require_exact_keys(payload, expected, "request")
            result = func(**payload)
        except (TypeError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        json.dump(result, sys.stdout, indent=2)
        _ = sys.stdout.write("\n")
        return 0

    return main
