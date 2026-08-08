from __future__ import annotations

import attrs
import pytest

from easy_cheese_schemas.contracts import (
    ArtifactRef,
    BoundedScope,
    ContractVersion,
    CriterionWriterView,
    CurdPlan,
    CurdPlanWriterView,
    EvidenceKind,
    EvidenceRef,
    IdentityAction,
    IdentityLineage,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResultWriterView,
    PlannerUncertaintyWriterView,
    SemanticCurdWriterView,
    SourcePlanRef,
    UncertaintyScope,
)
from easy_cheese_schemas.planner import (
    PlannerMaterializationError,
    materialize_planner_result,
)

SCHEMA_ROOT = "https://schemas.easy-cheese.dev"
DIGEST = f"sha256:{'a' * 64}"
OBJECTIVE = "Ship the planner seam"


def version(schema: str) -> ContractVersion:
    return ContractVersion(f"{SCHEMA_ROOT}/{schema}", "1", "0")


def artifact(key: str = "source") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"artifact-{key}",
        role="source",
        uri=f"repo://inputs/{key}.md",
        digest=DIGEST,
        size_bytes=12,
        media_type="text/markdown",
    )


def request(
    kind: PlannerRequestKind = PlannerRequestKind.DECOMPOSE,
    *,
    source_plan: CurdPlan | None = None,
    evidence: tuple[EvidenceRef, ...] = (),
) -> PlannerRequest:
    source_ref = (
        None
        if source_plan is None
        else SourcePlanRef(
            source_plan.plan_id,
            source_plan.revision,
            source_plan.digest,
        )
    )
    return PlannerRequest(
        contract_version=version("planner-request"),
        request_id="request-1",
        kind=kind,
        objective=OBJECTIVE,
        evidence=evidence,
        source_plan_ref=source_ref,
    )


def finding() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="finding-1",
        kind=EvidenceKind.REVIEW,
        artifact=artifact("review"),
        summary="The planner seam lacks a guard",
    )


def writer_curd(
    key: str,
    path: str,
    *,
    dependencies: tuple[str, ...] = (),
    input_keys: tuple[str, ...] = (),
) -> SemanticCurdWriterView:
    return SemanticCurdWriterView(
        key=key,
        outcome=f"Complete {key}",
        scope=BoundedScope(paths=[path]),
        outputs=[f"Implemented {key}"],
        criteria=[
            CriterionWriterView(
                description=f"{key} behavior is verified",
                check=f"uv run pytest tests/test_{key}.py",
            )
        ],
        dependencies=dependencies,
        input_keys=input_keys,
    )


def test_complete_decompose_materializes_host_identity_and_references() -> None:
    view = PlannerResultWriterView(
        disposition=PlannerDisposition.COMPLETE,
        plan=CurdPlanWriterView(
            objective=OBJECTIVE,
            curds=[
                writer_curd("core", "src/core.py", input_keys=("source",)),
                writer_curd(
                    "api", "src/api.py", dependencies=("core",)
                ),
            ],
        ),
    )
    host = {
        "plan_id": "plan-host",
        "curd_ids": {"core": "curd-core", "api": "curd-api"},
        "artifacts": {"source": artifact()},
        "lineages": {
            "core": IdentityLineage(IdentityAction.NEW),
            "api": IdentityLineage(IdentityAction.NEW),
        },
    }

    first = materialize_planner_result(request(), view, **host)
    second = materialize_planner_result(request(), view, **host)

    assert first == second
    assert first.contract_version == version("planner-result")
    assert first.request_id == "request-1"
    assert first.disposition is PlannerDisposition.COMPLETE
    assert first.reason is None
    assert first.unresolved_work == ()
    assert first.plan is not None
    assert first.plan.contract_version == version("curd-plan")
    assert first.plan.plan_id == "plan-host"
    assert first.plan.revision == 1
    assert first.plan.objective == OBJECTIVE
    assert first.plan.parent_plan_ref is None
    assert first.plan.digest.startswith("sha256:")
    assert [curd.curd_id for curd in first.plan.curds] == [
        "curd-core",
        "curd-api",
    ]
    assert first.plan.curds[0].inputs == (artifact(),)
    assert [curd.lineage for curd in first.plan.curds] == [
        IdentityLineage(IdentityAction.NEW),
        IdentityLineage(IdentityAction.NEW),
    ]
    assert first.plan.curds[0].criteria[0].criterion_id == (
        "curd-core/criterion/1"
    )
    assert first.plan.curds[1].dependencies == ("curd-core",)


def test_complete_writer_view_rejects_reason() -> None:
    with pytest.raises(
        ValueError,
        match="complete planner writer view must not include a reason",
    ):
        PlannerResultWriterView(
            disposition=PlannerDisposition.COMPLETE,
            plan=CurdPlanWriterView(
                objective=OBJECTIVE,
                curds=[writer_curd("core", "src/core.py")],
            ),
            reason="An unnecessary explanation",
        )


def source_plan() -> CurdPlan:
    result = materialize_planner_result(
        request(),
        PlannerResultWriterView(
            disposition=PlannerDisposition.COMPLETE,
            plan=CurdPlanWriterView(
                objective=OBJECTIVE,
                curds=[writer_curd("core", "src/core.py")],
            ),
        ),
        plan_id="plan-source",
        curd_ids={"core": "curd-core"},
    )
    assert result.plan is not None
    return result.plan


def test_replan_retains_plan_and_curd_identity_with_incremented_revision() -> None:
    source = source_plan()
    result = materialize_planner_result(
        request(PlannerRequestKind.REPLAN, source_plan=source),
        PlannerResultWriterView(
            disposition=PlannerDisposition.COMPLETE,
            plan=CurdPlanWriterView(
                objective=OBJECTIVE,
                curds=[writer_curd("core", "src/core.py")],
            ),
        ),
        plan_id="plan-source",
        curd_ids={"core": "curd-core"},
        lineages={
            "core": IdentityLineage(
                IdentityAction.RETAIN,
                source_curd_ids=["curd-core"],
            )
        },
        source_plan=source,
    )

    assert result.plan is not None
    assert result.plan.plan_id == "plan-source"
    assert result.plan.revision == 2
    assert result.plan.parent_plan_ref is None
    assert result.plan.curds[0].curd_id == "curd-core"
    assert result.plan.curds[0].lineage == IdentityLineage(
        IdentityAction.RETAIN,
        source_curd_ids=["curd-core"],
    )
    assert result.plan.curds[0].criteria == source.curds[0].criteria
    assert result.plan.digest != source.digest


def test_remediate_creates_revision_one_child_plan_with_derived_lineage() -> None:
    source = source_plan()
    result = materialize_planner_result(
        request(
            PlannerRequestKind.REMEDIATE,
            source_plan=source,
            evidence=(finding(),),
        ),
        PlannerResultWriterView(
            disposition=PlannerDisposition.COMPLETE,
            plan=CurdPlanWriterView(
                objective=OBJECTIVE,
                curds=[writer_curd("fix", "src/fix.py")],
            ),
        ),
        plan_id="plan-remediation",
        curd_ids={"fix": "curd-fix"},
        lineages={
            "fix": IdentityLineage(
                IdentityAction.DERIVE,
                source_curd_ids=["curd-core"],
            )
        },
        source_plan=source,
    )

    assert result.plan is not None
    assert result.plan.plan_id == "plan-remediation"
    assert result.plan.revision == 1
    assert result.plan.parent_plan_ref == SourcePlanRef(
        source.plan_id,
        source.revision,
        source.digest,
    )
    assert result.plan.curds[0].lineage == IdentityLineage(
        IdentityAction.DERIVE,
        source_curd_ids=["curd-core"],
    )


def omitted_work() -> PlannerUncertaintyWriterView:
    return PlannerUncertaintyWriterView(
        description="The CLI work remains to be planned",
        scope=UncertaintyScope.OMITTED_WORK,
        evidence_keys=["finding"],
    )


def test_partial_materializes_only_runnable_curds_and_omitted_work() -> None:
    result = materialize_planner_result(
        request(evidence=(finding(),)),
        PlannerResultWriterView(
            disposition=PlannerDisposition.PARTIAL,
            plan=CurdPlanWriterView(
                objective=OBJECTIVE,
                curds=[writer_curd("core", "src/core.py")],
            ),
            unresolved_work=[omitted_work()],
        ),
        plan_id="plan-partial",
        curd_ids={"core": "curd-core"},
        evidence={"finding": finding()},
    )

    assert result.disposition is PlannerDisposition.PARTIAL
    assert result.plan is not None
    assert [curd.curd_id for curd in result.plan.curds] == ["curd-core"]
    assert result.unresolved_work[0].description == (
        "The CLI work remains to be planned"
    )
    assert result.unresolved_work[0].scope is UncertaintyScope.OMITTED_WORK
    assert result.unresolved_work[0].evidence == (finding(),)


def test_blocked_requires_unresolved_work_and_has_no_runnable_payload() -> None:
    unresolved = PlannerUncertaintyWriterView(
        description="File ownership cannot yet be assigned",
        scope=UncertaintyScope.SHARED_CONSTRAINT,
        evidence_keys=["finding"],
    )
    result = materialize_planner_result(
        request(evidence=(finding(),)),
        PlannerResultWriterView(
            disposition=PlannerDisposition.BLOCKED,
            unresolved_work=[unresolved],
            reason="Resolve file ownership before planning",
        ),
        evidence={"finding": finding()},
    )

    assert result.disposition is PlannerDisposition.BLOCKED
    assert result.plan is None
    assert result.reason == "Resolve file ownership before planning"
    assert result.unresolved_work[0].scope is UncertaintyScope.SHARED_CONSTRAINT
    assert result.unresolved_work[0].evidence == (finding(),)


def test_no_work_is_empty_and_has_no_unresolved_work() -> None:
    result = materialize_planner_result(
        request(),
        PlannerResultWriterView(
            disposition=PlannerDisposition.NO_WORK,
            reason="The objective is already satisfied",
        ),
    )

    assert result.disposition is PlannerDisposition.NO_WORK
    assert result.plan is None
    assert result.unresolved_work == ()
    assert result.reason == "The objective is already satisfied"


@pytest.mark.parametrize(
    "disposition",
    [
        PlannerDisposition.INVALID,
        PlannerDisposition.EXECUTOR_FAILURE,
    ],
)
def test_terminal_failure_dispositions_require_reason_and_no_payload(
    disposition: PlannerDisposition,
) -> None:
    result = materialize_planner_result(
        request(),
        PlannerResultWriterView(
            disposition=disposition,
            reason=f"{disposition.value} reason",
        ),
    )

    assert result.disposition is disposition
    assert result.plan is None
    assert result.unresolved_work == ()
    assert result.reason == f"{disposition.value} reason"


def test_blocked_writer_requires_unresolved_work() -> None:
    with pytest.raises(
        ValueError,
        match="blocked planner writer view must describe unresolved work",
    ):
        PlannerResultWriterView(
            disposition=PlannerDisposition.BLOCKED,
            reason="Planner claimed a blocker without unresolved work",
        )


def test_invalid_writer_rejects_unresolved_payload() -> None:
    with pytest.raises(
        ValueError,
        match="invalid planner writer view must not carry unresolved work",
    ):
        PlannerResultWriterView(
            disposition=PlannerDisposition.INVALID,
            unresolved_work=[
                PlannerUncertaintyWriterView(
                    description="The invalid payload still claimed uncertainty",
                    scope=UncertaintyScope.SHARED_CONSTRAINT,
                )
            ],
            reason="The writer output was invalid",
        )


def complete_view(
    *curds: SemanticCurdWriterView,
    objective: str = OBJECTIVE,
) -> PlannerResultWriterView:
    return PlannerResultWriterView(
        disposition=PlannerDisposition.COMPLETE,
        plan=CurdPlanWriterView(objective=objective, curds=curds),
    )


@pytest.mark.parametrize(
    ("curds", "curd_ids", "message"),
    [
        (
            (
                writer_curd("core", "src/core.py"),
                writer_curd("core", "src/other.py"),
            ),
            {"core": "curd-core"},
            "writer curd keys must not contain duplicate 'core'",
        ),
        (
            (writer_curd("api", "src/api.py", dependencies=("missing",)),),
            {"api": "curd-api"},
            "curd 'api' references unknown dependency 'missing'",
        ),
        (
            (
                writer_curd("core", "src/core.py", dependencies=("api",)),
                writer_curd("api", "src/api.py", dependencies=("core",)),
            ),
            {"core": "curd-core", "api": "curd-api"},
            "curd dependencies must be acyclic",
        ),
    ],
)
def test_plan_rejects_duplicate_or_invalid_dependency_graphs(
    curds: tuple[SemanticCurdWriterView, ...],
    curd_ids: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(PlannerMaterializationError, match=message):
        materialize_planner_result(
            request(),
            complete_view(*curds),
            plan_id="plan-invalid",
            curd_ids=curd_ids,
        )


def test_writer_view_rejects_duplicate_dependencies_before_materialization() -> None:
    with pytest.raises(
        ValueError,
        match="dependencies must not contain duplicate 'core'",
    ):
        writer_curd(
            "api",
            "src/api.py",
            dependencies=("core", "core"),
        )


def test_writer_view_rejects_duplicate_input_keys_before_materialization() -> None:
    with pytest.raises(
        ValueError,
        match="input_keys must not contain duplicate 'source'",
    ):
        writer_curd(
            "core",
            "src/core.py",
            input_keys=("source", "source"),
        )


def test_plan_requires_input_keys_to_resolve_to_host_artifacts() -> None:
    with pytest.raises(
        PlannerMaterializationError,
        match="input keys references unknown key 'missing'",
    ):
        materialize_planner_result(
            request(),
            complete_view(
                writer_curd(
                    "core",
                    "src/core.py",
                    input_keys=("missing",),
                )
            ),
            plan_id="plan-inputs",
            curd_ids={"core": "curd-core"},
        )


def test_complete_plan_rejects_unresolved_file_ownership() -> None:
    with pytest.raises(
        PlannerMaterializationError,
        match=(
            "scope path 'src/core.py' has unresolved ownership between "
            "'curd-core' and 'curd-api'"
        ),
    ):
        materialize_planner_result(
            request(),
            complete_view(
                writer_curd("core", "src"),
                writer_curd("api", "src/core.py"),
            ),
            plan_id="plan-overlap",
            curd_ids={"core": "curd-core", "api": "curd-api"},
        )


def test_scope_exclusion_transfers_file_ownership_explicitly() -> None:
    broad = attrs.evolve(
        writer_curd("core", "src"),
        scope=BoundedScope(
            paths=["src"],
            excluded_paths=["src/api.py"],
        ),
    )
    result = materialize_planner_result(
        request(),
        complete_view(broad, writer_curd("api", "src/api.py")),
        plan_id="plan-owned",
        curd_ids={"core": "curd-core", "api": "curd-api"},
    )

    assert result.plan is not None
    assert result.plan.curds[0].scope == BoundedScope(
        paths=["src"],
        excluded_paths=["src/api.py"],
    )
    assert result.plan.curds[1].scope == BoundedScope(paths=["src/api.py"])


def test_plan_rejects_duplicate_acceptance_description_and_check() -> None:
    criterion = CriterionWriterView(
        description="The shared behavior works",
        check="uv run pytest tests/test_shared.py",
    )
    first = attrs.evolve(writer_curd("core", "src/core.py"), criteria=(criterion,))
    second = attrs.evolve(writer_curd("api", "src/api.py"), criteria=(criterion,))

    with pytest.raises(
        PlannerMaterializationError,
        match="acceptance criteria must not duplicate a description/check pair",
    ):
        materialize_planner_result(
            request(),
            complete_view(first, second),
            plan_id="plan-criteria",
            curd_ids={"core": "curd-core", "api": "curd-api"},
        )


def test_plan_objective_must_be_the_request_objective() -> None:
    with pytest.raises(
        PlannerMaterializationError,
        match="writer plan objective must match the planner request objective",
    ):
        materialize_planner_result(
            request(),
            complete_view(
                writer_curd("core", "src/core.py"),
                objective="A stale objective",
            ),
            plan_id="plan-stale",
            curd_ids={"core": "curd-core"},
        )


def test_request_schema_version_mismatch_rejects_before_materialization() -> None:
    mismatched = PlannerRequest(
        contract_version=version("curd-plan"),
        request_id="request-version",
        kind=PlannerRequestKind.DECOMPOSE,
        objective=OBJECTIVE,
    )

    with pytest.raises(
        PlannerMaterializationError,
        match="planner request schema version must identify",
    ):
        materialize_planner_result(
            mismatched,
            complete_view(writer_curd("core", "src/core.py")),
            plan_id="plan-version",
            curd_ids={"core": "curd-core"},
        )

@pytest.mark.parametrize(
    ("major", "minor", "message"),
    [
        (
            "2",
            "0",
            "unsupported planner request major version '2'; host supports '1'",
        ),
        (
            "1",
            "1",
            "future planner request minor version '1'; host supports '0'",
        ),
    ],
)
def test_request_schema_version_rejects_unsupported_components(
    major: str,
    minor: str,
    message: str,
) -> None:
    unsupported = attrs.evolve(
        request(),
        contract_version=ContractVersion(
            f"{SCHEMA_ROOT}/planner-request",
            major,
            minor,
        ),
    )

    with pytest.raises(
        PlannerMaterializationError,
        match=message,
    ):
        materialize_planner_result(
            unsupported,
            complete_view(writer_curd("core", "src/core.py")),
            plan_id="plan-version",
            curd_ids={"core": "curd-core"},
        )


@pytest.mark.parametrize("tampered_field", ["artifact", "kind", "summary"])
def test_unresolved_evidence_rejects_tampered_same_id_reference(
    tampered_field: str,
) -> None:
    original = finding()
    if tampered_field == "artifact":
        tampered = attrs.evolve(
            original,
            artifact=attrs.evolve(
                original.artifact,
                artifact_id="artifact-tampered",
            ),
        )
    elif tampered_field == "kind":
        tampered = attrs.evolve(original, kind=EvidenceKind.SOURCE)
    else:
        tampered = attrs.evolve(original, summary="Tampered summary")

    with pytest.raises(
        PlannerMaterializationError,
        match=(
            "unresolved work evidence key 'finding' does not exactly match "
            "planner request evidence"
        ),
    ):
        materialize_planner_result(
            request(evidence=(original,)),
            PlannerResultWriterView(
                disposition=PlannerDisposition.BLOCKED,
                unresolved_work=[
                    attrs.evolve(
                        omitted_work(),
                        evidence_keys=["finding"],
                    )
                ],
                reason="The host evidence row was tampered",
            ),
            evidence={"finding": tampered},
        )



def test_replan_rejects_stale_acceptance_checks_on_retained_curd() -> None:
    source = source_plan()
    stale = attrs.evolve(
        writer_curd("core", "src/core.py"),
        criteria=(
            CriterionWriterView(
                description="An obsolete behavior is verified",
                check="uv run pytest tests/test_obsolete.py",
            ),
        ),
    )

    with pytest.raises(
        PlannerMaterializationError,
        match="retained curd 'curd-core' changes semantic content",
    ):
        materialize_planner_result(
            request(PlannerRequestKind.REPLAN, source_plan=source),
            complete_view(stale),
            plan_id="plan-source",
            curd_ids={"core": "curd-core"},
            lineages={
                "core": IdentityLineage(
                    IdentityAction.RETAIN,
                    source_curd_ids=["curd-core"],
                )
            },
            source_plan=source,
        )


def two_curd_source_plan() -> CurdPlan:
    result = materialize_planner_result(
        request(),
        complete_view(
            writer_curd("core", "src/core.py"),
            writer_curd("api", "src/api.py"),
        ),
        plan_id="plan-source",
        curd_ids={"core": "curd-core", "api": "curd-api"},
    )
    assert result.plan is not None
    return result.plan


def test_complete_replan_rejects_unowned_source_work() -> None:
    source = two_curd_source_plan()

    with pytest.raises(
        PlannerMaterializationError,
        match=(
            "complete replan leaves source curds unaccounted for: "
            r"\['curd-api'\]"
        ),
    ):
        materialize_planner_result(
            request(PlannerRequestKind.REPLAN, source_plan=source),
            complete_view(writer_curd("core", "src/core.py")),
            plan_id="plan-source",
            curd_ids={"core": "curd-core"},
            lineages={
                "core": IdentityLineage(
                    IdentityAction.RETAIN,
                    source_curd_ids=["curd-core"],
                )
            },
            source_plan=source,
        )


def test_partial_replan_may_omit_source_work_only_when_declared_unresolved() -> None:
    source = two_curd_source_plan()
    result = materialize_planner_result(
        request(
            PlannerRequestKind.REPLAN,
            source_plan=source,
            evidence=(finding(),),
        ),
        PlannerResultWriterView(
            disposition=PlannerDisposition.PARTIAL,
            plan=CurdPlanWriterView(
                objective=OBJECTIVE,
                curds=[writer_curd("core", "src/core.py")],
            ),
            unresolved_work=[omitted_work()],
        ),
        plan_id="plan-source",
        curd_ids={"core": "curd-core"},
        evidence={"finding": finding()},
        lineages={
            "core": IdentityLineage(
                IdentityAction.RETAIN,
                source_curd_ids=["curd-core"],
            )
        },
        source_plan=source,
    )

    assert result.disposition is PlannerDisposition.PARTIAL
    assert result.plan is not None
    assert [curd.curd_id for curd in result.plan.curds] == ["curd-core"]
    assert result.unresolved_work[0].scope is UncertaintyScope.OMITTED_WORK


@pytest.mark.parametrize(
    ("curd_ids", "message"),
    [
        (
            {"core": "curd-core"},
            r"curd_ids keys mismatch: missing \['api'\]",
        ),
        (
            {"core": "curd-shared", "api": "curd-shared"},
            "host curd IDs must not contain duplicate 'curd-shared'",
        ),
    ],
)
def test_host_must_own_one_unique_id_per_writer_key(
    curd_ids: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(PlannerMaterializationError, match=message):
        materialize_planner_result(
            request(),
            complete_view(
                writer_curd("core", "src/core.py"),
                writer_curd("api", "src/api.py"),
            ),
            plan_id="plan-host",
            curd_ids=curd_ids,
        )


def test_unresolved_evidence_must_belong_to_the_planner_request() -> None:
    unresolved = PlannerUncertaintyWriterView(
        description="The review finding blocks planning",
        scope=UncertaintyScope.SHARED_CONSTRAINT,
        evidence_keys=["finding"],
    )

    with pytest.raises(
        PlannerMaterializationError,
        match=(
            "unresolved work references evidence outside the request: "
            r"\['finding-1'\]"
        ),
    ):
        materialize_planner_result(
            request(),
            PlannerResultWriterView(
                disposition=PlannerDisposition.BLOCKED,
                unresolved_work=[unresolved],
                reason="The request omitted the cited evidence",
            ),
            evidence={"finding": finding()},
        )


def test_replan_rejects_tampered_source_plan_digest() -> None:
    source = attrs.evolve(source_plan(), digest=DIGEST)

    with pytest.raises(
        PlannerMaterializationError,
        match="CurdPlan digest mismatch",
    ):
        materialize_planner_result(
            request(PlannerRequestKind.REPLAN, source_plan=source),
            complete_view(writer_curd("core", "src/core.py")),
            plan_id="plan-source",
            curd_ids={"core": "curd-core"},
            lineages={
                "core": IdentityLineage(
                    IdentityAction.RETAIN,
                    source_curd_ids=["curd-core"],
                )
            },
            source_plan=source,
        )


def test_replan_rejects_source_schema_version_mismatch() -> None:
    source = attrs.evolve(
        source_plan(),
        contract_version=ContractVersion(
            f"{SCHEMA_ROOT}/curd-plan",
            "2",
            "0",
        ),
    )

    with pytest.raises(
        PlannerMaterializationError,
        match="unsupported contract major 2",
    ):
        materialize_planner_result(
            request(PlannerRequestKind.REPLAN, source_plan=source),
            complete_view(writer_curd("core", "src/core.py")),
            plan_id="plan-source",
            curd_ids={"core": "curd-core"},
            lineages={
                "core": IdentityLineage(
                    IdentityAction.RETAIN,
                    source_curd_ids=["curd-core"],
                )
            },
            source_plan=source,
        )


def test_executor_failure_can_materialize_without_resolving_source_plan() -> None:
    failed_replan = PlannerRequest(
        contract_version=version("planner-request"),
        request_id="request-failed",
        kind=PlannerRequestKind.REPLAN,
        objective=OBJECTIVE,
        source_plan_ref=SourcePlanRef("plan-source", 1, DIGEST),
    )
    result = materialize_planner_result(
        failed_replan,
        PlannerResultWriterView(
            disposition=PlannerDisposition.EXECUTOR_FAILURE,
            reason="The planner process exited before producing a plan",
        ),
    )

    assert result.request_id == "request-failed"
    assert result.disposition is PlannerDisposition.EXECUTOR_FAILURE
    assert result.plan is None
    assert result.unresolved_work == ()
    assert result.reason == "The planner process exited before producing a plan"
