"""CLI structuring a payload against a named schema-catalog contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from easy_cheese_schemas import SCHEMA_ROOT, ContractValidationError, validate_contract

USAGE = "usage: validate.py <payload.json> --schema <slug>"


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[2] != "--schema":
        print(f"ERROR: {USAGE}", file=sys.stderr)
        return 2
    path = Path(argv[1])
    slug = argv[3]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    try:
        validate_contract(payload, f"{SCHEMA_ROOT}/{slug}")
    except KeyError:
        print(f"ERROR: unknown schema slug {slug!r}", file=sys.stderr)
        return 1
    except ContractValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: payload conforms to {slug!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
