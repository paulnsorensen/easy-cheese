from __future__ import annotations

import inspect

import pytest

from easy_cheese_schemas.compat import load
from easy_cheese_schemas.curd import (
    CurdBlock,
    Decomposer,
    DecomposerSource,
    PlannedCurd,
)
from easy_cheese_schemas.decomposition import DecomposedCurd, Decomposition
from easy_cheese_schemas.contracts import (
    ArtifactRef,
    BoundedContext,
    BoundedScope,
    ContractVersion,
    Criterion,
    CurdPlan,
    IdentityAction,
    IdentityLineage,
    SourcePlanRef,
    SemanticCurd,
    UnsupportedProjection,
)
from easy_cheese_schemas.projections import project_curd_block, project_decomposition
from shared.scripts.handoff import parse_handoff_slug

DIGEST = f"sha256:{'a' * 64}"
VERSION = ContractVersion(
    schema_uri="https://schemas.easy-cheese.dev/curd-plan",
    major="1",
    minor="0",
)
CHECK = "uv run pytest tests/test_widget.py"


def artifact() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="requirements",
        role="source",
        uri="repo://requirements/widget.md",
        digest=DIGEST,
        size_bytes=42,
        media_type="text/markdown",
    )


def semantic_curd(**changes: object) -> SemanticCurd:
    values = {
        "curd_id": "widget",
        "outcome": "Implement widget",
        "scope": BoundedScope(paths=("src/widget.py", "tests/test_widget.py")),
        "inputs": (),
        "outputs": ("Widget API", "Widget tests"),
        "dependencies": (),
        "criteria": (
            Criterion("widget-api", "Widget API is available", CHECK),
            Criterion("widget-tests", "Widget behavior is verified", CHECK),
        ),
        "lineage": IdentityLineage(IdentityAction.NEW),
    }
    values.update(changes)
    return SemanticCurd(**values)


def plan(curd: SemanticCurd | None = None, **changes: object) -> CurdPlan:
    values = {
        "contract_version": VERSION,
        "plan_id": "plan-widget",
        "revision": 1,
        "digest": DIGEST,
        "objective": "Ship widget support",
        "curds": (curd or semantic_curd(),),
    }
    values.update(changes)
    return CurdPlan(**values)

def test_curd_block_projects_single_curd_objective_without_loss() -> None:
    curd = semantic_curd(
        outcome="Ship widget support",
        criteria=(Criterion("widget", "Widget support is shipped", CHECK),),
    )
    curd_plan = plan(curd, objective=curd.outcome)

    projected = project_curd_block(curd_plan)

    assert projected == CurdBlock(
        curds=[
            PlannedCurd(
                slug="widget",
                contract="Ship widget support",
                files=["src/widget.py", "tests/test_widget.py"],
                test_target=CHECK,
                acceptance=["Widget support is shipped"],
                seed=["Widget API", "Widget tests"],
                est_edit_lines=25,
            )
        ],
        waves=[["widget"]],
        decomposer=Decomposer(
            source=DecomposerSource.COOK,
            model="easy-cheese-schemas",
            prompt_version="curd-plan-projection-v1",
        ),
    )
    assert projected.curds[0].contract == curd_plan.objective


def test_decomposition_projects_single_curd_objective_without_loss() -> None:
    curd = semantic_curd(
        outcome="Ship widget support",
        outputs=("src/widget.py", "tests/test_widget.py"),
        criteria=(Criterion("widget", "Widget support is shipped", CHECK),),
    )
    curd_plan = plan(curd, objective=curd.outcome)

    projected = project_decomposition(curd_plan)

    assert projected == Decomposition(
        curds=[
            DecomposedCurd(
                behavior="Ship widget support",
                acceptance_criterion="Widget support is shipped",
                files=["src/widget.py", "tests/test_widget.py"],
                test_target=CHECK,
            )
        ]
    )
    assert projected.curds[0].behavior == curd_plan.objective
    assert curd_plan.curds[0].outputs == tuple(projected.curds[0].files)



@pytest.mark.parametrize(
    ("projector", "target"),
    [
        (project_curd_block, "CurdBlock"),
        (project_decomposition, "Decomposition"),
    ],
)
def test_legacy_projection_rejects_distinct_objective(projector, target: str) -> None:
    curd = semantic_curd(
        outputs=("src/widget.py", "tests/test_widget.py"),
        criteria=(Criterion("widget", "Widget support is shipped", CHECK),),
    )

    assert projector(plan(curd, objective="Ship widget support")) == UnsupportedProjection(
        target=target,
        curd_id=None,
        field="objective",
        reason=f"{target} cannot express plan objective",
    )


def test_curd_block_rejects_plan_objective_instead_of_dropping_it() -> None:
    assert project_curd_block(plan()) == UnsupportedProjection(
        target="CurdBlock",
        curd_id=None,
        field="objective",
        reason="CurdBlock cannot express plan objective",
    )

def test_decomposition_rejects_outputs_even_when_equal_to_outcome() -> None:
    curd = semantic_curd(
        outcome="Implement widget",
        outputs=("Implement widget",),
        criteria=(Criterion("widget-api", "Widget API is available", CHECK),),
    )

    assert project_decomposition(plan(curd)) == UnsupportedProjection(
        target="Decomposition",
        curd_id="widget",
        field="outputs",
        reason="Decomposition cannot express semantic outputs without flattening them",
    )


@pytest.mark.parametrize(
    ("projector", "target"),
    [
        (project_curd_block, "CurdBlock"),
        (project_decomposition, "Decomposition"),
    ],
)
def test_plan_context_returns_typed_unsupported_projection(projector, target) -> None:
    context = BoundedContext(constraints=("Keep the public API stable",))

    assert projector(plan(context=context)) == UnsupportedProjection(
        target=target,
        curd_id=None,
        field="context",
        reason=f"{target} cannot express plan context",
    )

@pytest.mark.parametrize(
    ("projector", "target"),
    [
        (project_curd_block, "CurdBlock"),
        (project_decomposition, "Decomposition"),
    ],
)
def test_legacy_projection_rejects_parent_plan_ref(projector, target: str) -> None:
    parent = SourcePlanRef(plan_id="plan-parent", revision=1, digest=DIGEST)

    assert projector(plan(parent_plan_ref=parent)) == UnsupportedProjection(
        target=target,
        curd_id=None,
        field="parent_plan_ref",
        reason=f"{target} cannot express parent plan lineage",
    )


@pytest.mark.parametrize(
    ("projector", "target"),
    [
        (project_curd_block, "CurdBlock"),
        (project_decomposition, "Decomposition"),
    ],
)
def test_legacy_projection_rejects_shared_scope_paths(projector, target: str) -> None:
    foundation = semantic_curd(
        curd_id="foundation",
        outcome="Build foundation",
        scope=BoundedScope(paths=("src/widget.py",)),
        outputs=("Foundation API",),
        criteria=(Criterion("foundation", "Foundation is available", CHECK),),
    )
    widget = semantic_curd(
        scope=BoundedScope(paths=("src/widget.py", "tests/test_widget.py")),
    )

    assert projector(plan(curds=(foundation, widget))) == UnsupportedProjection(
        target=target,
        curd_id="widget",
        field="scope.paths",
        reason=(
            f"{target} requires file-disjoint curds; 'src/widget.py' is also "
            "owned by 'foundation'"
        ),
    )


@pytest.mark.parametrize(
    ("projector", "target"),
    [
        (project_curd_block, "CurdBlock"),
        (project_decomposition, "Decomposition"),
    ],
)
@pytest.mark.parametrize(
    ("changes", "field", "reason"),
    [
        (
            {"inputs": (artifact(),)},
            "inputs",
            "cannot express semantic inputs",
        ),
        (
            {
                "scope": BoundedScope(
                    paths=("src/widget.py",), excluded_paths=("vendor",)
                )
            },
            "scope.excluded_paths",
            "cannot express excluded scope paths",
        ),
        (
            {"lineage": IdentityLineage(IdentityAction.RETAIN, ("widget",))},
            "lineage",
            "cannot express retained or derived lineage",
        ),
    ],
)
def test_legacy_projection_never_flattens_unrepresentable_curd_fields(
    projector, target: str, changes: dict[str, object], field: str, reason: str
) -> None:
    assert projector(plan(semantic_curd(**changes))) == UnsupportedProjection(
        target=target,
        curd_id="widget",
        field=field,
        reason=f"{target} {reason}",
    )


@pytest.mark.parametrize(
    ("projector", "target"),
    [
        (project_curd_block, "CurdBlock"),
        (project_decomposition, "Decomposition"),
    ],
)
def test_legacy_projection_rejects_dependencies_instead_of_flattening(
    projector, target: str
) -> None:
    foundation = semantic_curd(
        curd_id="foundation",
        outcome="Build foundation",
        scope=BoundedScope(paths=("src/foundation.py",)),
        outputs=("Foundation API",),
        criteria=(Criterion("foundation", "Foundation is available", CHECK),),
    )
    widget = semantic_curd(dependencies=("foundation",))

    assert projector(plan(curds=(foundation, widget))) == UnsupportedProjection(
        target=target,
        curd_id="widget",
        field="dependencies",
        reason=f"{target} cannot express semantic dependencies",
    )


def test_curd_block_rejects_distinct_checks_instead_of_choosing_one() -> None:
    curd = semantic_curd(
        criteria=(
            Criterion("api", "API is available", "uv run pytest tests/test_api.py"),
            Criterion("cli", "CLI is available", "uv run pytest tests/test_cli.py"),
        )
    )

    assert project_curd_block(plan(curd)) == UnsupportedProjection(
        target="CurdBlock",
        curd_id="widget",
        field="checks",
        reason="CurdBlock has one test target and cannot express distinct checks",
    )


@pytest.mark.parametrize(
    ("curd", "field", "reason"),
    [
        (
            semantic_curd(
                outputs=("Generated client",),
                criteria=(Criterion("api", "API is available", CHECK),),
            ),
            "outputs",
            "Decomposition cannot express semantic outputs without flattening them",
        ),
        (
            semantic_curd(outputs=("Implement widget",)),
            "criteria",
            "Decomposition can express exactly one criterion per curd",
        ),
        (
            semantic_curd(
                outcome="Implements widget and creates client",
                outputs=("Implements widget and creates client",),
                criteria=(Criterion("api", "API is available", CHECK),),
            ),
            "outcome",
            "Decomposition cannot represent this outcome as one behavior",
        ),
        (
            semantic_curd(
                outputs=("Implement widget",),
                criteria=(
                    Criterion("api", "API is available", "pytest a.py && pytest b.py"),
                ),
            ),
            "checks",
            "Decomposition cannot represent a chained check as one test target",
        ),
    ],
)
def test_decomposition_returns_typed_unsupported_for_lossy_fields(
    curd: SemanticCurd, field: str, reason: str
) -> None:
    assert project_decomposition(plan(curd)) == UnsupportedProjection(
        target="Decomposition",
        curd_id="widget",
        field=field,
        reason=reason,
    )


def test_legacy_migration_api_signatures_remain_unchanged() -> None:
    assert (
        str(inspect.signature(load))
        == "(raw: 'dict[str, Any]', cls: 'type[T]', *, strict: 'bool') -> 'Loaded[T]'"
    )
    assert (
        str(inspect.signature(parse_handoff_slug))
        == "(text: 'str') -> 'HandoffSlug'"
    )
