"""CLI structuring a payload against a named schema-catalog contract."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from easy_cheese_schemas import (
    SCHEMA_ROOT,
    ContractValidationError,
    supported_version_for,
    validate_contract,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="validate.py")
    parser.add_argument("payload", type=Path)
    parser.add_argument("--schema", required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv[1:])
    try:
        raw = args.payload.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {args.payload}: {exc}", file=sys.stderr)
        return 1
    schema_uri = f"{SCHEMA_ROOT}/{args.schema}"
    try:
        supported_version = supported_version_for(schema_uri)
    except KeyError:
        print(f"ERROR: unknown schema slug {args.schema!r}", file=sys.stderr)
        return 1
    try:
        validate_contract(raw, schema_uri, supported_version)
    except ContractValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: payload conforms to {args.schema!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))