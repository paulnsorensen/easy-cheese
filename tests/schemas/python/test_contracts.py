from __future__ import annotations

import easy_cheese_schemas.contracts as contract_module
import attrs
import pytest

from easy_cheese_schemas.schema_runtime import ContractValidationError, validate_contract

from easy_cheese_schemas.contracts import (
    AgentWriterView,
    ArtifactRef,
    BoundedContext,
    BoundedScope,
    ContractVersion,
    CoverageDisposition,
    Criterion,
    CriterionDisposition,
    CriterionResult,
    CriterionWriterView,
    CriterionResultWriterView,
    CurdDisposition,
    MAX_ARTIFACT_BYTES,
    CurdPlan,
    CurdPlanWriterView,
    CurdResult,
    CurdResultWriterView,
    DiagnosisCause,
    DiagnosisDisposition,
    DiagnosisHypothesisWriterView,
    DiagnosisResultWriterView,
    DiagnosisHypothesis,
    DiagnosisRequest,
    DiagnosisResult,
    EvidenceKind,
    EvidenceRef,
    HandoffPointer,
    HypothesisDisposition,
    IdentityAction,
    IdentityLineage,
    IngressKind,
    NormalizationAction,
    NormalizationReceipt,
    PhaseContract,
    PhaseDestination,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResult,
    PlannerResultWriterView,
    PlannerUncertainty,
    PlannerUncertaintyWriterView,
    Reproduction,
    ReproductionDisposition,
    ReproductionWriterView,
    ReviewCoverage,
    ReviewDisposition,
    ReviewFinding,
    ReviewKind,
    ReviewRequest,
    ReviewResult,
    ReviewFindingWriterView,
    ReviewResultWriterView,
    ReviewSeverity,
    SemanticCurd,
    SemanticCurdWriterView,
    SourceCurdRef,
    SourceLocation,
    SourcePlanRef,
    UncertaintyScope,
    UnsupportedProjection,
    WriterViewKind,
    derive_curd_disposition,
)

DIGEST = f"sha256:{'a' * 64}"
VERSION = ContractVersion(
    schema_uri="https://schemas.easy-cheese.dev/curd-plan",
    major="1",
    minor="0",
)


def artifact(artifact_id: str = "artifact-1") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        role="source",
        uri=f"repo://artifacts/{artifact_id}",
        digest=DIGEST,
        size_bytes=12,
        media_type="text/plain",
    )


def evidence(evidence_id: str = "evidence-1") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        kind=EvidenceKind.SOURCE,
        artifact=artifact(),
        summary="Grounded source evidence",
    )


def criterion(criterion_id: str = "criterion-1") -> Criterion:
    return Criterion(
        criterion_id=criterion_id,
        description="The behavior is observable",
        check="uv run pytest tests/test_behavior.py",
    )


def curd(
    curd_id: str = "curd-1",
    *,
    dependencies: list[str] | None = None,
    criteria: list[Criterion] | None = None,
    lineage: IdentityLineage | None = None,
) -> SemanticCurd:
    return SemanticCurd(
        curd_id=curd_id,
        outcome=f"Complete {curd_id}",
        scope=BoundedScope(paths=[f"src/{curd_id}.py"]),
        inputs=[artifact()],
        outputs=[f"Implemented {curd_id}"],
        dependencies=[] if dependencies is None else dependencies,
        criteria=[criterion()] if criteria is None else criteria,
        lineage=lineage or IdentityLineage(IdentityAction.NEW),
    )


def plan(*curds: SemanticCurd) -> CurdPlan:
    planned = list(curds) or [curd()]
    return CurdPlan(
        contract_version=VERSION,
        plan_id="plan-1",
        revision=1,
        digest=DIGEST,
        objective="Ship the approved behavior",
        curds=planned,
        context=BoundedContext(
            shared_inputs=[artifact()],
            constraints=["Keep the public contract stable"],
            invariants=["Every criterion has one result"],
        ),
    )


def reproduction(
    status: ReproductionDisposition = ReproductionDisposition.REPRODUCED,
) -> Reproduction:
    return Reproduction(
        status=status,
        steps=["Run the focused reproducer"],
        observed="The failure is deterministic",
        evidence=[evidence()],
    )


def cause() -> DiagnosisCause:
    return DiagnosisCause(
        summary="The parser drops the final item",
        evidence=[evidence()],
        location=SourceLocation(
            artifact_id="artifact-1",
            path="src/parser.py",
            start_line=40,
            end_line=44,
        ),
    )


def source_plan_ref() -> SourcePlanRef:
    return SourcePlanRef(plan_id="plan-1", revision=1, digest=DIGEST)


def source_curd_ref() -> SourceCurdRef:
    return SourceCurdRef(curd_id="curd-1", digest=DIGEST)


def criterion_result(
    disposition: CriterionDisposition = CriterionDisposition.PASSED,
) -> CriterionResult:
    if disposition in {CriterionDisposition.PASSED, CriterionDisposition.FAILED}:
        return CriterionResult(
            criterion_id="criterion-1",
            disposition=disposition,
            evidence=[evidence()],
        )
    return CriterionResult(
        criterion_id="criterion-1",
        disposition=disposition,
        reason="Execution never reached this criterion",
    )


def curd_result(
    disposition: CurdDisposition = CurdDisposition.PASSED,
    row: CriterionResult | None = None,
) -> CurdResult:
    return CurdResult(
        contract_version=VERSION,
        result_id="result-1",
        source_plan_ref=source_plan_ref(),
        source_curd_ref=source_curd_ref(),
        disposition=disposition,
        expected_criterion_ids=["criterion-1"],
        criterion_results=[row or criterion_result()],
        deliverables=[artifact("artifact-output")],
    )


@pytest.mark.parametrize("slug", [1, " \t\n"])
def test_contract_rejects_invalid_slugs_at_decorator_construction(
    slug: object,
) -> None:
    with pytest.raises(
        ValueError, match=r"^contract slug must be a non-empty string$"
    ):
        _ = contract_module.contract(slug)  # pyright: ignore[reportArgumentType]


def test_canonical_contracts_are_deeply_frozen() -> None:
    paths = ["src/curd-1.py"]
    scope = BoundedScope(paths=paths)
    value = plan()

    paths.append("src/escaped.py")
    assert scope.paths == ("src/curd-1.py",)
    assert isinstance(value.curds, tuple)
    with pytest.raises(AttributeError, match="append"):
        value.curds.append(curd("escaped"))  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    with pytest.raises(attrs.exceptions.FrozenInstanceError):
        value.revision = 2  # pyright: ignore[reportAttributeAccessIssue]




def test_artifact_size_is_bounded() -> None:
    with pytest.raises(ValueError, match="at most"):
        _ = ArtifactRef(
            artifact_id="artifact-large",
            role="source",
            uri="repo://artifacts/large",
            digest=DIGEST,
            size_bytes=MAX_ARTIFACT_BYTES + 1,
            media_type="text/plain",
        )


def test_curd_disposition_precedence_has_one_canonical_producer() -> None:
    failed = attrs.evolve(
        criterion_result(CriterionDisposition.FAILED), criterion_id="failed"
    )
    blocked = attrs.evolve(
        criterion_result(CriterionDisposition.BLOCKED), criterion_id="blocked"
    )
    skipped = attrs.evolve(
        criterion_result(CriterionDisposition.SKIPPED), criterion_id="skipped"
    )
    assert derive_curd_disposition((failed, blocked, skipped)) is CurdDisposition.FAILED
    assert derive_curd_disposition((blocked, skipped)) is CurdDisposition.BLOCKED
    assert derive_curd_disposition((skipped,)) is CurdDisposition.SKIPPED

@pytest.mark.parametrize(
    ("scope", "message"),
    [
        (lambda: BoundedScope(paths=[]), "paths must be a non-empty list"),
        (
            lambda: BoundedScope(paths=["src/a.py"], excluded_paths=["src/a.py"]),
            "paths and excluded_paths must not overlap",
        ),
        (
            lambda: BoundedScope(paths=[f"src/{index}.py" for index in range(65)]),
            "paths must be at most 64 items",
        ),
    ],
)
def test_bounded_scope_rejects_unbounded_or_contradictory_paths(
    scope: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        scope()  # pyright: ignore[reportCallIssue]


def test_curd_plan_rejects_unknown_dependencies() -> None:
    with pytest.raises(
        ValueError,
        match=r"curds\[1\].dependencies references undeclared curd 'missing'",
    ):
        _ = plan(curd(dependencies=["missing"]))


def test_curd_plan_rejects_dependency_cycles() -> None:
    first = curd("curd-1", dependencies=["curd-2"])
    second = curd(
        "curd-2",
        dependencies=["curd-1"],
        criteria=[criterion("criterion-2")],
    )

    with pytest.raises(ValueError, match="curd dependencies must be acyclic"):
        _ = plan(first, second)


def test_curd_plan_rejects_duplicate_criterion_identity() -> None:
    first = curd("curd-1")
    second = curd("curd-2")

    with pytest.raises(ValueError, match="criterion_id 'criterion-1' must be unique"):
        _ = plan(first, second)


def test_identity_lineage_enforces_new_retain_and_derive_rules() -> None:
    with pytest.raises(ValueError, match="new lineage must not name source curds"):
        _ = IdentityLineage(IdentityAction.NEW, ["old-curd"])
    with pytest.raises(
        ValueError, match="retain lineage must name exactly one source curd"
    ):
        _ = IdentityLineage(IdentityAction.RETAIN)
    with pytest.raises(
        ValueError, match="derive lineage must name at least one source curd"
    ):
        _ = IdentityLineage(IdentityAction.DERIVE)
    with pytest.raises(
        ValueError, match="retain lineage must preserve curd_id 'curd-1'"
    ):
        _ = curd(lineage=IdentityLineage(IdentityAction.RETAIN, ["different-curd"]))


@pytest.mark.parametrize(
    ("disposition", "plan_value", "unresolved", "reason", "message"),
    [
        (
            PlannerDisposition.COMPLETE,
            None,
            [],
            None,
            "complete planner result must carry a plan",
        ),
        (
            PlannerDisposition.COMPLETE,
            plan(),
            [],
            "An unnecessary explanation",
            "complete planner result must not include a reason",
        ),
        (
            PlannerDisposition.PARTIAL,
            plan(),
            [],
            None,
            "partial planner result must describe omitted work",
        ),
        (
            PlannerDisposition.NO_WORK,
            plan(),
            [],
            "Nothing remains",
            "no_work planner result must not carry a plan",
        ),
        (
            PlannerDisposition.BLOCKED,
            None,
            [],
            "A blocker exists",
            "blocked planner result must describe unresolved work",
        ),
    ],
)
def test_planner_result_disposition_invariants(
    disposition: PlannerDisposition,
    plan_value: CurdPlan | None,
    unresolved: list[PlannerUncertainty],
    reason: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _ = PlannerResult(
            contract_version=VERSION,
            request_id="request-1",
            disposition=disposition,
            plan=plan_value,
            unresolved_work=unresolved,
            reason=reason,
        )


def test_partial_planner_result_rejects_uncertainty_in_emitted_work() -> None:
    uncertainty = PlannerUncertainty(
        description="The emitted dependency might be wrong",
        scope=UncertaintyScope.DEPENDENCY,
        evidence=[evidence()],
    )

    with pytest.raises(
        ValueError,
        match="partial planner result uncertainty must concern omitted work only",
    ):
        _ = PlannerResult(
            contract_version=VERSION,
            request_id="request-1",
            disposition=PlannerDisposition.PARTIAL,
            plan=plan(),
            unresolved_work=[uncertainty],
        )


def test_planner_request_kind_controls_source_plan_and_evidence() -> None:
    with pytest.raises(
        ValueError, match="decompose request must not name a source plan"
    ):
        _ = PlannerRequest(
            contract_version=VERSION,
            request_id="request-1",
            kind=PlannerRequestKind.DECOMPOSE,
            objective="Split the work",
            source_plan_ref=source_plan_ref(),
        )
    with pytest.raises(ValueError, match="remediate request must carry evidence"):
        _ = PlannerRequest(
            contract_version=VERSION,
            request_id="request-2",
            kind=PlannerRequestKind.REMEDIATE,
            objective="Address the findings",
            source_plan_ref=source_plan_ref(),
        )


def test_clean_review_requires_complete_coverage() -> None:
    coverage = [
        ReviewCoverage(
            target="correctness",
            disposition=CoverageDisposition.NOT_COVERED,
            reason="The dependency was unavailable",
        )
    ]

    with pytest.raises(
        ValueError, match="clean review result requires complete coverage"
    ):
        _ = ReviewResult(
            contract_version=VERSION,
            review_id="review-1",
            disposition=ReviewDisposition.CLEAN,
            findings=[],
            coverage=coverage,
        )


def test_review_findings_disposition_requires_a_finding() -> None:
    with pytest.raises(
        ValueError, match="findings review result must include at least one finding"
    ):
        _ = ReviewResult(
            contract_version=VERSION,
            review_id="review-1",
            disposition=ReviewDisposition.FINDINGS,
            findings=[],
            coverage=[ReviewCoverage("correctness", CoverageDisposition.COVERED)],
        )


def test_blocked_review_rejects_findings_at_both_contract_boundaries() -> None:
    finding = ReviewFinding(
        finding_id="finding-1",
        severity=ReviewSeverity.HIGH,
        summary="The failure path loses data",
        evidence=[evidence()],
    )

    with pytest.raises(
        ValueError, match="blocked review result must not include findings"
    ):
        _ = ReviewResult(
            contract_version=VERSION,
            review_id="review-1",
            disposition=ReviewDisposition.BLOCKED,
            findings=[finding],
            coverage=[],
            reason="The review could not complete",
        )


def test_review_request_and_result_accept_typed_evidence() -> None:
    request = ReviewRequest(
        contract_version=VERSION,
        review_id="review-1",
        subject=artifact(),
        coverage_targets=["correctness"],
        evidence=[evidence()],
    )
    assert request.review_kind is None
    finding = ReviewFinding(
        finding_id="finding-1",
        severity=ReviewSeverity.HIGH,
        summary="The failure path loses data",
        location=SourceLocation(
            artifact_id="artifact-1",
            path="src/parser.py",
            start_line=40,
            end_line=44,
        ),
        evidence=[evidence()],
    )
    result = ReviewResult(
        contract_version=VERSION,
        review_id=request.review_id,
        disposition=ReviewDisposition.FINDINGS,
        findings=[finding],
        coverage=[ReviewCoverage("correctness", CoverageDisposition.COVERED)],
    )

    assert result.findings == (finding,)
    assert result.coverage == (
        ReviewCoverage("correctness", CoverageDisposition.COVERED),
    )



def test_review_request_accepts_typed_review_kind_and_rejects_invalid_values() -> None:
    request = ReviewRequest(
        contract_version=VERSION,
        review_id="review-1",
        subject=artifact(),
        coverage_targets=["correctness"],
        review_kind=ReviewKind.AGE,
    )
    assert request.review_kind is ReviewKind.AGE

    request = ReviewRequest(
        contract_version=VERSION,
        review_id="review-1",
        subject=artifact(),
        coverage_targets=["correctness"],
        review_kind=ReviewKind.TASTE_TEST,
    )
    assert request.review_kind is ReviewKind.TASTE_TEST

    with pytest.raises(TypeError, match="'review_kind' must be"):
        _ = ReviewRequest(
            contract_version=VERSION,
            review_id="review-1",
            subject=artifact(),
            coverage_targets=["correctness"],
            review_kind="not_a_review_kind",  # pyright: ignore[reportArgumentType]
        )


def test_confirmed_diagnosis_requires_reproduction_cause_and_regression_seam() -> None:
    with pytest.raises(
        ValueError,
        match="confirmed diagnosis must include a confirmed cause",
    ):
        _ = DiagnosisResult(
            contract_version=VERSION,
            diagnosis_id="diagnosis-1",
            disposition=DiagnosisDisposition.CONFIRMED,
            symptom="The final item disappears",
            reproduction=reproduction(),
            hypotheses=[],
        )


def test_inconclusive_diagnosis_cannot_dispatch_a_confirmed_cause() -> None:
    with pytest.raises(
        ValueError, match="inconclusive diagnosis must not include a confirmed cause"
    ):
        _ = DiagnosisResult(
            contract_version=VERSION,
            diagnosis_id="diagnosis-1",
            disposition=DiagnosisDisposition.INCONCLUSIVE,
            symptom="The final item disappears",
            reproduction=reproduction(),
            hypotheses=[
                DiagnosisHypothesis(
                    hypothesis_id="hypothesis-1",
                    statement="The parser drops the item",
                    disposition=HypothesisDisposition.UNRESOLVED,
                )
            ],
            confirmed_cause=cause(),
            unresolved_evidence=[evidence()],
        )


def test_diagnosis_contract_rejects_remediation_fields() -> None:
    request = DiagnosisRequest(
        contract_version=VERSION,
        diagnosis_id="diagnosis-1",
        symptom="The final item disappears",
        subject=artifact(),
        evidence=[evidence()],
    )

    with pytest.raises(TypeError, match="unexpected keyword argument 'remediation'"):
        _ = DiagnosisResult(
            contract_version=VERSION,
            diagnosis_id=request.diagnosis_id,
            disposition=DiagnosisDisposition.CONFIRMED,
            symptom=request.symptom,
            reproduction=reproduction(),
            hypotheses=[],
            confirmed_cause=cause(),
            regression_seam=cause().location,
            remediation="Rewrite the parser",  # pyright: ignore[reportCallIssue]
        )

    assert set(attrs.fields_dict(DiagnosisResult)) == {
        "contract_version",
        "diagnosis_id",
        "disposition",
        "symptom",
        "reproduction",
        "hypotheses",
        "confirmed_cause",
        "regression_seam",
        "unresolved_evidence",
        "reason",
    }


@pytest.mark.parametrize(
    ("disposition", "evidence_value", "reason", "message"),
    [
        (
            CriterionDisposition.PASSED,
            [],
            None,
            "passed criterion result must include evidence",
        ),
        (
            CriterionDisposition.FAILED,
            [],
            None,
            "failed criterion result must include evidence",
        ),
        (
            CriterionDisposition.BLOCKED,
            [],
            None,
            "blocked criterion result must include a reason",
        ),
        (
            CriterionDisposition.SKIPPED,
            [],
            None,
            "skipped criterion result must include a reason",
        ),
    ],
)
def test_criterion_result_disposition_invariants(
    disposition: CriterionDisposition,
    evidence_value: list[EvidenceRef],
    reason: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _ = CriterionResult(
            criterion_id="criterion-1",
            disposition=disposition,
            evidence=evidence_value,
            reason=reason,
        )


def test_curd_result_requires_exact_criterion_coverage() -> None:
    with pytest.raises(
        ValueError,
        match="criterion_results must cover expected_criterion_ids exactly",
    ):
        _ = CurdResult(
            contract_version=VERSION,
            result_id="result-1",
            source_plan_ref=source_plan_ref(),
            source_curd_ref=source_curd_ref(),
            disposition=CurdDisposition.PASSED,
            expected_criterion_ids=["criterion-1", "criterion-2"],
            criterion_results=[criterion_result()],
        )


def test_curd_result_disposition_is_derived_from_criterion_rows() -> None:
    with pytest.raises(
        ValueError,
        match="disposition must be failed for the supplied criterion_results",
    ):
        _ = curd_result(
            disposition=CurdDisposition.PASSED,
            row=criterion_result(CriterionDisposition.FAILED),
        )


def test_phase_contract_rejects_duplicate_routes() -> None:
    route = PhaseDestination(
        destination="cook",
        payload_schema_uri="https://schemas.easy-cheese.dev/curd-plan",
    )

    with pytest.raises(ValueError, match="outputs must not contain duplicate routes"):
        _ = PhaseContract(
            contract_version=VERSION,
            source="mold",
            input_schema_uris=["https://schemas.easy-cheese.dev/spec"],
            outputs=[route, route],
        )


def test_contract_version_source_references_and_projection_are_typed() -> None:
    projection = UnsupportedProjection(
        target="CurdBlock",
        curd_id="curd-1",
        field="dependencies",
        reason="CurdBlock cannot express semantic dependencies",
    )

    assert source_plan_ref() == SourcePlanRef("plan-1", 1, DIGEST)
    assert source_curd_ref() == SourceCurdRef("curd-1", DIGEST)
    assert projection == UnsupportedProjection(
        "CurdBlock",
        "curd-1",
        "dependencies",
        "CurdBlock cannot express semantic dependencies",
    )


def test_agent_writer_view_cannot_supply_host_owned_plan_fields() -> None:
    assert set(attrs.fields_dict(CurdPlanWriterView)) == {
        "objective",
        "curds",
        "context",
    }

    view = AgentWriterView(
        kind=WriterViewKind.CURD_PLAN,
        payload=CurdPlanWriterView(
            objective="Ship the approved behavior",
            curds=[
                SemanticCurdWriterView(
                    key="contract-core",
                    outcome="Define the contract core",
                    scope=BoundedScope(paths=["src/contracts.py"]),
                    outputs=["Canonical contracts"],
                    criteria=[
                        CriterionWriterView(
                            description="Contracts reject invalid values",
                            check="uv run pytest tests/test_contracts.py",
                        )
                    ],
                )
            ],
        ),
    )
    assert view.kind is WriterViewKind.CURD_PLAN

    with pytest.raises(
        ValueError, match="curd_result writer view payload must be CurdResultWriterView"
    ):
        _ = AgentWriterView(kind=WriterViewKind.CURD_RESULT, payload=view.payload)


@pytest.mark.parametrize("component", [1, "", "01", "one", "-1"])
def test_contract_version_requires_numeric_string_components(component: object) -> None:
    with pytest.raises(ValueError, match="version component"):
        _ = ContractVersion(
            schema_uri="https://schemas.easy-cheese.dev/curd-plan",
            major=component,  # pyright: ignore[reportArgumentType]
            minor="0",
        )


@pytest.mark.parametrize("value", ["ab", {"a", "b"}, {"a": "b"}])
def test_collection_converter_rejects_non_sequence_inputs(value: object) -> None:
    with pytest.raises(TypeError, match="list or tuple"):
        _ = BoundedScope(paths=value)  # pyright: ignore[reportArgumentType]


def test_semantic_string_collections_use_their_declared_validators() -> None:
    with pytest.raises(ValueError, match="opaque identifier"):
        _ = IdentityLineage(IdentityAction.RETAIN, source_curd_ids=["not an id"])

    with pytest.raises(ValueError, match="opaque identifier"):
        _ = ReviewRequest(
            contract_version=VERSION,
            review_id="review-1",
            subject=artifact(),
            coverage_targets=["not an id"],
        )

    with pytest.raises(ValueError, match="absolute URI"):
        _ = PhaseContract(
            contract_version=VERSION,
            source="mold",
            input_schema_uris=["not-a-uri"],
            outputs=[
                PhaseDestination(
                    destination="cook",
                    payload_schema_uri="https://schemas.easy-cheese.dev/curd-plan",
                )
            ],
        )


def test_bounded_context_accepts_the_documented_context_limit() -> None:
    text = "x" * 5_000
    context = BoundedContext(constraints=[text])
    assert context.constraints == (text,)


def test_writer_views_expose_only_agent_authored_fields() -> None:
    assert set(attrs.fields_dict(SemanticCurdWriterView)) == {
        "key",
        "outcome",
        "scope",
        "outputs",
        "criteria",
        "input_keys",
        "dependencies",
    }
    assert set(attrs.fields_dict(ReviewFindingWriterView)) == {
        "severity",
        "summary",
        "evidence_keys",
        "location",
    }
    assert set(attrs.fields_dict(ReviewResultWriterView)) == {
        "disposition",
        "findings",
        "reason",
    }
    assert set(attrs.fields_dict(DiagnosisHypothesisWriterView)) == {
        "statement",
        "disposition",
        "evidence_keys",
    }
    assert set(attrs.fields_dict(DiagnosisResultWriterView)) == {
        "disposition",
        "reproduction",
        "hypotheses",
        "confirmed_cause",
        "regression_seam",
        "unresolved_evidence_keys",
        "reason",
    }
    assert set(attrs.fields_dict(CriterionResultWriterView)) == {
        "disposition",
        "evidence_keys",
        "reason",
    }
    assert set(attrs.fields_dict(CurdResultWriterView)) == {
        "criterion_results",
        "deliverables",
        "unresolved_work",
    }
    assert {name for name in contract_module.__all__ if "Writer" in name} == {
        "AgentWriterView",
        "BoundedContextWriterView",
        "CriterionResultWriterView",
        "CriterionWriterView",
        "CurdPlanWriterView",
        "CurdResultWriterView",
        "DeliverableWriterView",
        "DiagnosisCauseWriterView",
        "DiagnosisHypothesisWriterView",
        "DiagnosisResultWriterView",
        "PlannerResultWriterView",
        "PlannerUncertaintyWriterView",
        "ReproductionWriterView",
        "ReviewFindingWriterView",
        "ReviewResultWriterView",
        "SemanticCurdWriterView",
        "SourceLocationWriterView",
        "WriterPayload",
        "WriterViewKind",
    }


def test_planner_writer_view_rejects_no_work_with_unresolved_work() -> None:
    with pytest.raises(
        ValueError,
        match="no_work planner writer view must not carry unresolved work",
    ):
        _ = PlannerResultWriterView(
            disposition=PlannerDisposition.NO_WORK,
            unresolved_work=[
                PlannerUncertaintyWriterView(
                    description="A dependency is unresolved",
                    scope=UncertaintyScope.DEPENDENCY,
                    evidence_keys=[],
                )
            ],
            reason="No work can be emitted",
        )


def test_review_writer_view_enforces_disposition() -> None:
    finding_fields = attrs.fields_dict(ReviewFindingWriterView)
    finding_kwargs: dict[str, object] = {
        "severity": ReviewSeverity.HIGH,
        "summary": "The implementation violates the contract",
        "evidence_keys": ["evidence-1"],
    }
    if "evidence" in finding_fields:
        finding_kwargs["evidence"] = [evidence()]
        del finding_kwargs["evidence_keys"]

    result_kwargs: dict[str, object] = {
        "disposition": ReviewDisposition.CLEAN,
        "findings": [ReviewFindingWriterView(**finding_kwargs)],  # pyright: ignore[reportArgumentType]
    }
    if "coverage" in attrs.fields_dict(ReviewResultWriterView):
        result_kwargs["coverage"] = [
            ReviewCoverage("contract", CoverageDisposition.COVERED)
        ]

    with pytest.raises(
        ValueError, match="clean review writer view must not include findings"
    ):
        _ = ReviewResultWriterView(**result_kwargs)  # pyright: ignore[reportArgumentType]


def test_diagnosis_writer_view_enforces_confirmed_disposition() -> None:
    kwargs: dict[str, object] = {
        "disposition": DiagnosisDisposition.CONFIRMED,
        "reproduction": ReproductionWriterView(
            status=ReproductionDisposition.REPRODUCED,
            steps=["Run the focused reproducer"],
            observed="The failure is deterministic",
            evidence_keys=["evidence-1"],
        ),
        "hypotheses": [],
    }
    if "symptom" in attrs.fields_dict(DiagnosisResultWriterView):
        kwargs["symptom"] = "The parser drops the final item"

    with pytest.raises(
        ValueError,
        match="confirmed diagnosis writer view must include a confirmed cause",
    ):
        _ = DiagnosisResultWriterView(**kwargs)  # pyright: ignore[reportArgumentType]


def test_diagnosis_hypothesis_writer_view_requires_evidence_for_a_verdict() -> None:
    kwargs: dict[str, object] = {
        "statement": "The parser drops the final item",
        "disposition": HypothesisDisposition.CONFIRMED,
        "evidence_keys": [],
    }
    if "evidence" in attrs.fields_dict(DiagnosisHypothesisWriterView):
        kwargs["evidence"] = []
        del kwargs["evidence_keys"]

    with pytest.raises(ValueError, match="confirmed hypothesis must include evidence"):
        _ = DiagnosisHypothesisWriterView(**kwargs)  # pyright: ignore[reportArgumentType]


def test_criterion_writer_view_enforces_disposition() -> None:
    kwargs: dict[str, object] = {
        "disposition": CriterionDisposition.PASSED,
        "evidence_keys": [],
    }
    if "evidence" in attrs.fields_dict(CriterionResultWriterView):
        kwargs["evidence"] = []
        del kwargs["evidence_keys"]

    with pytest.raises(
        ValueError, match="passed criterion result must include evidence"
    ):
        _ = CriterionResultWriterView(**kwargs)  # pyright: ignore[reportArgumentType]


def test_handoff_pointer_rejects_invalid_request_digest() -> None:
    with pytest.raises(
        ValueError,
        match="request_digest must be sha256: followed by 64 lowercase hexadecimal characters",
    ):
        _ = HandoffPointer(
            contract_version=VERSION,
            operation_id="operation-1",
            request_digest="not-a-digest",
            source_phase="mold",
            destination_phase="cook",
            payload=artifact(),
        )


def test_normalization_receipt_legacy_ingress_requires_source_fields_at_attrs_level() -> None:
    with pytest.raises(
        ValueError,
        match="legacy_artifact ingress requires source_schema_uri and source_version",
    ):
        _ = NormalizationReceipt(
            ingress_kind=IngressKind.LEGACY_ARTIFACT,
            normalizer_id="normalizer-1",
            source_digest=DIGEST,
            canonical_digest=DIGEST,
        )


def test_normalization_receipt_legacy_ingress_requires_source_fields_at_contract_level() -> None:
    raw: dict[str, object] = {
        "ingress_kind": IngressKind.LEGACY_ARTIFACT.value,
        "normalizer_id": "normalizer-1",
        "source_digest": DIGEST,
        "canonical_digest": DIGEST,
        "actions": [],
    }
    with pytest.raises(
        ContractValidationError,
        match="legacy_artifact ingress requires source_schema_uri and source_version",
    ):
        _ = validate_contract(raw, NormalizationReceipt)


def test_normalization_action_exposes_only_field_path_and_action() -> None:
    assert set(attrs.fields_dict(NormalizationAction)) == {"field_path", "action"}
