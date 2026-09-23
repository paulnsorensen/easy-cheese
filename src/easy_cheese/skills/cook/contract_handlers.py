"""Handlers for Cook contract, ingress, and preparation commands.

``normalize`` and ``validate`` remain the writer-contract utilities.  ``accept``
is the canonical execution entry for a validated MoldCookHandoff; ``prepare``
and ``resubmit`` classify input and recompute closed preparation outcomes
without dispatching agents or inventing approval evidence.
"""

from __future__ import annotations

from cyclopts import App
from types import SimpleNamespace
import hashlib
import json
import sys
from pathlib import Path
from typing import cast

from easy_cheese.shared import cli

from easy_cheese_schemas import (
    SCHEMA_ROOT,
    ContractValidationError,
    ArtifactRef,
    TransitionError,
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
from easy_cheese.shared.mold_cook_handoff import accept_mold_cook_handoff
from easy_cheese.shared.publication import PublicationError
from easy_cheese.shared.taste_test import read_spec_text
from easy_cheese.skills.cook.preparation import (
    CookHoldClearance,
    PreparationEvidence,
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


def _normalize(document: Path, invocation: Path) -> int:
    invocation_path = invocation
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
        invocation_data = cast(object, json.loads(invocation_raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"ERROR: invalid invocation JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(invocation_data, dict):
        print("ERROR: invocation must be a JSON object", file=sys.stderr)
        return 1
    invocation_payload = cast("dict[str, object]", invocation_data)
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


def _validate(payload: Path, schema: str) -> int:
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




def _source_from_args(args: SimpleNamespace) -> tuple[str | Path, str | None]:
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


def _path_option(args: SimpleNamespace, name: str) -> Path | None:
    return cast("Path | None", getattr(args, name, None))


def _hold_clearances(args: SimpleNamespace) -> tuple[CookHoldClearance, ...]:
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
        digest = _digest_of(content)
        clearances.append(
            CookHoldClearance(
                hold_id=hold_id,
                response_ref=ArtifactRef(
                    artifact_id=f"hold-clearance-{digest.removeprefix('sha256:')[:16]}",
                    role="dialogue",
                    uri=path.as_uri(),
                    digest=digest,
                    size_bytes=len(content),
                    media_type="application/json",
                ),
                response_text=cast(str, dialogue["response"]),
            )
        )
    return tuple(clearances)


def _evidence_from_args(
    args: SimpleNamespace,
    *,
    clearances: tuple[CookHoldClearance, ...] = (),
) -> PreparationEvidence:
    """Collect the host-owned evidence the command-line options name."""

    return PreparationEvidence(
        scope_approval=_path_option(args, "scope_approval"),
        plan_approval=_path_option(args, "plan_approval"),
        runner_approval=_path_option(args, "runner_approval"),
        planner_result=_path_option(args, "planner_result"),
        setup_authorization=_path_option(args, "setup_authorization"),
        setup_evidence=_path_option(args, "setup_evidence"),
        spec_binding=_path_option(args, "bound_spec"),
        clearances=clearances,
    )


def _prepare_from_args(args: SimpleNamespace) -> CookPreparationResult:
    source, explicit_kind = _source_from_args(args)
    return prepare(
        source,
        request_id=cast("str | None", args.request_id),
        repository_root=cast("str", args.repository_root),
        artifact_root=cast("str", args.artifact_root),
        mode=MoldCookMode(cast(str, args.mode)),
        explicit_kind=explicit_kind,
        evidence=_evidence_from_args(args),
    )


def _emit_preparation(result: object) -> int:
    try:
        validated = validate_preparation_result(result)
    except (ContractValidationError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _ = sys.stdout.buffer.write(canonical_bytes(validated))
    return 0


def _prepare(source: str | None = None, spec: Path | None = None, pointer: Path | None = None,
             slug: str | None = None, task: str | None = None, continuation: str | None = None,
             request_id: str | None = None, repository_root: str = ".", artifact_root: str = ".cheese/cook",
             mode: str = "full", scope_approval: Path | None = None, plan_approval: Path | None = None,
             runner_approval: Path | None = None, planner_result: Path | None = None,
             setup_authorization: Path | None = None, setup_evidence: Path | None = None,
             bound_spec: Path | None = None) -> int:
    args = SimpleNamespace(source=source, spec=spec, pointer=pointer, slug=slug, task=task,
        continuation=continuation, request_id=request_id, repository_root=repository_root,
        artifact_root=artifact_root, mode=mode, scope_approval=scope_approval,
        plan_approval=plan_approval, runner_approval=runner_approval, planner_result=planner_result,
        setup_authorization=setup_authorization, setup_evidence=setup_evidence, bound_spec=bound_spec,
        clear_hold=[])
    try:
        result = _prepare_from_args(args)
    except (ValueError, OSError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return _emit_preparation(result)


def _resubmit(previous: Path, source: str | None = None, repository_root: str | None = None,
              artifact_root: str | None = None, mode: str | None = None,
              scope_approval: Path | None = None, plan_approval: Path | None = None,
              runner_approval: Path | None = None, planner_result: Path | None = None,
              setup_authorization: Path | None = None, setup_evidence: Path | None = None,
              bound_spec: Path | None = None, clear_hold: list[str] | None = None) -> int:
    args = SimpleNamespace(source=source, repository_root=repository_root, artifact_root=artifact_root,
        mode=mode, scope_approval=scope_approval, plan_approval=plan_approval, runner_approval=runner_approval,
        planner_result=planner_result, setup_authorization=setup_authorization, setup_evidence=setup_evidence,
        bound_spec=bound_spec, clear_hold=clear_hold or [])
    try:
        result = resubmit(load_preparation_result(previous), source=source, repository_root=repository_root,
            artifact_root=artifact_root, mode=None if mode is None else MoldCookMode(mode),
            evidence=_evidence_from_args(args, clearances=_hold_clearances(args)))
    except (ContractValidationError, ValueError, OSError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return _emit_preparation(result)


def _accept(pointer: str, spec: Path | None = None, artifact_root: Path | None = None) -> int:
    try:
        accepted = accept_mold_cook_handoff(pointer, artifact_root=artifact_root)
        handoff = cast(MoldCookHandoff, accepted.canonical.value)
        if spec is not None and _digest_of(read_spec_text(spec).encode("utf-8")) != handoff.spec_ref.digest:
            raise ContractValidationError("--spec does not match the handoff's bound spec")
    except (ContractValidationError, PublicationError, TransitionError, OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _ = sys.stdout.buffer.write(canonical_bytes({"value": handoff, "digest": _digest_of(accepted.canonical.canonical_bytes), "normalization_receipt": accepted.normalization_receipt}))
    return 0


normalize_app = App(name="normalize")
_ = normalize_app.default(_normalize)
validate_app = App(name="validate")
_ = validate_app.default(_validate)
prepare_app = App(name="prepare")
_ = prepare_app.default(_prepare)
resubmit_app = App(name="resubmit")
_ = resubmit_app.default(_resubmit)
accept_app = App(name="accept")
_ = accept_app.default(_accept)

def _run(app: App, argv: list[str]) -> int:
    return cli.run(app, argv=argv)

def normalize_main(argv: list[str]) -> int: return _run(normalize_app, argv)
def validate_main(argv: list[str]) -> int: return _run(validate_app, argv)
def prepare_main(argv: list[str]) -> int: return _run(prepare_app, argv)
def resubmit_main(argv: list[str]) -> int: return _run(resubmit_app, argv)
def accept_main(argv: list[str]) -> int: return _run(accept_app, argv)
