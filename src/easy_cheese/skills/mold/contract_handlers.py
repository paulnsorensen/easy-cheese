"""This module handles the ``publish`` and ``migrate`` commands for Mold.

The ``publish`` command reads a curd plan and its host invocation.
It sends both values to ``easy_cheese.shared.publication.publish``.

The ``migrate`` command reads a legacy artifact and its source schema version.
It sends the artifact to ``easy_cheese.shared.migrate.migrate``.

Both commands bind the route to ``mold -> cook``. A caller cannot select a
phase. Both write the resulting ``HandoffPointer`` as canonical JSON.
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


def _read_text(path: Path) -> str | None:
    """Return the file text, or ``None`` after it reports the read failure."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        return None


def _as_json_object(raw: str, label: str) -> dict[str, object] | None:
    """Return the parsed JSON object, or ``None`` after it reports the reason."""
    try:
        parsed = cast(object, json.loads(raw))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid {label} JSON: {exc}", file=sys.stderr)
        return None
    if not isinstance(parsed, dict):
        print(f"ERROR: {label} must be a JSON object", file=sys.stderr)
        return None
    return cast("dict[str, object]", parsed)


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
    document_raw = _read_text(document)
    if document_raw is None:
        return 1
    invocation_raw = _read_text(invocation_path)
    if invocation_raw is None:
        return 1
    invocation_payload = _as_json_object(invocation_raw, "invocation")
    if invocation_payload is None:
        return 1
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
    _ = parser.add_argument("--operation-id", required=True)
    _ = parser.add_argument("--artifact-root", required=True, type=Path)
    return parser.parse_args(argv)


def migrate_main(argv: list[str]) -> int:
    args = _parse_migrate_args(argv)
    document = cast(Path, args.document)
    source_schema_uri = cast(str, args.source_schema_uri)
    source_major = cast(str, args.source_major)
    source_minor = cast(str, args.source_minor)
    operation_id = cast(str, args.operation_id)
    artifact_root = cast(Path, args.artifact_root)
    document_raw = _read_text(document)
    if document_raw is None:
        return 1
    legacy_mapping = _as_json_object(document_raw, "legacy document")
    if legacy_mapping is None:
        return 1
    try:
        artifact = migrate(
            legacy_mapping,
            source_schema_uri=source_schema_uri,
            source_major=source_major,
            source_minor=source_minor,
            source_phase="mold",
            destination_phase="cook",
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
