"""Cook CLI handlers for normalizing writer views and validating contracts.

``normalize`` combines agent-authored JSON with host-owned invocation data,
then emits a canonical artifact. ``validate`` checks a payload against a named
schema-catalog contract. Both handlers validate through one shared path so
their contract handling cannot drift.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from easy_cheese_schemas import (
    SCHEMA_ROOT,
    ContractValidationError,
    canonical_bytes,
    canonical_digest,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
)



def _validate_against(raw: bytes | str, schema: object) -> None:
    """Validate raw against schema's catalog-supported version.

    The one call both verbs route through, so their validation cannot drift.
    """
    validate_contract(raw, schema, supported_version_for(schema))


def _parse_normalize_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="normalize.py")
    parser.add_argument("document", type=Path)
    parser.add_argument("--invocation", required=True, type=Path)
    return parser.parse_args(argv)


def normalize_main(argv: list[str]) -> int:
    args = _parse_normalize_args(argv)
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
        _validate_against(artifact.canonical_bytes, type(artifact.value))
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


def _parse_validate_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="validate.py")
    parser.add_argument("payload", type=Path)
    parser.add_argument("--schema", required=True)
    return parser.parse_args(argv)


def validate_main(argv: list[str]) -> int:
    args = _parse_validate_args(argv)
    try:
        raw = args.payload.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {args.payload}: {exc}", file=sys.stderr)
        return 1
    schema_uri = f"{SCHEMA_ROOT}/{args.schema}"
    try:
        _validate_against(raw, schema_uri)
    except KeyError:
        print(f"ERROR: unknown schema slug {args.schema!r}", file=sys.stderr)
        return 1
    except ContractValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: payload conforms to {args.schema!r}")
    return 0


