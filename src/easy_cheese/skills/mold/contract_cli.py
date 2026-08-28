"""Mold CLI for typed handoff publication."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from easy_cheese.shared.handoffs import (
    HandoffError,
    canonical_bytes,
    migrate_legacy_text,
    publish_writer_text,
    read_text_nofollow,
)


def _result(value) -> dict[str, object]:
    return {
        "pointer_path": str(value.pointer_path),
        "pointer": value.pointer,
        "canonical": value.canonical,
        "normalization_receipt": value.normalization_receipt,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="mold contract")
    operations = parser.add_subparsers(dest="operation", required=True)
    publish = operations.add_parser("publish")
    publish.add_argument("--writer-view", required=True, type=Path)
    publish.add_argument("--destination", required=True)
    publish.add_argument("--operation-id", required=True)
    publish.add_argument("--out-dir", required=True, type=Path)
    migrate = operations.add_parser("migrate")
    migrate.add_argument("--legacy-handoff", required=True, type=Path)
    migrate.add_argument("--operation-id", required=True)
    migrate.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "publish":
            result = publish_writer_text(
                read_text_nofollow(args.writer_view),
                args.destination,
                args.operation_id,
                args.out_dir,
            )
        else:
            result = migrate_legacy_text(
                read_text_nofollow(args.legacy_handoff),
                args.operation_id,
                args.out_dir,
            )
        sys.stdout.buffer.write(canonical_bytes(_result(result)) + b"\n")
        return 0
    except (HandoffError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
