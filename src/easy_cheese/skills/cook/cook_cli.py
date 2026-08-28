"""CLI verbs for the cook skill: normalize writer-view JSON into a canonical
host artifact, and validate a payload against a named schema-catalog
contract. Both verbs resolve their target schema and validate through one
shared path so they cannot drift apart from each other.

normalize's document argument is the AgentWriterView JSON (`kind` + `payload`)
an agent wrote. The separate --invocation file supplies the host-owned data
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
    SCHEMA_ROOT,
    ContractValidationError,
    canonical_bytes,
    canonical_digest,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
)

COMMANDS = {"normalize", "validate"}


def _command_of(argv: list[str]) -> tuple[str | None, list[str]]:
    """The verb, read from the name cook_cli was invoked as, then from argv.

    The bundle gives each verb its own entry point into this module and
    rewrites `argv[0]` to the verb name; running the module directly leaves
    `argv[0]` as the file, so the verb is looked for in `argv[1]` next.
    """
    invoked = Path(argv[0]).name if argv else ""
    if invoked.endswith(".py"):
        invoked = invoked[: -len(".py")]
    if invoked in COMMANDS:
        return invoked, list(argv[1:])
    if len(argv) >= 2 and argv[1] in COMMANDS:
        return argv[1], list(argv[2:])
    return None, []


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


def _run_normalize(argv: list[str]) -> int:
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


def _run_validate(argv: list[str]) -> int:
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


_RUNNERS = {"normalize": _run_normalize, "validate": _run_validate}


def normalize_main(argv: list[str]) -> int:
    return _run_normalize(argv)


def validate_main(argv: list[str]) -> int:
    return _run_validate(argv)


def main(argv: list[str]) -> int:
    command, rest = _command_of(argv)
    if command is None:
        print("ERROR: expected a 'normalize' or 'validate' command", file=sys.stderr)
        return 2
    return _RUNNERS[command](rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
