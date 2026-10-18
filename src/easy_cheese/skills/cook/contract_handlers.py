"""Cook writer-contract command handlers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast
import fromargs

from easy_cheese_schemas import (
    SCHEMA_ROOT,
    ContractValidationError,
    canonical_bytes,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
)

__all__ = ["normalize_main", "validate_main"]


def _digest_of(canonical: bytes) -> str:
    """Return the canonical digest without re-serializing the value."""
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _validate_against(raw: bytes | str, schema: str | type) -> None:
    """Validate raw against schema's catalog-supported version.

    The one call both verbs route through, so their validation cannot drift.
    """
    _ = validate_contract(raw, schema, supported_version_for(schema))


def normalize(document: str, *, invocation: str) -> dict[str, object]:
    """Normalize a typed contract payload on the host.

    Parameters
    ----------
    document
        Path to the raw agent-output document to normalize.
    invocation
        Path to the invocation JSON that supplies plan identity and version.
    """
    document_path = Path(document)
    invocation_path = Path(invocation)
    # Read bytes, not text: the schema runtime converts a decode failure into a
    # ContractValidationError, while read_text would raise UnicodeDecodeError.
    try:
        document_raw = document_path.read_bytes()
    except OSError as exc:
        raise fromargs.CliError(f"cannot read {document_path}: {exc}", exit_code=2) from exc
    try:
        invocation_raw = invocation_path.read_bytes()
    except OSError as exc:
        raise fromargs.CliError(f"cannot read {invocation_path}: {exc}", exit_code=2) from exc
    try:
        invocation_parsed = cast(object, json.loads(invocation_raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise fromargs.CliError(f"invalid invocation JSON: {exc}", exit_code=2) from exc
    if not isinstance(invocation_parsed, dict):
        raise fromargs.CliError("invocation must be a JSON object", exit_code=2)
    invocation_payload = cast("dict[str, object]", invocation_parsed)
    try:
        artifact = normalize_agent_output(document_raw, invocation_payload)
        _validate_against(artifact.canonical_bytes, type(artifact.value))
    except ContractValidationError as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    wrapper = {
        "value": artifact.value,
        "digest": _digest_of(artifact.canonical_bytes),
        "version": artifact.source_version,
    }
    return cast("dict[str, object]", json.loads(canonical_bytes(wrapper)))


def validate(payload: str, *, schema: str) -> str:
    """Validate a typed contract payload against its registered schema.

    Parameters
    ----------
    payload
        Path to the JSON payload to validate.
    schema
        Schema slug to validate against, under SCHEMA_ROOT.
    """
    payload_path = Path(payload)
    try:
        raw = payload_path.read_bytes()
    except OSError as exc:
        raise fromargs.CliError(f"cannot read {payload_path}: {exc}", exit_code=2) from exc
    schema_uri = f"{SCHEMA_ROOT}/{schema}"
    try:
        _validate_against(raw, schema_uri)
    except KeyError as exc:
        raise fromargs.CliError(f"unknown schema slug {schema!r}", exit_code=2) from exc
    except ContractValidationError as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    return f"OK: payload conforms to {schema!r}"


def _build_normalize_app() -> fromargs.App:
    return fromargs.App("normalize", help_formatter="plain", default_command=normalize)


def _build_validate_app() -> fromargs.App:
    return fromargs.App("validate", help_formatter="plain", default_command=validate)



def normalize_main(argv: list[str] | None = None) -> int:
    return _build_normalize_app().run(argv)


def validate_main(argv: list[str] | None = None) -> int:
    return _build_validate_app().run(argv)
