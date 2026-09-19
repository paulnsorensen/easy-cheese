"""Handlers for Cook contract, ingress, and preparation commands.

``normalize`` and ``validate`` remain the writer-contract utilities.  ``accept``
is the canonical execution entry for a validated MoldCookHandoff; ``prepare``
and ``resubmit`` classify input and recompute closed preparation outcomes
without dispatching agents or inventing approval evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    SCHEMA_ROOT,
    ContractValidationError,
    ArtifactRef,
    canonical_bytes,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.mold_cook import (
    CookPreparationResult,
    MoldCookHandoff,
    MoldCookMode,
)
from easy_cheese.shared.publication import PublicationError, accept_mold_cook_handoff
from easy_cheese.shared.taste_test import read_spec_text
from easy_cheese.skills.cook.preparation import (
    CookHoldClearance,
    execute_accepted_handoff,
    load_preparation_result,
    prepare,
    resubmit,
    validate_preparation_result,
)

__all__ = [
    "accept_main",
    "execute_accepted_handoff",
    "normalize_main",
    "prepare_main",
    "resubmit_main",
    "validate_main",
]


def _digest_of(canonical: bytes) -> str:
    """Return the canonical digest without re-serializing the value."""
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _validate_against(raw: bytes | str, schema: str | type) -> None:
    """Validate raw against schema's catalog-supported version.

    The one call both verbs route through, so their validation cannot drift.
    """
    _ = validate_contract(raw, schema, supported_version_for(schema))


def normalize_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="normalize.py")
    _ = parser.add_argument("document", type=Path)
    _ = parser.add_argument("--invocation", required=True, type=Path)
    args = parser.parse_args(argv)
    document = cast(Path, args.document)
    invocation_path = cast(Path, args.invocation)
    # Read bytes, not text: the schema runtime converts a decode failure into a
    # ContractValidationError, while read_text would raise UnicodeDecodeError.
    try:
        document_raw = document.read_bytes()
    except OSError as exc:
        print(f"ERROR: cannot read {document}: {exc}", file=sys.stderr)
        return 1
    try:
        invocation_raw = invocation_path.read_bytes()
    except OSError as exc:
        print(f"ERROR: cannot read {invocation_path}: {exc}", file=sys.stderr)
        return 1
    try:
        invocation = cast(object, json.loads(invocation_raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
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
        "digest": _digest_of(artifact.canonical_bytes),
        "version": artifact.source_version,
    }
    _ = sys.stdout.buffer.write(canonical_bytes(wrapper))
    return 0


def validate_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="validate.py")
    _ = parser.add_argument("payload", type=Path)
    _ = parser.add_argument("--schema", required=True)
    args = parser.parse_args(argv)
    payload = cast(Path, args.payload)
    schema = cast(str, args.schema)
    try:
        raw = payload.read_bytes()
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


def _source_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    _ = group.add_argument("--spec", type=Path)
    _ = group.add_argument("--pointer", type=Path)
    _ = group.add_argument("--slug")
    _ = group.add_argument("--task")
    _ = group.add_argument("--continuation")


def _source_from_args(args: argparse.Namespace) -> tuple[str | Path, str | None]:
    positional = cast("str | None", getattr(args, "source", None))
    selected: tuple[tuple[str, str | Path | None], ...] = (
        ("spec", cast("Path | None", getattr(args, "spec", None))),
        ("pointer", cast("Path | None", getattr(args, "pointer", None))),
        ("slug", cast("str | None", getattr(args, "slug", None))),
        ("task", cast("str | None", getattr(args, "task", None))),
        ("continuation", cast("str | None", getattr(args, "continuation", None))),
    )
    present = tuple((kind, value) for kind, value in selected if value is not None)
    if positional is not None and present:
        raise ValueError(
            "source positional argument cannot be combined with an explicit input option"
        )
    if len(present) > 1:
        raise ValueError("only one explicit input option may be supplied")
    if present:
        kind, value = present[0]
        return value, kind
    if positional is None:
        raise ValueError("Cook preparation requires an input source")
    return positional, None


def _path_option(args: argparse.Namespace, name: str) -> Path | None:
    return cast("Path | None", getattr(args, name, None))


def _setup_authorization(args: argparse.Namespace) -> Path | None:
    """Return the host-retained authorization path for strict resolution."""

    return _path_option(args, "setup_authorization")


def _hold_clearances(args: argparse.Namespace) -> tuple[CookHoldClearance, ...]:
    clearances: list[CookHoldClearance] = []
    for value in cast("list[str]", getattr(args, "clear_hold", ())):
        hold_id, separator, raw_path = value.partition("=")
        if not separator or not hold_id or not raw_path:
            raise ValueError("--clear-hold requires HOLD_ID=DIALOGUE_JSON")
        path = Path(raw_path).expanduser().resolve()
        content = path.read_bytes()
        try:
            parsed = cast(object, json.loads(content))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"hold clearance {path} is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"hold clearance {path} must be a JSON object")
        dialogue = cast("dict[str, object]", parsed)
        if not isinstance(dialogue.get("response"), str):
            raise ValueError(f"hold clearance {path} must contain a string response")
        clearances.append(
            CookHoldClearance(
                hold_id=hold_id,
                response_ref=ArtifactRef(
                    artifact_id=f"hold-clearance-{hashlib.sha256(content).hexdigest()[:16]}",
                    role="dialogue",
                    uri=path.as_uri(),
                    digest=f"sha256:{hashlib.sha256(content).hexdigest()}",
                    size_bytes=len(content),
                    media_type="application/json",
                ),
                response_text=cast(str, dialogue["response"]),
            )
        )
    return tuple(clearances)


def _prepare_from_args(args: argparse.Namespace) -> CookPreparationResult:
    source, explicit_kind = _source_from_args(args)
    return prepare(
        source,
        request_id=cast("str | None", args.request_id),
        repository_root=cast("str", args.repository_root),
        artifact_root=cast("str", args.artifact_root),
        mode=MoldCookMode(cast(str, args.mode)),
        explicit_kind=explicit_kind,
        scope_approval=_path_option(args, "scope_approval"),
        plan_approval=_path_option(args, "plan_approval"),
        runner_approval=_path_option(args, "runner_approval"),
        planner_result=_path_option(args, "planner_result"),
        setup_authorization=_setup_authorization(args),
        setup_evidence=_path_option(args, "setup_evidence"),
        spec_binding=_path_option(args, "bound_spec"),
    )


def _emit_preparation(result: object) -> int:
    try:
        validated = validate_preparation_result(result)
    except (ContractValidationError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _ = sys.stdout.buffer.write(canonical_bytes(validated))
    return 0


def prepare_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="prepare.py")
    _ = parser.add_argument("source", nargs="?")
    _source_options(parser)
    _ = parser.add_argument("--request-id")
    _ = parser.add_argument("--repository-root", default=".")
    _ = parser.add_argument("--artifact-root", default=".cheese/cook")
    _ = parser.add_argument("--mode", choices=("full", "light"), default="full")
    _ = parser.add_argument("--scope-approval", type=Path)
    _ = parser.add_argument("--plan-approval", type=Path)
    _ = parser.add_argument("--runner-approval", type=Path)
    _ = parser.add_argument("--planner-result", type=Path)
    _ = parser.add_argument("--setup-authorization", type=Path)
    _ = parser.add_argument("--setup-evidence", type=Path)
    _ = parser.add_argument("--bound-spec", type=Path)
    try:
        result = _prepare_from_args(parser.parse_args(argv))
    except (ValueError, OSError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return _emit_preparation(result)


def resubmit_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="resubmit.py")
    _ = parser.add_argument("previous", type=Path)
    _ = parser.add_argument("--source")
    _ = parser.add_argument("--repository-root", default=None)
    _ = parser.add_argument("--artifact-root", default=None)
    _ = parser.add_argument("--mode", choices=("full", "light"), default=None)
    _ = parser.add_argument("--scope-approval", type=Path)
    _ = parser.add_argument("--plan-approval", type=Path)
    _ = parser.add_argument("--runner-approval", type=Path)
    _ = parser.add_argument("--planner-result", type=Path)
    _ = parser.add_argument("--setup-authorization", type=Path)
    _ = parser.add_argument("--setup-evidence", type=Path)
    _ = parser.add_argument("--bound-spec", type=Path)
    _ = parser.add_argument(
        "--clear-hold",
        action="append",
        default=[],
        metavar="HOLD_ID=DIALOGUE_JSON",
    )
    args = parser.parse_args(argv)
    previous_path = cast(Path, args.previous)
    mode = cast("str | None", args.mode)
    try:
        previous = load_preparation_result(
            previous_path,
            artifact_root=cast(str, args.artifact_root),
        )
        result = resubmit(
            previous,
            source=cast("str | None", args.source),
            repository_root=cast(str, args.repository_root),
            artifact_root=cast(str, args.artifact_root),
            mode=None if mode is None else MoldCookMode(mode),
            scope_approval=_path_option(args, "scope_approval"),
            plan_approval=_path_option(args, "plan_approval"),
            runner_approval=_path_option(args, "runner_approval"),
            planner_result=_path_option(args, "planner_result"),
            setup_authorization=_setup_authorization(args),
            setup_evidence=_path_option(args, "setup_evidence"),
            spec_binding=_path_option(args, "bound_spec"),
            clearances=_hold_clearances(args),
        )
    except (ContractValidationError, ValueError, OSError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return _emit_preparation(result)


def accept_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="accept.py")
    _ = parser.add_argument("pointer")
    _ = parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help="optional identity assertion; it cannot replace the handoff binding",
    )
    _ = parser.add_argument("--artifact-root", type=Path, default=None)
    args = parser.parse_args(argv)
    pointer_source = cast(str, args.pointer)
    spec_path = cast("Path | None", args.spec)
    artifact_root = cast("Path | None", args.artifact_root)
    try:
        accepted = accept_mold_cook_handoff(
            pointer_source,
            artifact_root=artifact_root,
        )
        handoff = cast(MoldCookHandoff, accepted.canonical.value)
        if spec_path is not None:
            spec_raw = read_spec_text(spec_path).encode("utf-8")
            if _digest_of(spec_raw) != handoff.spec_ref.digest:
                raise ContractValidationError(
                    "--spec does not match the handoff's bound spec"
                )
    except (
        ContractValidationError,
        PublicationError,
        OSError,
        UnicodeDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    wrapper = {
        "value": handoff,
        "digest": _digest_of(accepted.canonical.canonical_bytes),
        "normalization_receipt": accepted.normalization_receipt,
    }
    _ = sys.stdout.buffer.write(canonical_bytes(wrapper))
    return 0
