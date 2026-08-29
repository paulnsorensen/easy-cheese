from __future__ import annotations

from easy_cheese_schemas.contracts import (
    CurdPlan,
    IdentityAction,
    SemanticCurd,
    UnsupportedProjection,
)
from easy_cheese_schemas.curd import (
    MIN_CURD_SURFACE,
    CurdBlock,
    Decomposer,
    DecomposerSource,
    PlannedCurd,
)
from easy_cheese_schemas.decomposition import DecomposedCurd, Decomposition

__all__ = ["project_curd_block", "project_decomposition"]


def _unsupported(
    target: str,
    field: str,
    reason: str,
    curd: SemanticCurd | None = None,
) -> UnsupportedProjection:
    return UnsupportedProjection(
        target=target,
        curd_id=None if curd is None else curd.curd_id,
        field=field,
        reason=reason,
    )


def _unsupported_common(plan: CurdPlan, target: str) -> UnsupportedProjection | None:
    if plan.context is not None:
        return _unsupported(target, "context", f"{target} cannot express plan context")
    if plan.parent_plan_ref is not None:
        return _unsupported(
            target,
            "parent_plan_ref",
            f"{target} cannot express parent plan lineage",
        )

    for curd in plan.curds:
        if curd.inputs:
            return _unsupported(
                target,
                "inputs",
                f"{target} cannot express semantic inputs",
                curd,
            )
        if curd.scope.excluded_paths:
            return _unsupported(
                target,
                "scope.excluded_paths",
                f"{target} cannot express excluded scope paths",
                curd,
            )
        if curd.dependencies:
            return _unsupported(
                target,
                "dependencies",
                f"{target} cannot express semantic dependencies",
                curd,
            )
        if curd.lineage.identity_action is not IdentityAction.NEW:
            return _unsupported(
                target,
                "lineage",
                f"{target} cannot express retained or derived lineage",
                curd,
            )
    return None


def _shared_path(plan: CurdPlan, target: str) -> UnsupportedProjection | None:
    owners: dict[str, str] = {}
    for curd in plan.curds:
        for path in curd.scope.paths:
            owner = owners.get(path)
            if owner is not None:
                return _unsupported(
                    target,
                    "scope.paths",
                    f"{target} requires file-disjoint curds; {path!r} is also owned by {owner!r}",
                    curd,
                )
            owners[path] = curd.curd_id
    return None


def project_curd_block(plan: CurdPlan) -> CurdBlock | UnsupportedProjection:
    unsupported = _unsupported_common(plan, "CurdBlock") or _shared_path(
        plan, "CurdBlock"
    )
    if unsupported is not None:
        return unsupported

    planned: list[PlannedCurd] = []
    for curd in plan.curds:
        checks = {criterion.check for criterion in curd.criteria}
        if len(checks) != 1:
            return _unsupported(
                "CurdBlock",
                "checks",
                "CurdBlock has one test target and cannot express distinct checks",
                curd,
            )
        planned.append(
            PlannedCurd(
                slug=curd.curd_id,
                contract=curd.outcome,
                files=list(curd.scope.paths),
                test_target=curd.criteria[0].check,
                acceptance=[criterion.description for criterion in curd.criteria],
                seed=list(curd.outputs),
                est_edit_lines=MIN_CURD_SURFACE,
            )
        )

    if len(plan.curds) != 1 or plan.objective != plan.curds[0].outcome:
        return _unsupported(
            "CurdBlock",
            "objective",
            "CurdBlock cannot express plan objective",
        )

    return CurdBlock(
        curds=planned,
        waves=[[curd.curd_id] for curd in plan.curds],
        decomposer=Decomposer(
            source=DecomposerSource.COOK,
            model="easy-cheese-schemas",
            prompt_version="curd-plan-projection-v1",
        ),
    )


def project_decomposition(plan: CurdPlan) -> Decomposition | UnsupportedProjection:
    unsupported = _unsupported_common(plan, "Decomposition") or _shared_path(
        plan, "Decomposition"
    )
    if unsupported is not None:
        return unsupported

    decomposed: list[DecomposedCurd] = []
    for curd in plan.curds:
        if len(curd.criteria) != 1:
            return _unsupported(
                "Decomposition",
                "criteria",
                "Decomposition can express exactly one criterion per curd",
                curd,
            )

        criterion = curd.criteria[0]
        try:
            projected = DecomposedCurd(
                behavior=curd.outcome,
                acceptance_criterion=criterion.description,
                files=list(curd.scope.paths),
                test_target=criterion.check,
            )
        except ValueError:
            try:
                _ = DecomposedCurd(
                    behavior=curd.outcome,
                    acceptance_criterion=criterion.description,
                    files=list(curd.scope.paths),
                    test_target="true",
                )
            except ValueError:
                return _unsupported(
                    "Decomposition",
                    "outcome",
                    "Decomposition cannot represent this outcome as one behavior",
                    curd,
                )
            return _unsupported(
                "Decomposition",
                "checks",
                "Decomposition cannot represent a chained check as one test target",
                curd,
            )
        if tuple(curd.outputs) != curd.scope.paths:
            return _unsupported(
                "Decomposition",
                "outputs",
                "Decomposition cannot express semantic outputs without flattening them",
                curd,
            )
        decomposed.append(projected)

    if len(plan.curds) != 1 or plan.objective != plan.curds[0].outcome:
        return _unsupported(
            "Decomposition",
            "objective",
            "Decomposition cannot express plan objective",
        )

    return Decomposition(curds=decomposed)
