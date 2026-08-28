"""CLI entry point for age_route.route -- JSON in (arg path or stdin), JSON out.

Split from age_route.py so that module stays a pure function with zero I/O
imports (see age_route.py's module docstring); all I/O for pyz dispatch
lives here instead.
"""
from __future__ import annotations

import sys

from easy_cheese.shared.manifest_io import json_command

from .age_route import route

main = json_command(route, "usage: age_route_cli.py [<request.json>]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
