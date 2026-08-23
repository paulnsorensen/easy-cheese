"""CLI wrapping normalize_agent_output: writer-view JSON in, canonical JSON out.

The document argument is the AgentWriterView JSON (`kind` + `payload`) an
agent wrote. The separate --invocation file supplies the host-owned data
(plan ids, contract versions, evidence, ...) normalize_agent_output needs to
resolve the writer's shorthand into the canonical host artifact. A document
that itself supplies a host-owned field -- including `invocation` -- is
rejected before that resolution runs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from easy_cheese_schemas import (
    ContractValidationError,
    canonical_bytes,
    canonical_digest,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="normalize.py")
    parser.add_argument("document", type=Path)
    parser.add_argument("--invocation", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv[1:])
    try:
        document_raw = args.document.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {args.document}: {exc}", file=sys.stderr)
        return 1
    try:
        invocation_raw = args.invocation.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {args.invocation}: {exc}", file=sys.stderr)
        return 1
    try:
        invocation = json.loads(invocation_raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid invocation JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(invocation, dict):
        print("ERROR: invocation must be a JSON object", file=sys.stderr)
        return 1
    try:
        artifact = normalize_agent_output(document_raw, invocation)
        contract_type = type(artifact.value)
        validate_contract(
            artifact.canonical_bytes,
            contract_type,
            supported_version_for(contract_type),
        )
    except ContractValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    wrapper = {
        "value": artifact.value,
        "digest": canonical_digest(artifact.value),
        "version": artifact.source_version,
    }
    sys.stdout.buffer.write(canonical_bytes(wrapper))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))