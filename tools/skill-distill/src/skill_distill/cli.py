"""Command-line boundary for deterministic skill-distill preparation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path


def _prepare(args: argparse.Namespace) -> int:
    from .prepare import prepare_to_path

    prepare_to_path(args.report, args.adversarial_controls, args.out)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-distill")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser(
        "prepare", help="build the deterministic pilot dataset"
    )
    prepare.add_argument("--report", required=True, type=Path)
    prepare.add_argument("--adversarial-controls", required=True, type=Path)
    prepare.add_argument("--out", required=True, type=Path)
    prepare.set_defaults(run=_prepare)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.run(args)
