"""Handler for Mold's publish contract command.

``publish`` is the CLI entry point for the shared Mold-to-Cook publication
gateway: it reads an agent-authored curd-plan document and its host-owned
invocation, runs them through ``easy_cheese.shared.publication.publish``, and
prints the revealed ``HandoffPointer`` as canonical JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    CURD_PLAN_SCHEMA_URI,
    ContractValidationError,
    TransitionError,
    canonical_bytes,
)

from easy_cheese.shared.publication import (
    AmbiguousSyntaxRepairError,
    IdempotencyConflictError,
    UnrecoverableSyntaxError,
    publish,
)

__all__ = ["publish_main"]


def _parse_publish_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="publish.py")
    _ = parser.add_argument("document", type=Path)
    _ = parser.add_argument("--invocation", required=True, type=Path)
    _ = parser.add_argument("--operation-id", required=True)
    _ = parser.add_argument("--artifact-root", required=True, type=Path)
    return parser.parse_args(argv)


def publish_main(argv: list[str]) -> int:
    args = _parse_publish_args(argv)
    document = cast(Path, args.document)
    invocation_path = cast(Path, args.invocation)
    operation_id = cast(str, args.operation_id)
    artifact_root = cast(Path, args.artifact_root)
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
        artifact = publish(
            document_raw,
            invocation_payload,
            source_phase="mold",
            destination_phase="cook",
            payload_schema_uri=CURD_PLAN_SCHEMA_URI,
            operation_id=operation_id,
            artifact_root=artifact_root,
        )
    except (
        ContractValidationError,
        TransitionError,
        AmbiguousSyntaxRepairError,
        UnrecoverableSyntaxError,
        IdempotencyConflictError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _ = sys.stdout.buffer.write(canonical_bytes(artifact.pointer))
    return 0
