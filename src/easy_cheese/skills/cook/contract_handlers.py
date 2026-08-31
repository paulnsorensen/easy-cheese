"""Handlers for Cook's normalize, validate, and accept contract commands.

``normalize`` combines agent-authored JSON with host-owned invocation data,
then emits a canonical artifact. ``validate`` checks a payload against a named
schema-catalog contract. ``accept`` is the canonical execution entry: it
rejects bare payloads and admits only a route-bound ``HandoffPointer`` whose
referenced payload (and any normalization receipt) has been verified, then
emits the resulting ``CurdPlan`` for execution. All three handlers validate
through shared, non-drifting paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    CURD_PLAN_SCHEMA_URI,
    SCHEMA_ROOT,
    ContractValidationError,
    TransitionError,
    canonical_bytes,
    canonical_digest,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
)

from easy_cheese.shared.publication import PointerNotFoundError, accept

__all__ = ["accept_main", "normalize_main", "validate_main"]



def _validate_against(raw: bytes | str, schema: str | type) -> None:
    """Validate raw against schema's catalog-supported version.

    The one call both verbs route through, so their validation cannot drift.
    """
    _ = validate_contract(raw, schema, supported_version_for(schema))


def _parse_normalize_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="normalize.py")
    _ = parser.add_argument("document", type=Path)
    _ = parser.add_argument("--invocation", required=True, type=Path)
    return parser.parse_args(argv)


def normalize_main(argv: list[str]) -> int:
    args = _parse_normalize_args(argv)
    document = cast(Path, args.document)
    invocation_path = cast(Path, args.invocation)
    try:
        document_raw = document.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {document}: {exc}", file=sys.stderr)
        return 1
    try:
        invocation_raw = invocation_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {invocation_path}: {exc}", file=sys.stderr)
        return 1
    try:
        invocation = cast(object, json.loads(invocation_raw))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid invocation JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(invocation, dict):
        print("ERROR: invocation must be a JSON object", file=sys.stderr)
        return 1
    invocation_payload = cast("dict[str, object]", invocation)
    try:
        artifact = normalize_agent_output(document_raw, invocation_payload)
        _validate_against(artifact.canonical_bytes, type(artifact.value))
    except ContractValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    wrapper = {
        "value": artifact.value,
        "digest": canonical_digest(artifact.value),
        "version": artifact.source_version,
    }
    _ = sys.stdout.buffer.write(canonical_bytes(wrapper))
    return 0


def _parse_validate_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="validate.py")
    _ = parser.add_argument("payload", type=Path)
    _ = parser.add_argument("--schema", required=True)
    return parser.parse_args(argv)


def validate_main(argv: list[str]) -> int:
    args = _parse_validate_args(argv)
    payload = cast(Path, args.payload)
    schema = cast(str, args.schema)
    try:
        raw = payload.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {payload}: {exc}", file=sys.stderr)
        return 1
    schema_uri = f"{SCHEMA_ROOT}/{schema}"
    try:
        _validate_against(raw, schema_uri)
    except KeyError:
        print(f"ERROR: unknown schema slug {schema!r}", file=sys.stderr)
        return 1
    except ContractValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: payload conforms to {schema!r}")
    return 0




def _parse_accept_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="accept.py")
    _ = parser.add_argument("pointer")
    return parser.parse_args(argv)


def accept_main(argv: list[str]) -> int:
    args = _parse_accept_args(argv)
    pointer_source = cast(str, args.pointer)
    try:
        accepted = accept(
            pointer_source,
            destination_phase="cook",
            payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        )
    except (ContractValidationError, TransitionError, PointerNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    wrapper = {
        "value": accepted.canonical.value,
        "digest": canonical_digest(accepted.canonical.value),
        "normalization_receipt": accepted.normalization_receipt,
    }
    _ = sys.stdout.buffer.write(canonical_bytes(wrapper))
    return 0
