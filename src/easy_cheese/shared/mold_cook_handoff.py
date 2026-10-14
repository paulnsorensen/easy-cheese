"""Host validation for bound Mold specs, plans, scope, and runner limits."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, cast
from urllib.parse import urlsplit

import attrs
from easy_cheese_schemas import SCHEMA_ROOT
from easy_cheese_schemas.contracts import (
    ArtifactRef,
    CurdPlan,
    Landing,
    MAX_CONTRACT_BYTES,
    PlannerDisposition,
    PlannerResult,
    canonical_bytes,
    landing_layer_errors,
)
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookHoldKind,
    CookSetupAuthorization,
    MoldCookCoverage,
)
from easy_cheese_schemas.schema_runtime import (
    CanonicalArtifact,
    ContractValidationError,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.validate import (
    require_exact_keys,
    require_int,
    require_mapping,
    require_relative_path,
    require_str,
)

from easy_cheese.shared.artifacts import (
    ArtifactDigestMismatchError,
    ArtifactResolutionError,
    resolve_artifact,
)
from easy_cheese.shared.bounded_read import read_bounded_file
from easy_cheese.shared.taste_test import parse_spec_frontmatter, typed_mold_document
from easy_cheese.shared.wheypoint.canonical import digest_bytes


SETUP_EVIDENCE_SCHEMA_URI = f"{SCHEMA_ROOT}/setup-evidence"

_REQUEST_DIRECTIVE_KEYS = frozenset(
    {"request_directive", "execution_directive", "whole_request_directive"}
)
_DIRECTIVE_FIELDS = frozenset(
    {"action", "decision", "directive", "disposition", "intent"}
)
_REQUEST_DIRECTIVE_HEADINGS = re.compile(
    r"(?im)^##\s+(?:request|execution|whole-request)\s+directive\s*$"
)


__all__ = [
    "MoldCookSpecReadiness",
    "SETUP_EVIDENCE_SCHEMA_URI",
    "SetupEvidence",
    "SetupEvidenceExecutionError",
    "evaluate_mold_cook_spec",
    "materialize_artifact_ref",
    "resolve_contract",
    "request_directive",
    "resolve_contract_value",
    "validate_bound_execution",
    "validate_runner_authority",
    "validate_mold_cook_setup_evidence",
]


@dataclass(frozen=True, slots=True)
class MoldCookSpecReadiness:
    """One bounded spec snapshot and the authority it is fit to support."""

    spec_ref: ArtifactRef
    landing: Landing | None
    lifecycle: str | None
    holds: tuple[CookExecutionHold, ...]


@attrs.define(frozen=True)
class SetupEvidence:
    """Bounded host-runner evidence required before setup execution."""

    prerequisite_curd_id: str
    plan_digest: str
    authorization_digest: str
    runner_command: str
    fixture_path: str
    environment_id: str
    exit_code: int
    captured_output_digest: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "SetupEvidence":
        values = require_mapping(raw, "setup evidence")
        required = (
            "prerequisite_curd_id",
            "plan_digest",
            "authorization_digest",
            "runner_command",
            "fixture_path",
            "environment_id",
            "exit_code",
            "captured_output_digest",
        )
        try:
            require_exact_keys(values, required, "setup evidence")
            return cls(
                prerequisite_curd_id=require_str(
                    values["prerequisite_curd_id"],
                    "setup evidence prerequisite_curd_id",
                ),
                plan_digest=require_str(
                    values["plan_digest"], "setup evidence plan_digest"
                ),
                authorization_digest=require_str(
                    values["authorization_digest"],
                    "setup evidence authorization_digest",
                ),
                runner_command=require_str(
                    values["runner_command"], "setup evidence runner_command"
                ),
                fixture_path=require_relative_path(
                    values["fixture_path"], "setup evidence fixture_path"
                ),
                environment_id=require_str(
                    values["environment_id"], "setup evidence environment_id"
                ),
                exit_code=require_int(values["exit_code"], "setup evidence exit_code"),
                captured_output_digest=require_str(
                    values["captured_output_digest"],
                    "setup evidence captured_output_digest",
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(str(exc)) from exc


class SetupEvidenceExecutionError(ContractValidationError):
    """Setup evidence records a non-zero host-runner exit."""


def validate_mold_cook_setup_evidence(
    evidence_ref: ArtifactRef,
    *,
    authorization: CookSetupAuthorization,
    plan: CurdPlan,
    artifact_root: str | Path,
) -> SetupEvidence:
    """Validate durable setup evidence and its retained runner output."""
    if evidence_ref.role != "setup_evidence":
        raise ContractValidationError("setup evidence reference has the wrong role")
    if evidence_ref.schema_uri != SETUP_EVIDENCE_SCHEMA_URI:
        raise ContractValidationError(
            "setup evidence reference has the wrong schema URI"
        )
    raw = _resolve_bytes(evidence_ref, artifact_root)
    try:
        decoded = cast(object, json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("setup evidence is not valid JSON") from exc
    try:
        values = require_mapping(decoded, "setup evidence")
        parsed = SetupEvidence.from_mapping(values)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(str(exc)) from exc
    if not parsed.environment_id.strip():
        raise ContractValidationError("setup evidence environment_id must not be empty")
    if parsed.prerequisite_curd_id != authorization.prerequisite_curd_id:
        raise ContractValidationError("setup evidence names a different prerequisite curd")
    if parsed.plan_digest != plan.digest:
        raise ContractValidationError("setup evidence is stale for this plan")
    if parsed.authorization_digest != digest_bytes(canonical_bytes(authorization)):
        raise ContractValidationError("setup evidence is stale for this authorization")
    if parsed.runner_command not in authorization.allowed_commands:
        raise ContractValidationError("setup command is outside approved commands")
    fixture = require_relative_path(parsed.fixture_path, "setup evidence fixture_path")
    allowed = tuple(
        require_relative_path(item, "setup authorization allowed_paths item")
        for item in authorization.allowed_paths
    )
    if not any(
        fixture == item or fixture.startswith(item.rstrip("/") + "/")
        for item in allowed
    ):
        raise ContractValidationError("setup fixture path is outside approved paths")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", parsed.captured_output_digest) is None:
        raise ContractValidationError("setup output digest is invalid")
    root = Path(artifact_root).resolve()
    output_path = root / (
        f"sha256-{parsed.captured_output_digest.removeprefix('sha256:')}"
    )
    try:
        size = output_path.stat().st_size
        output_ref = ArtifactRef(
            artifact_id=f"{evidence_ref.artifact_id}/output",
            role="setup_output",
            uri=output_path.as_uri(),
            digest=parsed.captured_output_digest,
            size_bytes=size,
            media_type="text/plain",
        )
        _ = resolve_artifact(
            output_ref,
            repository_root=root,
            artifact_directory=root,
            allowed_local_root=root,
        )
    except (ArtifactDigestMismatchError, ArtifactResolutionError, OSError, ValueError) as exc:
        raise ContractValidationError(
            "setup output digest does not match retained bytes"
        ) from exc
    if parsed.exit_code != 0:
        raise SetupEvidenceExecutionError("setup runner did not pass")
    return parsed


def _directive_value(value: object) -> str | None:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        for key in _DIRECTIVE_FIELDS:
            candidate = mapping.get(key)
            if isinstance(candidate, str):
                value = candidate
                break
        else:
            return None
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold().replace("_", "-").replace(" ", "-")
    return normalized if normalized in {"do-not-implement", "do-not-proceed"} else None


def request_directive(text: str) -> str | None:
    """Read an explicit whole-request stop from frontmatter or its section."""
    values = parse_spec_frontmatter(text)
    directive = next(
        (
            parsed
            for key, value in values.items()
            if key in _REQUEST_DIRECTIVE_KEYS
            for parsed in (_directive_value(value),)
            if parsed is not None
        ),
        None,
    )
    if directive is not None:
        return directive
    match = _REQUEST_DIRECTIVE_HEADINGS.search(text)
    if match is None:
        return None
    next_heading = re.search(r"(?im)^##\s+", text[match.end() :])
    section = (
        text[match.end() : match.end() + next_heading.start()]
        if next_heading
        else text[match.end() :]
    )
    for line in section.splitlines():
        candidate = line.strip().lstrip("-*").strip()
        if ":" not in candidate:
            continue
        key, value = candidate.split(":", 1)
        if key.strip().casefold() in _DIRECTIVE_FIELDS:
            directive = _directive_value(value)
            if directive is not None:
                return directive
    return None


def evaluate_mold_cook_spec(
    content: bytes,
    *,
    spec_ref: ArtifactRef,
    plan: CurdPlan | None = None,
    lifecycle: str | None = None,
    holds: Sequence[CookExecutionHold] = (),
) -> MoldCookSpecReadiness:
    """Evaluate one immutable spec snapshot and its landing declaration."""

    if len(content) != spec_ref.size_bytes:
        raise ContractValidationError("spec snapshot size does not match spec_ref")
    if digest_bytes(content) != spec_ref.digest:
        raise ContractValidationError("spec snapshot digest does not match spec_ref")
    try:
        text = content.decode("utf-8")
        document, _, _ = typed_mold_document(text)
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            f"spec snapshot is not a valid Mold document: {exc}"
        ) from exc
    parsed_lifecycle = document.frontmatter.status
    if lifecycle is not None and lifecycle != parsed_lifecycle:
        raise ContractValidationError(
            "supplied lifecycle is detached from the spec snapshot"
        )
    landing = document.frontmatter.landing
    if plan is not None and landing is not None:
        errors = landing_layer_errors(plan, landing)
        if errors:
            raise ContractValidationError(
                "spec landing does not match plan: " + "; ".join(errors)
            )
    # A Mold draft records each unresolved scope-audit row, ALIAS/NEW ENTITY
    # binding, or coherence gap as a frontmatter `execution_holds` entry.
    # The direct-spec Cook path reads this snapshot itself, so the hold must
    # come from the frontmatter here, not only from the caller.
    declared_holds = tuple(
        CookExecutionHold(
            hold_id=f"execution-hold-{index}",
            kind=CookHoldKind.PREPARATION,
            reason=f"unresolved execution hold: {entry}",
        )
        for index, entry in enumerate(document.frontmatter.execution_holds, start=1)
    )
    return MoldCookSpecReadiness(
        spec_ref=spec_ref,
        landing=landing,
        lifecycle=parsed_lifecycle,
        holds=(*tuple(holds), *declared_holds),
    )


def _content_for(value: object) -> bytes:
    if isinstance(value, CanonicalArtifact):
        return value.canonical_bytes
    if isinstance(value, bytes):
        return value
    return canonical_bytes(value)


def materialize_artifact_ref(
    value: object,
    *,
    artifact_id: str,
    role: str,
    uri: str,
    media_type: str = "application/json",
    schema_uri: str | None = None,
) -> ArtifactRef:
    """Create a deterministic reference without changing the caller's identity.

    Storage is deliberately separate: the caller chooses the durable URI and
    can call this helper again with the same identity on a retry. The digest is
    always computed from the exact bytes that will be resolved by the consumer.
    """

    content = _content_for(value)
    return ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=uri,
        digest=digest_bytes(content),
        size_bytes=len(content),
        media_type=media_type,
        schema_uri=schema_uri,
    )


_LOCAL_ARTIFACT_SCHEMES = frozenset({"file", "repo"})


def _resolve_bytes(ref: ArtifactRef, artifact_root: str | Path) -> bytes:
    try:
        scheme = urlsplit(ref.uri).scheme
    except ValueError as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} has an invalid URI"
        ) from exc
    if scheme not in _LOCAL_ARTIFACT_SCHEMES:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} uses unsupported URI scheme {scheme!r}"
        )
    root = Path(artifact_root).resolve()
    try:
        resolved = resolve_artifact(
            attrs.evolve(ref, schema_uri=None),
            repository_root=root,
            artifact_directory=root,
            allowed_local_root=root,
        )
    except ArtifactDigestMismatchError as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} is stale or corrupt: {exc}"
        ) from exc
    except ArtifactResolutionError as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} is unreadable: {exc}"
        ) from exc
    if not resolved.content:
        raise ContractValidationError(f"artifact {ref.artifact_id!r} is empty")
    return resolved.content


def resolve_contract(
    ref: ArtifactRef,
    contract_type: type,
    artifact_root: str | Path,
) -> CanonicalArtifact:
    """Resolve one artifact reference into a validated canonical contract.

    The reference must resolve to non-empty bytes that parse as the given
    contract type at a host-supported version.
    """

    content = _resolve_bytes(ref, artifact_root)
    version = supported_version_for(contract_type)
    if version is None:
        raise ContractValidationError(
            f"{contract_type.__name__} has no host-supported contract version"
        )
    try:
        return validate_contract(content, contract_type, version)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            f"artifact {ref.artifact_id!r} does not contain a valid {contract_type.__name__}: {exc}"
        ) from exc


_ContractT = TypeVar("_ContractT")


def _read_contract_path(path: Path) -> bytes:
    """Read one operator-named contract file under the contract size cap.

    The path comes from the caller's own command line, not from inside an
    artifact, so it is not confined to the artifact root: an operator may
    keep an approval or a planner result anywhere. The shared reader still
    refuses a final symlink and anything that is not a regular file, and
    still stops at `MAX_CONTRACT_BYTES`. Containment stays on the `file://`
    references that an artifact carries, which `resolve_artifact` resolves.
    """

    try:
        return read_bounded_file(path, limit=MAX_CONTRACT_BYTES)
    except OSError as exc:
        raise ContractValidationError(
            f"contract path {path} is unreadable: {exc}"
        ) from exc


def resolve_contract_value(
    value: object,
    contract_type: type[_ContractT],
    artifact_root: str | Path,  # pyright: ignore[reportUnusedParameter]
) -> _ContractT:
    """Resolve one raw producer value into its validated contract instance.

    A producer holds a contract as a local path, raw bytes, a decoded mapping,
    or an already typed instance. Every shape passes the same host-supported
    version check here, so a typed instance a producer built in memory is
    trusted no further than bytes it just read. `artifact_root` stays in the
    signature because every producer seam names its retention root here, and
    because a shape that resolves a reference would need it; the operator-named
    path shape does not.
    """

    raw: object
    if isinstance(value, Path):
        raw = _read_contract_path(value)
    elif isinstance(value, contract_type):
        raw = canonical_bytes(value)
    elif isinstance(value, (bytes, Mapping)):
        raw = cast(object, value)
    else:
        raise ContractValidationError(
            f"cannot resolve a {contract_type.__name__} "
            + f"from a {type(value).__name__} value"
        )
    version = supported_version_for(contract_type)
    if version is None:
        raise ContractValidationError(
            f"{contract_type.__name__} has no host-supported contract version"
        )
    try:
        artifact = validate_contract(raw, contract_type, version)
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            f"value is not a valid {contract_type.__name__}: {exc}"
        ) from exc
    return cast(_ContractT, artifact.value)




def _retained_runner_bytes(ref: ArtifactRef, artifact_root: str | Path) -> bytes:
    raw = _resolve_bytes(ref, artifact_root)
    digest = digest_bytes(raw)
    expected = (
        Path(artifact_root).resolve() / f"sha256-{digest.removeprefix('sha256:')}"
    ).as_uri()
    if ref.uri != expected:
        raise ContractValidationError("runner authority must be a retained host artifact")
    return raw


def validate_runner_authority(
    authorization_ref: ArtifactRef,
    response_ref: ArtifactRef,
    artifact_root: str | Path,
    *,
    spec_digest: str,
    coverage: MoldCookCoverage,
) -> CookSetupAuthorization:
    """Read retained runner limits and the explicit response to those limits."""

    if authorization_ref.role != "runner_authorization":
        raise ContractValidationError("runner authorization has the wrong role")
    if response_ref.role != "dialogue":
        raise ContractValidationError("runner response must be retained local dialogue")
    authorization_raw = _retained_runner_bytes(authorization_ref, artifact_root)
    try:
        authorization_data = require_mapping(
            cast(object, json.loads(authorization_raw)), "runner authorization"
        )
        require_exact_keys(
            authorization_data,
            ("prerequisite_curd_id", "allowed_paths", "allowed_commands"),
            "runner authorization",
        )
        authorization = CookSetupAuthorization(
            prerequisite_curd_id=cast(str, authorization_data["prerequisite_curd_id"]),
            allowed_paths=cast(list[str], authorization_data["allowed_paths"]),
            allowed_commands=cast(list[str], authorization_data["allowed_commands"]),
        )
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError(f"invalid runner authorization: {exc}") from exc
    if authorization_raw != canonical_bytes(authorization):
        raise ContractValidationError("runner authorization is not canonical")
    response_raw = _retained_runner_bytes(response_ref, artifact_root)
    try:
        dialogue = require_mapping(
            cast(object, json.loads(response_raw)), "runner response"
        )
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError(f"invalid runner response: {exc}") from exc
    digest = digest_bytes(authorization_raw)
    question = dialogue.get("question")
    response = dialogue.get("response")
    if dialogue.get("authorization_digest") != digest:
        raise ContractValidationError("runner response names different authorization")
    if dialogue.get("spec_digest") != spec_digest:
        raise ContractValidationError("runner response names a different spec")
    if dialogue.get("curd_ids") != list(coverage.curd_ids):
        raise ContractValidationError("runner response names different coverage")
    if not isinstance(question, str) or not all(
        item in question for item in (digest, spec_digest, *coverage.curd_ids)
    ):
        raise ContractValidationError("runner question does not present exact limits and work")
    if not isinstance(response, str) or response.strip().lower() not in {
        "approve", "approved", "yes",
    }:
        raise ContractValidationError("runner response is not explicit approval")
    if dialogue.get("execution_authorized") is not True or dialogue.get("hold") or dialogue.get("holds"):
        raise ContractValidationError("runner response does not authorize execution")
    return authorization


def _check_coverage_against_plan(
    coverage: MoldCookCoverage,
    planner: PlannerResult,
    plan: CurdPlan,
) -> None:
    declared = {curd.curd_id: curd for curd in plan.curds}
    selected = set(coverage.curd_ids)
    unknown = selected - declared.keys()
    if unknown:
        raise ContractValidationError(
            "coverage names unknown canonical curd IDs: " + ", ".join(sorted(unknown))
        )
    if planner.disposition is PlannerDisposition.COMPLETE:
        if tuple(coverage.curd_ids) != tuple(curd.curd_id for curd in plan.curds):
            raise ContractValidationError(
                "complete planner result requires coverage of every canonical curd"
            )
        if coverage.unresolved_work:
            raise ContractValidationError(
                "complete planner result cannot retain unresolved work"
            )
    elif planner.disposition is PlannerDisposition.PARTIAL:
        if not coverage.unresolved_work:
            raise ContractValidationError(
                "partial coverage must acknowledge unresolved work"
            )
        if coverage.unresolved_work != planner.unresolved_work:
            raise ContractValidationError(
                "partial coverage does not preserve the PlannerResult remainder"
            )
    else:
        raise ContractValidationError(
            f"planner disposition {planner.disposition.value} cannot authorize a handoff"
        )
    for curd_id in coverage.curd_ids:
        missing = set(declared[curd_id].dependencies) - selected
        if missing:
            raise ContractValidationError(
                f"coverage for {curd_id!r} omits dependencies: {', '.join(sorted(missing))}"
            )




def validate_bound_execution(
    *,
    spec_ref: ArtifactRef,
    planner_result_ref: ArtifactRef,
    plan_ref: ArtifactRef,
    coverage: MoldCookCoverage,
    artifact_root: str | Path,
    runner_authorization_ref: ArtifactRef | None = None,
    runner_response_ref: ArtifactRef | None = None,
    setup_evidence_refs: Sequence[ArtifactRef] = (),
) -> CurdPlan:
    """Validate direct spec, plan, scope, and retained runner authority."""
    if spec_ref.role != "spec":
        raise ContractValidationError("execution requires a spec reference")
    if planner_result_ref.role != "planner_result" or plan_ref.role != "curd_plan":
        raise ContractValidationError("execution requires planner and plan references")
    spec_content = _resolve_bytes(spec_ref, artifact_root)
    planner_artifact = resolve_contract(planner_result_ref, PlannerResult, artifact_root)
    plan_artifact = resolve_contract(plan_ref, CurdPlan, artifact_root)
    planner = cast(PlannerResult, planner_artifact.value)
    plan = cast(CurdPlan, plan_artifact.value)
    if planner.plan is None or canonical_bytes(planner.plan) != plan_artifact.canonical_bytes:
        raise ContractValidationError("planner and plan references are detached")
    _check_coverage_against_plan(coverage, planner, plan)
    readiness = evaluate_mold_cook_spec(spec_content, spec_ref=spec_ref, plan=plan)
    if readiness.holds:
        raise ContractValidationError("spec retains execution holds")
    directive = request_directive(spec_content.decode("utf-8"))
    if directive is not None:
        raise ContractValidationError(
            f"spec request directive {directive!r} blocks execution"
        )
    if (runner_authorization_ref is None) != (runner_response_ref is None):
        raise ContractValidationError("runner authority requires authorization and response")
    if setup_evidence_refs and runner_authorization_ref is None:
        raise ContractValidationError("setup evidence requires runner authority")
    if runner_authorization_ref is not None and runner_response_ref is not None:
        if not setup_evidence_refs:
            raise ContractValidationError("runner authority requires passing setup evidence")
        authorization = validate_runner_authority(
            runner_authorization_ref, runner_response_ref, artifact_root,
            spec_digest=spec_ref.digest, coverage=coverage,
        )
        for evidence_ref in setup_evidence_refs:
            _ = validate_mold_cook_setup_evidence(
                evidence_ref, authorization=authorization, plan=plan,
                artifact_root=artifact_root,
            )
    return plan
