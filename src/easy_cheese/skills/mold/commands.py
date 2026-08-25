"""Mold's declarative bundle commands and canonical producer boundary."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from easy_cheese.shared.artifact_path import main as _artifact_path_main
from easy_cheese.shared.bundle_commands import bundle_command, dispatch
from easy_cheese.shared.handoffs import (
    HandoffError,
    InvocationContext,
    LegacyHandoff,
    PublishedArtifact,
    canonical_bytes,
    migrate,
    publish,
    publish_writer_text,
)
from easy_cheese.skills.mold.gate_graph import main as _gate_graph_main
from easy_cheese.skills.mold.legacy_validate_spec import validate as _validate_spec
from easy_cheese_schemas.contracts import (
    AgentWriterView,
    ArtifactRef,
    ContractVersion,
)


def contract_publish(
    writer_view: AgentWriterView,
    invocation: InvocationContext,
    destination: str,
    operation_id: str,
) -> PublishedArtifact:
    """Publish a typed writer view as a canonical Mold-to-Cook handoff."""
    return publish(writer_view, invocation, destination, operation_id)


def validate_spec(value: Any) -> Any:
    if isinstance(value, Path):
        errors = _validate_spec(value)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(f"OK: {value} is a valid mold spec")
        return 0
    if not isinstance(value, (str, dict)):
        raise ValueError("spec must be text or object")
    return value


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _version(value: object, label: str) -> ContractVersion:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_uri",
        "major",
        "minor",
    }:
        raise ValueError(f"invalid {label}")
    if not all(isinstance(value[name], str) for name in value):
        raise ValueError(f"{label} fields must be strings")
    return ContractVersion(**value)


def _artifact(value: object) -> ArtifactRef:
    fields = {
        "artifact_id",
        "role",
        "uri",
        "digest",
        "size_bytes",
        "media_type",
        "schema_uri",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError("invalid invocation artifact reference")
    return ArtifactRef(**value)


def invocation_from_mapping(value: object) -> InvocationContext:
    fields = {
        "root",
        "contract_version",
        "plan_id",
        "revision",
        "request_digest",
        "artifacts",
        "lineages",
        "parent_plan_ref",
        "source_phase",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError("invocation context has unknown or missing fields")
    if not isinstance(value["root"], str) or not isinstance(value["plan_id"], str):
        raise ValueError("invocation root and plan_id must be strings")
    if not isinstance(value["revision"], int) or isinstance(value["revision"], bool):
        raise ValueError("invocation revision must be an integer")
    if not isinstance(value["request_digest"], str) or not isinstance(
        value["source_phase"], str
    ):
        raise ValueError("invocation digest and source_phase must be strings")
    artifacts_raw = value["artifacts"]
    if not isinstance(artifacts_raw, Mapping) or not all(
        isinstance(key, str) for key in artifacts_raw
    ):
        raise ValueError("invocation artifacts must be an object")
    if not isinstance(value["lineages"], Mapping):
        raise ValueError("invocation lineages must be an object")
    return InvocationContext(
        root=Path(value["root"]),
        contract_version=_version(value["contract_version"], "contract_version"),
        plan_id=value["plan_id"],
        revision=value["revision"],
        request_digest=value["request_digest"],
        artifacts={key: _artifact(item) for key, item in artifacts_raw.items()},
        lineages=value["lineages"],
        parent_plan_ref=value["parent_plan_ref"],
        source_phase=value["source_phase"],
    )


def legacy_handoff_from_mapping(value: object) -> LegacyHandoff:
    fields = {"payload", "source_schema_uri", "source_version", "invocation"}
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError("legacy handoff has unknown or missing fields")
    if not isinstance(value["payload"], Mapping) or not isinstance(
        value["source_schema_uri"], str
    ):
        raise ValueError("legacy payload must be an object with a schema URI")
    return LegacyHandoff(
        payload=value["payload"],
        source_schema_uri=value["source_schema_uri"],
        source_version=_version(value["source_version"], "legacy source_version"),
        invocation=invocation_from_mapping(value["invocation"]),
    )


@bundle_command("artifact-path")
def artifact_path_command(argv: list[str]) -> int:
    """Resolve a durable or transient artifact path."""
    return _artifact_path_main(argv)


@bundle_command("curd-count")
def curd_count_command(argv: list[str]) -> int:
    """Count a validated Mold spec's semantic curds."""
    return importlib.import_module("curd_count").main(argv)


@bundle_command("gate-graph")
def gate_graph_command(argv: list[str]) -> int:
    """Render the Mold handshake gate graph."""
    return _gate_graph_main(argv)


@bundle_command("render_html")
def render_html_command(argv: list[str]) -> int:
    """Render a Markdown artifact as a self-contained HTML report."""
    cli = importlib.import_module("cli")
    renderer = importlib.import_module("html_report_cli")
    return cli.run(renderer._setup, argv=argv)


@bundle_command("taste-test")
def taste_test_command(argv: list[str]) -> int:
    """Validate a digest-bound Mold fork-coherence verdict."""
    return importlib.import_module("taste_test").main(argv)


@bundle_command("validate-spec")
def validate_spec_command(argv: list[str]) -> int:
    """Validate a Mold specification."""
    parser = argparse.ArgumentParser(prog="mold validate-spec")
    parser.add_argument("spec_path", type=Path)
    arguments = parser.parse_args(argv)
    return int(validate_spec(arguments.spec_path))


@bundle_command("contract")
def contract_command(argv: list[str]) -> int:
    """Publish or migrate a canonical Mold-to-Cook handoff."""
    parser = argparse.ArgumentParser(prog="mold contract")
    operations = parser.add_subparsers(dest="operation", required=True)
    publish_parser = operations.add_parser("publish")
    publish_parser.add_argument("--writer-view", required=True, type=Path)
    publish_parser.add_argument("--invocation", required=True, type=Path)
    publish_parser.add_argument("--destination", default="cook")
    publish_parser.add_argument("--operation-id", required=True)
    migrate_parser = operations.add_parser("migrate")
    migrate_parser.add_argument("--legacy", required=True, type=Path)
    migrate_parser.add_argument("--operation-id", required=True)
    arguments = parser.parse_args(argv)
    if arguments.operation == "publish":
        invocation = invocation_from_mapping(_read_json(arguments.invocation))
        result = publish_writer_text(
            arguments.writer_view.read_text(encoding="utf-8"),
            invocation,
            arguments.destination,
            arguments.operation_id,
        )
    else:
        result = migrate(
            legacy_handoff_from_mapping(_read_json(arguments.legacy)),
            arguments.operation_id,
        )
    sys.stdout.buffer.write(canonical_bytes(result.pointer))
    sys.stdout.buffer.write(b"\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return dispatch(__name__, sys.argv[1:] if argv is None else argv)
    except (HandoffError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
