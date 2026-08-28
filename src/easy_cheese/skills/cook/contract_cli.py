"""Cook CLI for pointer-only typed handoff acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from easy_cheese.shared.handoffs import HandoffError, accept, canonical_bytes


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cook contract")
    operations = parser.add_subparsers(dest="operation", required=True)
    accept_parser = operations.add_parser("accept")
    accept_parser.add_argument("--pointer", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        accepted = accept(args.pointer)
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "canonical": accepted.canonical,
                    "normalization_receipt": accepted.normalization_receipt,
                }
            )
            + b"\n"
        )
        return 0
    except (HandoffError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
