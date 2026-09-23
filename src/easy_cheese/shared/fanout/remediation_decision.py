#!/usr/bin/env python3
"""Deterministic fan-remediation router: one event in, one state out.

`run_fan` owns the `Cook -> Age` and `Press -> Age` entry transitions and
publishes the initial `awaiting_review` state. After the first Age starts, this
command is the sole authority for every later fan transition. It accepts exactly
one event -- a Review or a Cure -- validates its inputs, computes the next state
with the pure decision core, publishes one immutable `RemediationState`
artifact, reloads and validates it, then emits the verdict.

Inputs:

    --state <path>            The current RemediationState artifact. The router
                              publishes the next state back to this path.
    --event {review,cure}     Which event to apply.
    --request-digest <sha256:...>
                              Required. The digest of the host request that
                              produced the event. The router rejects an event
                              whose identity binds a different request.
    --review <path>           Required for a review event: the ReviewResult.
    --cure-result <path>      Required for a cure event: the
                              RemediationCureObservation the Cure agent authored.
    --gate-evidence <path>    Optional, repeatable. A host-side digest
                              cross-check: each path's bytes must match the
                              digest the cure observation claims for the gate
                              evidence at the same position. A mismatch fails
                              closed -- an agent-declared digest that does not
                              match real bytes is an untrustworthy claim.

Output (JSON), matching mini-spec Sec13:

    {
      "action": "age | cure | complete | remediate | blocked",
      "next_phase": "age | cure | mold | null",
      "scope": {"kind": "curd | postmerge", "id": "..."},
      "cursor": "awaiting_review | awaiting_cure | terminal",
      "state_ref": "<published state path>",
      "progress": true,
      "reason": null
    }

The router publishes, reloads, and validates the state before it emits a
verdict. If publication or reload fails, it stops closed and dispatches no next
phase (raises, never emits a soft-fail verdict).
"""
from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Protocol, cast
from cyclopts import App, Parameter

from easy_cheese_schemas import (
    ArtifactRef,
    ContractValidationError,
    RemediationCureObservation,
    RemediationState,
    ReviewResult,
    supported_version_for,
    validate_contract,
)

from easy_cheese.shared import cli
from easy_cheese.shared.fanout.remediation import (
    Verdict,
    validate_event_identity,
    decide_cure,
    decide_review,
)
from easy_cheese.shared.fanout.remediation_store import (
    StateStoreError,
    load_state,
    publish_state,
)
from easy_cheese.shared.remediation_artifacts import build_artifact_ref, bytes_digest


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise cli.CliError(f"cannot read {path}: {exc}") from exc


def _load_contract(path: Path, schema: type, context: str) -> tuple[object, bytes]:
    raw = _read_bytes(path)
    try:
        value = validate_contract(raw, schema, supported_version_for(schema)).value
    except ContractValidationError as exc:
        raise cli.contract_error(exc, context=context) from exc
    return value, raw


_REQUEST_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _load_state(state_path: Path) -> RemediationState:
    """Load the state through the store. Exit 2 for I/O, exit 3 for contract."""
    try:
        return load_state(state_path.parent, state_path)
    except StateStoreError as exc:
        cause = exc.__cause__
        if isinstance(cause, ContractValidationError):
            raise cli.contract_error(cause, context="remediation state") from exc
        raise cli.CliError(f"cannot read {state_path}: {cause or exc}") from exc


def _require_request_digest(value: str | None) -> str:
    if value is None or _REQUEST_DIGEST.fullmatch(value) is None:
        raise cli.CliError(
            "--request-digest is required and must match sha256:<64 lowercase hex>",
            exit_code=3,
        )
    return value


def _artifact_ref(path: Path, raw: bytes, *, role: str) -> ArtifactRef:
    """Build a host-owned reference to an already-at-rest input file."""
    return build_artifact_ref(path, raw, artifact_id=role, role=role)


def _cross_check_gate_evidence(
    observation: RemediationCureObservation, gate_evidence_paths: list[Path]
) -> None:
    """Verify each --gate-evidence file's bytes match the claimed digest.

    The check rejects an observation that claims gate evidence when no
    --gate-evidence path is given. It also rejects a path count or a digest that
    does not match the claimed gate evidence, in order.
    """
    claimed = observation.gate_evidence
    if not gate_evidence_paths and claimed:
        raise cli.CliError(
            "every claimed gate-evidence reference requires a host-resolved --gate-evidence path",
            exit_code=3,
        )
    if gate_evidence_paths and not claimed:
        raise cli.CliError(
            "--gate-evidence paths require claimed gate-evidence references",
            exit_code=3,
        )
    if not gate_evidence_paths:
        return
    if len(gate_evidence_paths) != len(claimed):
        raise cli.CliError(
            f"--gate-evidence count {len(gate_evidence_paths)} does not match the {len(claimed)} gate-evidence references in the cure observation",
            exit_code=3,
        )
    for path, evidence in zip(gate_evidence_paths, claimed):
        raw = _read_bytes(path)
        actual = bytes_digest(raw)
        if actual != evidence.artifact.digest:
            raise cli.CliError(
                f"gate-evidence digest mismatch for {path}: file is {actual}, cure observation claims {evidence.artifact.digest}",
                exit_code=3,
            )


def _publish_and_reload(state_path: Path, next_state: RemediationState) -> RemediationState:
    """Publish next_state through the store. Fail closed with exit 2."""
    try:
        return publish_state(state_path.parent, state_path, next_state)
    except StateStoreError as exc:
        raise cli.CliError(
            f"state publish/reload failed; no next phase dispatched: {exc}",
            exit_code=2,
        ) from exc


def apply_event(
    state: RemediationState,
    *,
    event: str,
    artifact_ref: ArtifactRef,
    review: ReviewResult | None = None,
    observation: RemediationCureObservation | None = None,
    request_digest: str | None = None,
    publish: Callable[[RemediationState], RemediationState] | None = None,
    max_rounds: int = 8,
) -> tuple[RemediationState, Verdict]:
    """Validate and route one event through the shared in-process decision core."""
    if event == "review":
        if review is None or observation is not None:
            raise ValueError("review routing requires only a review payload")
        if review.event_identity is None:
            raise ValueError("review event is missing host-owned identity")
        validate_event_identity(
            state, review.event_identity, event="review", request_digest=request_digest
        )
        next_state, verdict = decide_review(state, review, artifact_ref, max_rounds=max_rounds)
    elif event == "cure":
        if observation is None or review is not None:
            raise ValueError("cure routing requires only a Cure payload")
        if observation.event_identity is None:
            raise ValueError("cure event is missing host-owned identity")
        validate_event_identity(
            state, observation.event_identity, event="cure", request_digest=request_digest
        )
        next_state, verdict = decide_cure(
            state,
            artifact_ref,
            observation.applied_finding_keys,
            observation.deferred_finding_keys,
            observation.gate_evidence,
            observation.touched_paths,
            new_gate_failures=bool(observation.new_gate_failures),
            reverted_finding_keys=observation.reverted_finding_keys,
        )
    else:
        raise ValueError(f"unknown remediation event: {event}")
    if publish is not None:
        next_state = publish(next_state)
    return next_state, verdict


def _decide(args: _Args) -> Verdict:
    state_path = args.state
    request_digest = _require_request_digest(args.request_digest)
    state = _load_state(state_path)

    if args.event == "review":
        if args.review is None:
            raise cli.CliError("a review event requires --review")
        if args.cure_result is not None:
            raise cli.CliError("a review event does not accept --cure-result")
        review_value, review_raw = _load_contract(
            args.review, ReviewResult, "review result"
        )
        review = cast(ReviewResult, review_value)
        review_ref = _artifact_ref(args.review, review_raw, role="review")
        try:
            _next_state, verdict = apply_event(
                state, event="review", artifact_ref=review_ref, review=review,
                request_digest=request_digest,
                publish=lambda value: _publish_and_reload(state_path, value),
            )
        except ValueError as exc:
            raise cli.CliError(f"review event rejected: {exc}", exit_code=3) from exc
    else:
        if args.cure_result is None:
            raise cli.CliError("a cure event requires --cure-result")
        if args.review is not None:
            raise cli.CliError("a cure event does not accept --review")
        cure_value, cure_raw = _load_contract(
            args.cure_result, RemediationCureObservation, "cure observation"
        )
        observation = cast(RemediationCureObservation, cure_value)
        gate_paths = list(args.gate_evidence) if args.gate_evidence else []
        _cross_check_gate_evidence(observation, gate_paths)
        cure_ref = _artifact_ref(args.cure_result, cure_raw, role="cure-result")
        try:
            _next_state, verdict = apply_event(
                state, event="cure", artifact_ref=cure_ref, observation=observation,
                request_digest=request_digest,
                publish=lambda value: _publish_and_reload(state_path, value),
            )
        except ValueError as exc:
            raise cli.CliError(f"cure event rejected: {exc}", exit_code=3) from exc

    verdict["state_ref"] = str(state_path)
    return verdict


class _Args(Protocol):
    state: Path
    event: str
    request_digest: str | None
    review: Path | None
    cure_result: Path | None
    gate_evidence: list[Path] | None


def _cmd_decide(*, state: Path, event: str, request_digest: Annotated[str | None, Parameter(name="--request-digest")] = None, review: Path | None = None, cure_result: Annotated[Path | None, Parameter(name="--cure-result")] = None, gate_evidence: Annotated[list[Path] | None, Parameter(name="--gate-evidence")] = None) -> None:
    args = SimpleNamespace(state=state, event=event, request_digest=request_digest, review=review, cure_result=cure_result, gate_evidence=gate_evidence)
    verdict = _decide(cast(_Args, cast(object, args)))
    cli.emit(verdict, json_mode=True)


app = App(name="remediation-decision")
_ = app.default(_cmd_decide)


def main(argv: list[str]) -> int:
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
