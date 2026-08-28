"""CLI entry point for pasteurize_route.size_pasteurize_fanout -- JSON in
(arg path or stdin), JSON out.

Split from pasteurize_route.py so that module stays a pure function with
zero I/O imports (see pasteurize_route.py's module docstring); all I/O for
pyz dispatch lives here instead.
"""
from __future__ import annotations

import sys

from easy_cheese.shared.manifest_io import json_command

from .pasteurize_route import size_pasteurize_fanout

main = json_command(size_pasteurize_fanout, "usage: pasteurize_route_cli.py [<request.json>]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
