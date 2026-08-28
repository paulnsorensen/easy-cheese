"""CLI entry point for pasteurize_route.size_pasteurize_fanout -- JSON in
(arg path or stdin), JSON out.

Split from pasteurize_route.py so that module stays a pure function with
zero I/O imports (see pasteurize_route.py's module docstring); all I/O for
pyz dispatch lives here instead.
"""
from __future__ import annotations

import json
import sys

from easy_cheese.shared.manifest_io import ManifestLoadError, read_mapping_arg_or_stdin

from .pasteurize_route import size_pasteurize_fanout


def main(argv: list[str]) -> int:
    try:
        payload = read_mapping_arg_or_stdin(argv, "usage: pasteurize_route_cli.py [<request.json>]")
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        result = size_pasteurize_fanout(**payload)
    except (TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
