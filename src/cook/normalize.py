"""CLI wrapping normalize_agent_value: writer-view JSON in, canonical JSON out.

The input document is the AgentWriterView JSON (`kind` + `payload`) an agent
wrote, plus an optional sibling `invocation` object supplying the host-owned
data (plan ids, contract versions, evidence, ...) normalize_agent_value needs
to resolve the writer's shorthand into the canonical host artifact. Reject any
payload that itself supplies a host-owned field before that resolution runs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from easy_cheese_schemas import (
    ContractValidationError,
    canonical_bytes,
    normalize_agent_value,
)

USAGE = "usage: normalize.py <writer-view.json>"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"ERROR: {USAGE}", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not isinstance(document, dict):
        print("ERROR: writer-view document must be a JSON object", file=sys.stderr)
        return 1
    invocation = document.pop("invocation", {})
    if not isinstance(invocation, dict):
        print("ERROR: invocation must be a JSON object", file=sys.stderr)
        return 1
    try:
        value = normalize_agent_value(document, invocation)
    except ContractValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(canonical_bytes(value))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
