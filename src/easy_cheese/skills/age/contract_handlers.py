"""This module handles the ``publish-review`` command for Age.

The command reads a host-authored envelope -- a writer-view review result
plus its evidence pool -- and sends it to
``easy_cheese.shared.publication.publish``. It binds the route to
``age -> cure`` and writes the resulting ``HandoffPointer`` as canonical JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    SCHEMA_ROOT,
    ContractValidationError,
    ReviewResult,
    TransitionError,
    canonical_bytes,
    supported_version_for,
)

from easy_cheese.shared.publication import PublicationError, publish

__all__ = ["publish_review_main"]

REVIEW_RESULT_SCHEMA_URI = f"{SCHEMA_ROOT}/review-result"


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


def _coverage_targets(view: dict[str, object]) -> tuple[str, ...] | None:
    """Return each coverage row's target from the view's own payload."""
    payload = view.get("payload")
    if not isinstance(payload, dict):
        print("ERROR: envelope view is missing a payload object", file=sys.stderr)
        return None
    coverage = cast("dict[str, object]", payload).get("coverage")
    if not isinstance(coverage, list):
        print("ERROR: envelope view payload is missing a coverage list", file=sys.stderr)
        return None
    targets: list[str] = []
    for row in cast("list[object]", coverage):
        if not isinstance(row, dict):
            print("ERROR: coverage row is missing a target", file=sys.stderr)
            return None
        target = cast("dict[str, object]", row).get("target")
        if not isinstance(target, str):
            print("ERROR: coverage row is missing a target", file=sys.stderr)
            return None
        targets.append(target)
    return tuple(targets)


def _parse_publish_review_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="publish-review.py")
    _ = parser.add_argument("--view", required=True, type=Path)
    _ = parser.add_argument("--slug", required=True)
    _ = parser.add_argument("--operation-id", required=True)
    _ = parser.add_argument("--artifact-root", required=True, type=Path)
    return parser.parse_args(argv)


def publish_review_main(argv: list[str]) -> int:
    args = _parse_publish_review_args(argv)
    view_path = cast(Path, args.view)
    slug = cast(str, args.slug)
    operation_id = cast(str, args.operation_id)
    artifact_root = cast(Path, args.artifact_root)
    envelope_raw = _read_text(view_path)
    if envelope_raw is None:
        return 1
    envelope = _as_json_object(envelope_raw, "envelope")
    if envelope is None:
        return 1
    view = envelope.get("view")
    if not isinstance(view, dict):
        print("ERROR: envelope is missing a view object", file=sys.stderr)
        return 1
    view = cast("dict[str, object]", view)
    evidence = envelope.get("evidence")
    if not isinstance(evidence, dict):
        print("ERROR: envelope is missing an evidence object", file=sys.stderr)
        return 1
    coverage_targets = _coverage_targets(view)
    if coverage_targets is None:
        return 1
    version = supported_version_for(ReviewResult)
    assert version is not None
    invocation: dict[str, object] = {
        "review_id": slug,
        "coverage_targets": coverage_targets,
        "evidence": evidence,
        "contract_version": {
            "schema_uri": version.schema_uri,
            "major": version.major,
            "minor": version.minor,
        },
    }
    document_raw = json.dumps(view)
    try:
        artifact = publish(
            document_raw,
            invocation,
            source_phase="age",
            destination_phase="cure",
            payload_schema_uri=REVIEW_RESULT_SCHEMA_URI,
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
