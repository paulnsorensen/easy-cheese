"""CLI entry point for age_route.route -- contextual JSON in, JSON out.

The request is read from an optional JSON path or stdin and passed to the pure
contextual planner.  This wrapper owns only argument and stream I/O.
"""
from __future__ import annotations

import sys

from easy_cheese.shared.manifest_io import json_command

from .age_route import route

main = json_command(route, "usage: age_route_cli.py [<request.json>]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
