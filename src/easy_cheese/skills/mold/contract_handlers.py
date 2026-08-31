"""Handlers for Mold's publish and migrate contract commands.

``publish`` is the CLI entry point for the shared Mold-to-Cook publication
gateway: it reads an agent-authored curd-plan document and its host-owned
invocation, runs them through ``easy_cheese.shared.publication.publish``, and
prints the revealed ``HandoffPointer`` as canonical JSON.

``migrate`` is the CLI entry point for exact-version legacy migration: it
reads a persisted legacy artifact and its declared source schema/version,
runs them through ``easy_cheese.shared.migrate.migrate``, and prints the
revealed ``HandoffPointer`` as canonical JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    CURD_PLAN_SCHEMA_URI,
    AdapterSunsetError,
    ContractValidationError,
    TransitionError,
    canonical_bytes,
)

from easy_cheese.shared.migrate import UnsupportedLegacySourceError, migrate
from easy_cheese.shared.publication import PublicationError, publish

__all__ = ["migrate_main", "publish_main"]


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
        PublicationError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _ = sys.stdout.buffer.write(canonical_bytes(artifact.pointer))
    return 0


def _parse_migrate_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="migrate.py")
    _ = parser.add_argument("document", type=Path)
    _ = parser.add_argument("--source-schema-uri", required=True)
    _ = parser.add_argument("--source-major", required=True)
    _ = parser.add_argument("--source-minor", required=True)
    _ = parser.add_argument("--source-phase", default="mold")
    _ = parser.add_argument("--destination-phase", default="cook")
    _ = parser.add_argument("--operation-id", required=True)
    _ = parser.add_argument("--artifact-root", required=True, type=Path)
    return parser.parse_args(argv)


def migrate_main(argv: list[str]) -> int:
    args = _parse_migrate_args(argv)
    document = cast(Path, args.document)
    source_schema_uri = cast(str, args.source_schema_uri)
    source_major = cast(str, args.source_major)
    source_minor = cast(str, args.source_minor)
    source_phase = cast(str, args.source_phase)
    destination_phase = cast(str, args.destination_phase)
    operation_id = cast(str, args.operation_id)
    artifact_root = cast(Path, args.artifact_root)
    try:
        document_raw = document.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {document}: {exc}", file=sys.stderr)
        return 1
    try:
        legacy_payload = cast(object, json.loads(document_raw))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid legacy document JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(legacy_payload, dict):
        print("ERROR: legacy document must be a JSON object", file=sys.stderr)
        return 1
    legacy_mapping = cast("dict[str, object]", legacy_payload)
    try:
        artifact = migrate(
            legacy_mapping,
            source_schema_uri=source_schema_uri,
            source_major=source_major,
            source_minor=source_minor,
            source_phase=source_phase,
            destination_phase=destination_phase,
            operation_id=operation_id,
            artifact_root=artifact_root,
        )
    except (
        ContractValidationError,
        TransitionError,
        UnsupportedLegacySourceError,
        PublicationError,
        AdapterSunsetError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _ = sys.stdout.buffer.write(canonical_bytes(artifact.pointer))
    return 0
