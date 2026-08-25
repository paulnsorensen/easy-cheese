"""Cook's declarative bundle commands and canonical consumer boundary."""

# Transitional shared modules are imported after a source-tree path fallback.
# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

_SHARED_SOURCE = Path(__file__).resolve().parents[4] / "shared" / "scripts"
if _SHARED_SOURCE.is_dir() and str(_SHARED_SOURCE) not in sys.path:
    sys.path.insert(0, str(_SHARED_SOURCE))

import cli as _cli
import findings_cli as _findings_cli
import gates_cli as _gates_cli
import handoff_cli as _handoff_cli
import html_report_cli as _html_report_cli
import paths_cli as _paths_cli
import read_handoff_slug as _read_handoff_slug
import slugify as _slugify
import worktree as _worktree
import write_handoff_artifact as _write_handoff_artifact

from easy_cheese.shared.artifact_path import main as _artifact_path_main
from easy_cheese.shared.bundle_commands import bundle_command, dispatch
from easy_cheese.shared.handoffs import (
    AcceptedArtifact,
    HandoffError,
    HandoffPointer,
    accept,
    canonical_bytes,
    pointer_from_mapping,
    read_nofollow_file,
)
from easy_cheese_schemas.schema_runtime import (
    SCHEMA_ROOT,
    ContractValidationError,
    canonical_digest,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
)


def contract_accept(pointer: HandoffPointer, expected_root: Path) -> AcceptedArtifact:
    """Accept a route-bound canonical Mold-to-Cook handoff."""
    return accept(pointer, expected_root)


def execute(pointer: HandoffPointer, expected_root: Path) -> Any:
    """Return only the canonical plan produced by full pointer acceptance."""
    return contract_accept(pointer, expected_root).canonical


def _read_pointer(path: Path) -> HandoffPointer:
    if path.is_symlink():
        raise HandoffError("pointer file must not be a symlink")
    data = read_nofollow_file(path.parent, path.name)
    raw = json.loads(data)
    if not isinstance(raw, dict):
        raise HandoffError("pointer must be an object")
    pointer = pointer_from_mapping(raw)
    if canonical_bytes(pointer) != data:
        raise HandoffError("pointer must use canonical JSON")
    if path.parent.is_symlink():
        raise HandoffError("pointer operation directory must not be a symlink")
    operation_root = path.parent.parent.resolve()
    payload = urlsplit(pointer.payload.uri)
    if payload.scheme != "file" or payload.netloc not in {"", "localhost"}:
        raise HandoffError("pointer payload must use a local file URI")
    expected_payload = operation_root / "payloads" / f"{pointer.operation_id}.json"
    if Path(unquote(payload.path)).resolve() != expected_payload:
        raise HandoffError("pointer payload escapes the operation root")
    expected = (operation_root / "pointers" / f"{pointer.operation_id}.json").resolve()
    if path.resolve() != expected:
        raise HandoffError("pointer path does not match its operation id")
    return pointer


def _shared_command(module: Any, argv: list[str]) -> int:
    return _cli.run(module._setup, argv=argv)


@bundle_command("artifact-path")
def artifact_path_command(argv: list[str]) -> int:
    """Resolve a durable or transient artifact path."""
    return _artifact_path_main(argv)


@bundle_command("worktree")
def worktree_command(argv: list[str]) -> int:
    """Create, harvest, or tear down a curd worktree."""
    return _cli.run(_worktree._setup, argv=argv)


@bundle_command("slugify")
def slugify_command(argv: list[str]) -> int:
    """Derive a bounded task slug and artifact path."""
    return _shared_command(_slugify, argv)


@bundle_command("write_handoff_artifact")
def write_handoff_artifact_command(argv: list[str]) -> int:
    """Write a canonical phase handoff artifact atomically."""
    return _shared_command(_write_handoff_artifact, argv)


@bundle_command("read_handoff_slug")
def read_handoff_slug_command(argv: list[str]) -> int:
    """Read and validate a canonical handoff preamble."""
    return _shared_command(_read_handoff_slug, argv)


@bundle_command("findings_cli")
def findings_command(argv: list[str]) -> int:
    """Render or select structured review findings."""
    return _shared_command(_findings_cli, argv)


@bundle_command("gates_cli")
def gates_command(argv: list[str]) -> int:
    """Classify readiness from the quality scoreboard."""
    return _shared_command(_gates_cli, argv)


@bundle_command("paths_cli")
def paths_command(argv: list[str]) -> int:
    """Resolve and validate workflow artifact paths."""
    return _shared_command(_paths_cli, argv)


@bundle_command("handoff_cli")
def handoff_command(argv: list[str]) -> int:
    """Render, parse, or dispatch a canonical handoff preamble."""
    return _shared_command(_handoff_cli, argv)


@bundle_command("render_html")
def render_html_command(argv: list[str]) -> int:
    """Render a Markdown artifact as a self-contained HTML report."""
    return _shared_command(_html_report_cli, argv)


@bundle_command("normalize")
def normalize_command(argv: list[str]) -> int:
    """Normalize an agent writer view through the canonical schema runtime."""
    parser = argparse.ArgumentParser(prog="cook normalize")
    parser.add_argument("document", type=Path)
    parser.add_argument("--invocation", required=True, type=Path)
    arguments = parser.parse_args(argv)
    document_raw = arguments.document.read_text(encoding="utf-8")
    invocation = json.loads(arguments.invocation.read_text(encoding="utf-8"))
    if not isinstance(invocation, dict):
        raise ValueError("invocation must be a JSON object")
    artifact = normalize_agent_output(document_raw, invocation)
    validate_contract(
        artifact.canonical_bytes,
        type(artifact.value),
        supported_version_for(type(artifact.value)),
    )
    wrapper = {
        "value": artifact.value,
        "digest": canonical_digest(artifact.value),
        "version": artifact.source_version,
    }
    sys.stdout.buffer.write(canonical_bytes(wrapper))
    sys.stdout.buffer.write(b"\n")
    return 0


@bundle_command("validate")
def validate_command(argv: list[str]) -> int:
    """Validate a canonical payload against one registered schema."""
    parser = argparse.ArgumentParser(prog="cook validate")
    parser.add_argument("payload", type=Path)
    parser.add_argument("--schema", required=True)
    arguments = parser.parse_args(argv)
    schema = f"{SCHEMA_ROOT}/{arguments.schema}"
    try:
        supported = supported_version_for(schema)
    except KeyError as exc:
        raise ValueError(f"unknown schema slug {arguments.schema!r}") from exc
    validate_contract(arguments.payload.read_bytes(), schema, supported)
    print(f"OK: payload conforms to {arguments.schema!r}")
    return 0


@bundle_command("contract")
def contract_command(argv: list[str]) -> int:
    """Accept and expose only a verified canonical Mold handoff pointer."""
    parser = argparse.ArgumentParser(prog="cook contract")
    operations = parser.add_subparsers(dest="operation", required=True)
    accept_parser = operations.add_parser("accept")
    accept_parser.add_argument("--pointer", required=True, type=Path)
    arguments = parser.parse_args(argv)
    pointer = _read_pointer(arguments.pointer)
    accepted = contract_accept(pointer, arguments.pointer.parent.parent)
    sys.stdout.buffer.write(canonical_bytes(accepted.canonical))
    sys.stdout.buffer.write(b"\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return dispatch(__name__, sys.argv[1:] if argv is None else argv)
    except (
        ContractValidationError,
        HandoffError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
