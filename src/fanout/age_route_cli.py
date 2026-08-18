# ships-as: affinage.pyz age-route age.pyz age-route
"""CLI entry point for age_route.route -- JSON in (arg path or stdin), JSON out.

Split from age_route.py so that module stays a pure function with zero I/O
imports (see age_route.py's module docstring); all I/O for pyz dispatch
lives here instead.
"""
from __future__ import annotations

import json
import sys

from age_route import route
from manifest_io import ManifestLoadError, read_mapping_arg_or_stdin


def main(argv: list[str]) -> int:
    try:
        payload = read_mapping_arg_or_stdin(argv, "usage: age_route_cli.py [<request.json>]")
    except ManifestLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        result = route(**payload)
    except (TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))