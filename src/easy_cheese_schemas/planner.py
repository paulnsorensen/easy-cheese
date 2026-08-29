from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

import attrs

from easy_cheese_schemas.contracts import (
    ArtifactRef,
    BoundedContext,
    BoundedContextWriterView,
    ContractVersion,
    Criterion,
    CurdPlan,
    EvidenceRef,
    IdentityAction,
    IdentityLineage,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    PlannerResultWriterView,
    PlannerUncertainty,
    SemanticCurd,
    SemanticCurdWriterView,
    SourcePlanRef,
)
from easy_cheese_schemas.schema_runtime import (
    SCHEMA_ROOT,
    curd_plan_digest,
    supported_version_for,
    validate_curd_plan,
)


PLANNER_REQUEST_SCHEMA = f"{SCHEMA_ROOT}/planner-request"
PLANNER_RESULT_SCHEMA = f"{SCHEMA_ROOT}/planner-result"
CURD_PLAN_SCHEMA = f"{SCHEMA_ROOT}/curd-plan"

_T = TypeVar("_T")


class PlannerMaterializationError(ValueError):
    pass


def materialize_planner_result(
    request: PlannerRequest,
    writer: PlannerResultWriterView,
    *,
    plan_id: str | None = None,
    curd_ids: Mapping[str, str] | None = None,
    artifacts: Mapping[str, ArtifactRef] | None = None,
    evidence: Mapping[str, EvidenceRef] | None = None,
    lineages: Mapping[str, IdentityLineage] | None = None,
    source_plan: CurdPlan | None = None,
) -> PlannerResult:
    """Turn a planner's slim writer view into the host-owned canonical result."""
    if not isinstance(request, PlannerRequest):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("request must be a PlannerRequest")  # pyright: ignore[reportUnreachable]
    if not isinstance(writer, PlannerResultWriterView):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("writer must be a PlannerResultWriterView")  # pyright: ignore[reportUnreachable]
    _validate_request_version(request)
    artifacts = _mapping(artifacts, "artifacts")
    evidence = _mapping(evidence, "evidence")
    curd_ids = _mapping(curd_ids, "curd_ids")
    lineages = _mapping(lineages, "lineages")

    unresolved = _materialize_uncertainty(writer, evidence, request)
    _validate_source_plan(
        request,
        source_plan,
        required=writer.plan is not None,
    )
    if writer.plan is None:
        if plan_id is not None or curd_ids or lineages:
            raise PlannerMaterializationError(
                "a result without runnable curds must not receive plan identity"
            )
        return PlannerResult(
            contract_version=_version(PLANNER_RESULT_SCHEMA),
            request_id=request.request_id,
            disposition=writer.disposition,
            unresolved_work=unresolved,
            reason=writer.reason,
        )

    if writer.plan.objective != request.objective:
        raise PlannerMaterializationError(
            "writer plan objective must match the planner request objective"
        )
    if plan_id is None:
        raise PlannerMaterializationError("plan_id is required for runnable curds")

    try:
        plan = _materialize_plan(
            request,
            writer,
            plan_id,
            curd_ids,
            artifacts,
            lineages,
            source_plan,
        )
    except PlannerMaterializationError:
        raise
    except (TypeError, ValueError) as error:
        raise PlannerMaterializationError(str(error)) from error
    return PlannerResult(
        contract_version=_version(PLANNER_RESULT_SCHEMA),
        request_id=request.request_id,
        disposition=writer.disposition,
        plan=plan,
        unresolved_work=unresolved,
        reason=writer.reason,
    )


def _materialize_plan(
    request: PlannerRequest,
    writer: PlannerResultWriterView,
    plan_id: str,
    curd_ids: Mapping[str, object],
    artifacts: Mapping[str, object],
    lineages: Mapping[str, object],
    source_plan: CurdPlan | None,
) -> CurdPlan:
    assert writer.plan is not None
    keys = tuple(curd.key for curd in writer.plan.curds)
    _require_unique(keys, "writer curd keys")
    _require_exact_keys(curd_ids, keys, "curd_ids")
    resolved_ids = tuple(
        _typed_id(curd_ids[key], f"curd_ids[{key!r}]") for key in keys
    )
    _require_unique(resolved_ids, "host curd IDs")
    ids_by_key = dict(zip(keys, resolved_ids, strict=True))
    revision, parent = _plan_identity(request, plan_id, source_plan)
    resolved_lineages = _plan_lineages(
        request, keys, ids_by_key, lineages, source_plan
    )
    source_curds = (
        {}
        if source_plan is None
        else {curd.curd_id: curd for curd in source_plan.curds}
    )

    curds = tuple(
        _materialize_curd(
            curd,
            ids_by_key,
            artifacts,
            resolved_lineages[curd.key],
            source_curds,
        )
        for curd in writer.plan.curds
    )
    _validate_scope_ownership(curds)
    _validate_criteria(curds)
    _validate_retained_curds(curds, source_curds)
    if (
        request.kind is PlannerRequestKind.REPLAN
        and writer.disposition is PlannerDisposition.COMPLETE
    ):
        represented = {
            source_id
            for curd in curds
            for source_id in curd.lineage.source_curd_ids
        }
        missing = sorted(source_curds.keys() - represented)
        if missing:
            raise PlannerMaterializationError(
                f"complete replan leaves source curds unaccounted for: {missing!r}"
            )
    context = _materialize_context(writer.plan.context, artifacts)
    placeholder = CurdPlan(
        contract_version=_version(CURD_PLAN_SCHEMA),
        plan_id=plan_id,
        revision=revision,
        digest="sha256:" + "0" * 64,
        objective=writer.plan.objective,
        curds=curds,
        context=context,
        parent_plan_ref=parent,
    )
    return validate_curd_plan(
        attrs.evolve(placeholder, digest=curd_plan_digest(placeholder))
    )


def _validate_source_plan(
    request: PlannerRequest,
    source_plan: CurdPlan | None,
    *,
    required: bool,
) -> None:
    if request.kind is PlannerRequestKind.DECOMPOSE:
        if source_plan is not None:
            raise PlannerMaterializationError(
                "decompose materialization must not receive a source plan"
            )
        return
    if source_plan is None:
        if required:
            raise PlannerMaterializationError(
                f"{request.kind.value} materialization requires a source plan"
            )
        return
    expected_ref = SourcePlanRef(
        source_plan.plan_id,
        source_plan.revision,
        source_plan.digest,
    )
    if request.source_plan_ref != expected_ref:
        raise PlannerMaterializationError(
            "source plan does not match the planner request reference"
        )
    if source_plan.contract_version.schema_uri != CURD_PLAN_SCHEMA:
        raise PlannerMaterializationError(
            f"source plan schema version must identify {CURD_PLAN_SCHEMA!r}"
        )
    if supported_version_for(CURD_PLAN_SCHEMA) is None:
        raise PlannerMaterializationError(
            "curd plan schema has no host-supported contract version"
        )
    try:
        _ = validate_curd_plan(source_plan)
    except (TypeError, ValueError) as error:
        raise PlannerMaterializationError(str(error)) from error
    if (
        request.kind is PlannerRequestKind.REPLAN
        and request.objective != source_plan.objective
    ):
        raise PlannerMaterializationError(
            "replan request must preserve the source plan objective"
        )


def _plan_identity(
    request: PlannerRequest,
    plan_id: str,
    source_plan: CurdPlan | None,
) -> tuple[int, SourcePlanRef | None]:
    if request.kind is PlannerRequestKind.DECOMPOSE:
        return 1, None
    assert source_plan is not None
    assert request.source_plan_ref is not None
    if request.kind is PlannerRequestKind.REPLAN:
        if plan_id != source_plan.plan_id:
            raise PlannerMaterializationError(
                "replan must retain the source plan identity"
            )
        return source_plan.revision + 1, None
    if plan_id == source_plan.plan_id:
        raise PlannerMaterializationError(
            "remediate must create a child plan with a new identity"
        )
    return 1, request.source_plan_ref


def _plan_lineages(
    request: PlannerRequest,
    keys: tuple[str, ...],
    ids_by_key: Mapping[str, str],
    lineages: Mapping[str, object],
    source_plan: CurdPlan | None,
) -> dict[str, IdentityLineage]:
    if request.kind is PlannerRequestKind.DECOMPOSE and not lineages:
        return {key: IdentityLineage(IdentityAction.NEW) for key in keys}

    if request.kind is PlannerRequestKind.DECOMPOSE:
        _require_exact_keys(lineages, keys, "lineages")
        resolved = {}
        for key in keys:
            lineage = lineages[key]
            if not isinstance(lineage, IdentityLineage):
                raise PlannerMaterializationError(
                    f"lineages[{key!r}] must be an IdentityLineage"
                )
            if lineage.identity_action is not IdentityAction.NEW:
                raise PlannerMaterializationError(
                    f"decompose curd {key!r} must have new lineage"
                )
            resolved[key] = lineage
        return resolved

    _require_exact_keys(lineages, keys, "lineages")
    assert source_plan is not None
    source_ids = {curd.curd_id for curd in source_plan.curds}
    resolved: dict[str, IdentityLineage] = {}
    for key in keys:
        lineage = lineages[key]
        if not isinstance(lineage, IdentityLineage):
            raise PlannerMaterializationError(
                f"lineages[{key!r}] must be an IdentityLineage"
            )
        unknown = sorted(set(lineage.source_curd_ids) - source_ids)
        if unknown:
            raise PlannerMaterializationError(
                f"lineages[{key!r}] references unknown source curds {unknown!r}"
            )
        curd_id = ids_by_key[key]
        if lineage.identity_action is IdentityAction.RETAIN:
            if lineage.source_curd_ids != (curd_id,):
                raise PlannerMaterializationError(
                    f"retained curd {key!r} must preserve source identity"
                )
        elif curd_id in source_ids:
            raise PlannerMaterializationError(
                f"{lineage.identity_action.value} curd {key!r} must use a new identity"
            )
        resolved[key] = lineage
    return resolved


def _validate_retained_curds(
    curds: tuple[SemanticCurd, ...],
    source_curds: Mapping[str, SemanticCurd],
) -> None:
    semantic_fields = (
        "outcome",
        "scope",
        "inputs",
        "outputs",
        "dependencies",
        "criteria",
    )
    for curd in curds:
        if curd.lineage.identity_action is not IdentityAction.RETAIN:
            continue
        source = source_curds[curd.curd_id]
        if any(
            getattr(curd, name) != getattr(source, name)
            for name in semantic_fields
        ):
            raise PlannerMaterializationError(
                f"retained curd {curd.curd_id!r} changes semantic content; "
                + "use derive lineage"
            )




def _materialize_curd(
    writer: SemanticCurdWriterView,
    ids_by_key: Mapping[str, str],
    artifacts: Mapping[str, object],
    lineage: IdentityLineage,
    source_curds: Mapping[str, SemanticCurd],
) -> SemanticCurd:
    _require_unique(writer.dependencies, f"curd {writer.key!r} dependencies")
    if writer.key in writer.dependencies:
        raise PlannerMaterializationError(
            f"curd {writer.key!r} must not depend on itself"
        )
    try:
        dependencies = tuple(ids_by_key[key] for key in writer.dependencies)
    except KeyError as error:
        raise PlannerMaterializationError(
            f"curd {writer.key!r} references unknown dependency {error.args[0]!r}"
        ) from None
    inputs = _resolve_refs(
        writer.input_keys,
        artifacts,
        ArtifactRef,
        f"curd {writer.key!r} input keys",
    )
    curd_id = ids_by_key[writer.key]
    source = (
        source_curds.get(curd_id)
        if lineage.identity_action is IdentityAction.RETAIN
        else None
    )
    criteria = tuple(
        Criterion(
            criterion_id=(
                source.criteria[index - 1].criterion_id
                if source is not None and index <= len(source.criteria)
                else f"{curd_id}/criterion/{index}"
            ),
            description=item.description,
            check=item.check,
        )
        for index, item in enumerate(writer.criteria, start=1)
    )
    return SemanticCurd(
        curd_id=curd_id,
        outcome=writer.outcome,
        scope=writer.scope,
        inputs=inputs,
        outputs=writer.outputs,
        dependencies=dependencies,
        criteria=criteria,
        lineage=lineage,
    )


def _materialize_context(
    writer: BoundedContextWriterView | None,
    artifacts: Mapping[str, object],
) -> BoundedContext | None:
    if writer is None:
        return None
    return BoundedContext(
        shared_inputs=_resolve_refs(
            writer.shared_input_keys,
            artifacts,
            ArtifactRef,
            "plan context shared input keys",
        ),
        constraints=writer.constraints,
        invariants=writer.invariants,
    )


def _materialize_uncertainty(
    writer: PlannerResultWriterView,
    evidence: Mapping[str, object],
    request: PlannerRequest,
) -> tuple[PlannerUncertainty, ...]:
    unresolved = tuple(
        PlannerUncertainty(
            description=item.description,
            scope=item.scope,
            evidence=_resolve_refs(
                item.evidence_keys,
                evidence,
                EvidenceRef,
                "planner unresolved evidence keys",
            ),
        )
        for item in writer.unresolved_work
    )
    request_evidence = request.evidence
    unbound: set[str] = set()
    tampered: list[str] = []
    for writer_item, result_item in zip(
        writer.unresolved_work,
        unresolved,
        strict=True,
    ):
        for key, resolved in zip(
            writer_item.evidence_keys,
            result_item.evidence,
            strict=True,
        ):
            expected = next(
                (
                    item
                    for item in request_evidence
                    if item.evidence_id == resolved.evidence_id
                ),
                None,
            )
            if expected is None:
                unbound.add(resolved.evidence_id)
            elif resolved != expected:
                tampered.append(key)
    if unbound:
        raise PlannerMaterializationError(
            "unresolved work references evidence outside the request: "
            + f"{sorted(unbound)!r}"
        )
    if tampered:
        raise PlannerMaterializationError(
            "unresolved work evidence key "
            + f"{tampered[0]!r} does not exactly match planner request evidence"
        )
    return unresolved




def _validate_request_version(request: PlannerRequest) -> None:
    version = request.contract_version
    if version.schema_uri != PLANNER_REQUEST_SCHEMA:
        raise PlannerMaterializationError(
            f"planner request schema version must identify {PLANNER_REQUEST_SCHEMA!r}"
        )
    supported = supported_version_for(PLANNER_REQUEST_SCHEMA)
    if supported is None:
        raise PlannerMaterializationError(
            "planner request schema has no host-supported contract version"
        )
    if _compare_decimal_strings(version.major, supported.major) != 0:
        raise PlannerMaterializationError(
            f"unsupported planner request major version {version.major!r}; "
            + f"host supports {supported.major!r}"
        )
    if _compare_decimal_strings(version.minor, supported.minor) > 0:
        raise PlannerMaterializationError(
            f"future planner request minor version {version.minor!r}; "
            + f"host supports {supported.minor!r}"
        )


def _compare_decimal_strings(left: str, right: str) -> int:
    if len(left) != len(right):
        return -1 if len(left) < len(right) else 1
    if left == right:
        return 0
    return -1 if left < right else 1


def _version(schema_uri: str) -> ContractVersion:
    supported = supported_version_for(schema_uri)
    if supported is None:
        raise PlannerMaterializationError(
            f"{schema_uri!r} has no host-supported contract version"
        )
    return supported


def _mapping(value: Mapping[str, _T] | None, name: str) -> Mapping[str, _T]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"{name} must be a mapping")  # pyright: ignore[reportUnreachable]
    return value


def _typed_id(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise PlannerMaterializationError(f"{path} must be a string")
    return value


def _require_unique(values: tuple[str, ...], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise PlannerMaterializationError(
                f"{label} must not contain duplicate {value!r}"
            )
        seen.add(value)


def _require_exact_keys(
    values: Mapping[str, object], expected: tuple[str, ...], label: str
) -> None:
    missing = sorted(set(expected) - values.keys())
    extra = sorted(values.keys() - set(expected))
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing {missing!r}")
        if extra:
            details.append(f"unknown {extra!r}")
        raise PlannerMaterializationError(
            f"{label} keys mismatch: {', '.join(details)}"
        )


def _resolve_refs(
    keys: tuple[str, ...],
    pool: Mapping[str, object],
    expected: type[_T],
    label: str,
) -> tuple[_T, ...]:
    _require_unique(keys, label)
    resolved: list[_T] = []
    for key in keys:
        if key not in pool:
            raise PlannerMaterializationError(f"{label} references unknown key {key!r}")
        value = pool[key]
        if not isinstance(value, expected):
            raise PlannerMaterializationError(
                f"{label} key {key!r} must resolve to {expected.__name__}"
            )
        resolved.append(value)
    return tuple(resolved)


def _validate_scope_ownership(curds: tuple[SemanticCurd, ...]) -> None:
    for curd in curds:
        for path in (*curd.scope.paths, *curd.scope.excluded_paths):
            normalized = "/".join(
                part
                for part in path.split("/")
                if part not in {"", "."}
            )
            if normalized != path:
                raise PlannerMaterializationError(
                    f"scope path {path!r} must be normalized"
                )
        for excluded in curd.scope.excluded_paths:
            if not any(_covers(path, excluded) for path in curd.scope.paths):
                raise PlannerMaterializationError(
                    f"curd {curd.curd_id!r} excludes unowned path {excluded!r}"
                )

    for index, first in enumerate(curds):
        for second in curds[index + 1 :]:
            for left in first.scope.paths:
                for right in second.scope.paths:
                    overlap = (
                        right
                        if _covers(left, right)
                        else left
                        if _covers(right, left)
                        else None
                    )
                    if (
                        overlap is not None
                        and _owns(first, overlap)
                        and _owns(second, overlap)
                    ):
                        raise PlannerMaterializationError(
                            f"scope path {overlap!r} has unresolved ownership between "
                            + f"{first.curd_id!r} and {second.curd_id!r}"
                        )


def _covers(root: str, path: str) -> bool:
    return root == path or path.startswith(f"{root}/")


def _owns(curd: SemanticCurd, path: str) -> bool:
    return any(_covers(root, path) for root in curd.scope.paths) and not any(
        _covers(excluded, path) for excluded in curd.scope.excluded_paths
    )


def _validate_criteria(curds: tuple[SemanticCurd, ...]) -> None:
    seen: set[tuple[str, str]] = set()
    for curd in curds:
        for criterion in curd.criteria:
            signature = (criterion.description, criterion.check)
            if signature in seen:
                raise PlannerMaterializationError(
                    "acceptance criteria must not duplicate a description/check pair"
                )
            seen.add(signature)




__all__ = ["PlannerMaterializationError", "materialize_planner_result"]
