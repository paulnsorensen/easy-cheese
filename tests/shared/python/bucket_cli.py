"""Shared bucket-command parser for CLI adversarial and repair tests."""

from __future__ import annotations

import argparse
from typing import TextIO, cast


def print_bucket(args: argparse.Namespace) -> None:
    values = (cast(int, args.files), cast(int, args.modules), cast(str, args.title))
    print(*values, file=cast("TextIO", args.stdout))


def bucket_setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="cmd", required=True)
    bucket = sub.add_parser("bucket")
    _ = bucket.add_argument("--files", type=int, required=True)
    _ = bucket.add_argument("--modules", type=int, default=1)
    _ = bucket.add_argument("--title", default="")
    bucket.set_defaults(func=print_bucket)
