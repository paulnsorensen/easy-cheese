"""Focused regressions for Cook ingress classification and preparation."""

from __future__ import annotations

import hashlib
import inspect
import shutil
from pathlib import Path

import pytest

from easy_cheese_schemas import (
    ArtifactRef,
    CurdPlan,
    canonical_bytes,
    require_contract_version,
)
from easy_cheese_schemas.contracts import (
    BoundedScope,
    Criterion,
    IdentityAction,
    IdentityLineage,
    PlannerDisposition,
    PlannerResult,
    SemanticCurd,
)
from easy_cheese_schemas.compat import (
    LegacyAdapter,
    register_adapter,
    unregister_adapter,
)
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    CookPreparationOutcome,
    CookSetupAuthorization,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
    MoldCookCoverage,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese.shared.mold_cook_handoff import canonical_mold_cook_proposal
from easy_cheese.shared import paths
from easy_cheese.skills.cook.preparation import (
    CookEvidenceError,
    CookInputError,
    CookPreparationRequest,
    PreparationEvidence,
    SetupEvidence,
    classify_input,
    load_preparation_result,
    prepare,
)
from easy_cheese.skills.cook.preparation import classify, pipeline, setup

from tests.python.mold_cook_helpers import bind_mold_cook_approval
from tests.python.test_cook_contract_accept import published_handoff


_SPEC_FIXTURE = Path(__file__).parent / "fixtures" / "spec_format" / "valid_spec.md"
_SPEC_SLUG = "valid-spec-format-fixture"
_BOUNDARY_FIXTURES = Path(__file__).parents[1] / "fixtures" / "mold_cook_boundary"


def test_explicit_mode_wins_and_rejects_a_declared_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "misleading.md"
    _ = pointer.write_text('{"operation_id": "stored"}', encoding="utf-8")

    with pytest.raises(CookInputError, match="declares canonical_pointer"):
        _ = classify_input(pointer, explicit_kind=MoldCookInputKind.TASK)


def test_declared_pointer_is_classified_before_filename_suffix(tmp_path: Path) -> None:
    pointer = tmp_path / "pointer.txt"
    _ = pointer.write_text('{"operation_id": "stored"}', encoding="utf-8")

    classified = classify_input(pointer)

    assert classified.kind is MoldCookInputKind.CANONICAL_POINTER
    assert classified.path == pointer
    assert classified.declared_kind is MoldCookInputKind.CANONICAL_POINTER


def test_declared_projection_is_not_downgraded_to_task_text(tmp_path: Path) -> None:
    continuation = tmp_path / "notes.txt"
    _ = continuation.write_text('{"status": "GATED"}', encoding="utf-8")

    classified = classify_input(continuation)

    assert classified.kind is MoldCookInputKind.CONTINUATION
    assert classified.kind is not MoldCookInputKind.TASK


def test_unrecognised_existing_artifact_fails_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "result.bin"
    _ = artifact.write_bytes(b"not a Cook task")

    with pytest.raises(CookInputError, match="unrecognised artifact"):
        _ = classify_input(artifact)


def test_markdown_and_slug_inputs_keep_their_supported_routes(tmp_path: Path) -> None:
    spec = tmp_path / "approved.md"
    _ = spec.write_text("# Approved\n", encoding="utf-8")

    assert classify_input(spec).kind is MoldCookInputKind.DIRECT_SPEC
    assert classify_input("approved-spec").kind is MoldCookInputKind.SLUG
    assert (
        classify_input("implement the approved change").kind is MoldCookInputKind.TASK
    )


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _retain(root: Path, content: bytes) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"sha256-{_digest(content).removeprefix('sha256:')}"
    _ = path.write_bytes(content)
    return path


def _historical_pointer(tmp_path: Path) -> Path:
    for name in (
        "historical-plan.json",
        "historical-receipt.json",
        "historical-pointer.json",
    ):
        _ = shutil.copy2(_BOUNDARY_FIXTURES / name, tmp_path / name)
    return tmp_path / "historical-pointer.json"


def test_request_id_separates_two_direct_specs_in_one_repository(
    tmp_path: Path,
) -> None:
    """Finding 33: a kind-only request id collides across every direct spec."""
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    _ = first.write_text("# First spec\n", encoding="utf-8")
    _ = second.write_text("# Second spec\n", encoding="utf-8")

    first_id = classify.derive_request_id(classify_input(first), None)
    second_id = classify.derive_request_id(classify_input(second), None)
    repeat_id = classify.derive_request_id(classify_input(first), None)

    assert first_id != second_id
    assert first_id == repeat_id


def test_slug_input_resolves_its_stored_spec_instead_of_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 30: `/cook <slug>` had no branch and always blocked."""
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "cheese-home"))
    spec_path = paths.artifact_path("specs", _SPEC_SLUG)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    _ = spec_path.write_bytes(_SPEC_FIXTURE.read_bytes())

    result = prepare(
        _SPEC_SLUG,
        request_id="slug-request",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        explicit_kind=MoldCookInputKind.SLUG,
    )

    assert result.input_kind is MoldCookInputKind.SLUG
    assert result.outcome is CookPreparationOutcome.NEEDS_APPROVAL
    assert "spec" in {reference.role for reference in result.references}


def test_direct_spec_without_execution_holds_still_needs_approval(
    tmp_path: Path,
) -> None:
    """An absent `execution_holds` list must not gain a spurious hold."""
    spec_path = tmp_path / f"{_SPEC_SLUG}.md"
    _ = spec_path.write_text(_SPEC_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    result = prepare(
        spec_path,
        request_id="direct-spec-no-holds",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        explicit_kind=MoldCookInputKind.DIRECT_SPEC,
    )

    assert result.outcome is CookPreparationOutcome.NEEDS_APPROVAL
    assert result.holds == ()


@pytest.mark.parametrize(
    "declaration",
    [
        "execution_holds:\n  - scope-audit-row-3-needs-a-verb\n",
        'execution_holds: ["scope-audit-row-3-needs-a-verb"]\n',
    ],
    ids=["block", "flow"],
)
def test_direct_spec_execution_holds_block_before_scope_approval(
    tmp_path: Path, declaration: str
) -> None:
    """A Mold draft's unresolved holds must survive the direct `/cook <spec>` path."""
    fixture = _SPEC_FIXTURE.read_text(encoding="utf-8")
    assert "gate_applicability:\n" in fixture
    spec_path = tmp_path / f"{_SPEC_SLUG}.md"
    _ = spec_path.write_text(
        fixture.replace("gate_applicability:\n", declaration + "gate_applicability:\n", 1),
        encoding="utf-8",
    )

    result = prepare(
        spec_path,
        request_id="direct-spec-held",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        explicit_kind=MoldCookInputKind.DIRECT_SPEC,
    )

    assert result.outcome is CookPreparationOutcome.BLOCKED
    assert [hold.hold_id for hold in result.holds] == ["execution-hold-1"]

def test_canonical_pointer_outside_the_artifact_root_is_refused(
    tmp_path: Path,
) -> None:
    """Finding 41: the pointer's own location must not widen the trusted root."""
    published_root = tmp_path / "published"
    pointer, _, _ = published_handoff(published_root, "operation-outside")

    result = prepare(
        pointer,
        request_id="pointer-request",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        explicit_kind=MoldCookInputKind.CANONICAL_POINTER,
    )

    assert result.outcome is CookPreparationOutcome.INVALID
    assert [item.code for item in result.findings] == ["pointer-outside-artifact-root"]


def _signed_plan() -> CurdPlan:
    curd = SemanticCurd(
        curd_id="root",
        outcome="Implement root",
        scope=BoundedScope(paths=["src/root.py"]),
        inputs=(),
        outputs=("root-result",),
        dependencies=(),
        criteria=(
            Criterion(
                criterion_id="root-criterion",
                description="root passes",
                check="the focused Cook regression passes",
            ),
        ),
        lineage=IdentityLineage(IdentityAction.NEW),
    )
    version = require_contract_version(CurdPlan)
    return CurdPlan.signed(
        contract_version=version,
        plan_id="cook-plan",
        revision=1,
        objective="Execute the approved Cook boundary",
        curds=(curd,),
    )


def test_setup_evidence_binds_the_published_plan_digest(tmp_path: Path) -> None:
    """Finding 29: approvals bind `plan.digest`; setup evidence must agree."""
    artifacts = tmp_path / "artifacts"
    plan = _signed_plan()
    authorization = CookSetupAuthorization(
        prerequisite_curd_id="root",
        allowed_paths=("tests/setup.py",),
        allowed_commands=("python -m pytest tests/setup.py",),
    )
    output = b"setup passed\n"
    _ = _retain(artifacts, output)
    request = CookPreparationRequest(
        request_id="setup-request",
        source=classify_input("migrate the approved plan"),
        repository_root=tmp_path,
        artifact_root=artifacts,
        mode=MoldCookMode.FULL,
    )

    def evidence_ref(plan_digest: str) -> ArtifactRef:
        evidence = SetupEvidence(
            prerequisite_curd_id="root",
            plan_digest=plan_digest,
            authorization_digest=_digest(canonical_bytes(authorization)),
            runner_command="python -m pytest tests/setup.py",
            fixture_path="tests/setup.py",
            environment_id="test-env",
            exit_code=0,
            captured_output_digest=_digest(output),
        )
        content = canonical_bytes(evidence)
        path = _retain(artifacts, content)
        return ArtifactRef(
            artifact_id="setup-evidence",
            role="setup_evidence",
            uri=path.as_uri(),
            digest=_digest(content),
            size_bytes=len(content),
            media_type="application/json",
            schema_uri="https://schemas.easy-cheese.dev/setup-evidence",
        )

    accepted = setup._validate_setup(  # pyright: ignore[reportPrivateUsage]
        evidence_ref(plan.digest),
        authorization=authorization,
        plan=plan,
        request=request,
    )
    assert accepted.role == "setup_evidence"

    with pytest.raises(CookEvidenceError, match="stale for this plan"):
        _ = setup._validate_setup(  # pyright: ignore[reportPrivateUsage]
            evidence_ref(_digest(canonical_bytes(plan))),
            authorization=authorization,
            plan=plan,
            request=request,
        )


def test_prepare_no_longer_accepts_a_dead_clearances_argument() -> None:
    """Finding 65: `prepare` declared `clearances` and discarded it."""
    assert "clearances" not in inspect.signature(prepare).parameters


def _legacy_migration(tmp_path: Path) -> tuple[Path, Path]:
    pointer = _historical_pointer(tmp_path)
    artifacts = tmp_path / "artifacts"
    spec_binding = _retain(artifacts, _SPEC_FIXTURE.read_bytes())
    return pointer, spec_binding


_EXPIRED_ADAPTER_URI = "https://schemas.easy-cheese.dev/test-fixtures/cook-sunset"


def test_expired_legacy_adapter_fails_the_migration_ingress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 13: the sunset rule now gates the surviving legacy ingress."""
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "cheese-home"))
    pointer, spec_binding = _legacy_migration(tmp_path)
    register_adapter(
        LegacyAdapter(
            source_schema_uri=_EXPIRED_ADAPTER_URI,
            source_major="0",
            source_minor="1",
            target_schema_uri=_EXPIRED_ADAPTER_URI,
            remove_after="2020-01-01",
            convert=dict,
        )
    )
    try:
        result = prepare(
            pointer,
            request_id="historical-expired",
            repository_root=tmp_path,
            artifact_root=tmp_path / "artifacts",
            explicit_kind=MoldCookInputKind.CANONICAL_POINTER,
            evidence=PreparationEvidence(spec_binding=spec_binding),
        )
    finally:
        unregister_adapter(_EXPIRED_ADAPTER_URI, "0", "1")

    assert result.outcome is not CookPreparationOutcome.READY
    assert b"expired legacy adapters" in canonical_bytes(result)


def test_load_preparation_result_takes_no_artifact_root(tmp_path: Path) -> None:
    """Finding 71: the dead `artifact_root` parameter is gone."""
    saved = tmp_path / "previous.json"
    first = prepare(
        "implement the approved change",
        request_id="dead-param",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )
    _ = saved.write_bytes(canonical_bytes(first))

    assert load_preparation_result(saved).request_id == "dead-param"
    with pytest.raises(TypeError):
        _ = load_preparation_result(  # pyright: ignore[reportUnknownVariableType]
            saved,
            artifact_root=str(tmp_path),  # pyright: ignore[reportCallIssue]
        )


def test_bound_legacy_plan_is_adopted_through_one_shared_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 22: both legacy branches now share `_adopt_legacy_plan`."""
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "cheese-home"))
    pointer, spec_binding = _legacy_migration(tmp_path)

    result = prepare(
        pointer,
        request_id="historical-adopt",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        explicit_kind=MoldCookInputKind.CANONICAL_POINTER,
        evidence=PreparationEvidence(spec_binding=spec_binding),
    )

    roles = [reference.role for reference in result.references]
    assert result.requirements == ()
    assert result.holds == ()
    assert roles.count("curd_plan") == 1
    assert "planner_result" in roles
    assert "spec" in roles


def test_legacy_migration_still_honours_a_gated_continuity_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 9: the rebound readiness suppressed every migration hold."""
    monkeypatch.setenv("EASY_CHEESE_HOME", str(tmp_path / "cheese-home"))
    pointer, spec_binding = _legacy_migration(tmp_path)
    prior = tmp_path / ".cheese" / "cook" / f"{_SPEC_SLUG}.md"
    prior.parent.mkdir(parents=True, exist_ok=True)
    _ = prior.write_text(
        """\
status: ok
next: press
artifact: none
A prior Cook run already claims this spec slug.
""",
        encoding="utf-8",
    )

    result = prepare(
        pointer,
        request_id="historical-gated",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        explicit_kind=MoldCookInputKind.CANONICAL_POINTER,
        evidence=PreparationEvidence(spec_binding=spec_binding),
    )

    assert result.outcome is CookPreparationOutcome.BLOCKED
    assert [hold.hold_id.split("-")[0] for hold in result.holds] == ["continuity"]


def _landing_spec(root: Path) -> Path:
    """Copy the spec fixture and declare one landing layer on it.

    ``single`` refuses declared layers, so the one-layer landing uses
    ``stacked_linear``. Its coverage stays exactly ``("root",)``.
    """

    head, separator, body = _SPEC_FIXTURE.read_text(encoding="utf-8").partition(
        "\n---\n"
    )
    root.mkdir(parents=True, exist_ok=True)
    spec = root / "spec.md"
    _ = spec.write_text(
        head
        + '\nlanding:\n  shape: stacked_linear\n  layers: [["root"]]'
        + separator
        + body,
        encoding="utf-8",
    )
    return spec


def _write_artifact(
    root: Path,
    content: bytes,
    *,
    artifact_id: str,
    role: str,
    filename: str,
    media_type: str = "application/json",
    schema_uri: str | None = None,
) -> ArtifactRef:
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    _ = path.write_bytes(content)
    return ArtifactRef(
        artifact_id=artifact_id,
        role=role,
        uri=path.as_uri(),
        digest=_digest(content),
        size_bytes=len(content),
        media_type=media_type,
        schema_uri=schema_uri,
    )


def _approval_ref(
    root: Path,
    *,
    kind: MoldCookApprovalKind,
    spec_digest: str,
    coverage: MoldCookCoverage,
    proposal: bytes,
    name: str,
    plan_digest: str | None = None,
    response_source: str | None = None,
) -> ArtifactRef:
    proposal_ref = _write_artifact(
        root,
        proposal,
        artifact_id=f"{name}-proposal",
        role="proposal",
        filename=f"{name}-proposal.json",
    )
    response_ref = _write_artifact(
        root,
        b"Approve",
        artifact_id=f"{name}-response",
        role="response",
        filename=f"{name}-response.txt",
        media_type="text/plain",
    )
    approval = bind_mold_cook_approval(
        request_id="cook-request",
        kind=kind,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=spec_digest,
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source=(
            f"{name}-response.txt" if response_source is None else response_source
        ),
        coverage=coverage,
        plan_digest=plan_digest,
    )
    return _write_artifact(
        root,
        canonical_bytes(approval),
        artifact_id=f"{name}-approval",
        role="approval",
        filename=f"{name}-approval.json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )


def _scope_approval_ref(
    root: Path,
    spec_digest: str,
    curd_ids: tuple[str, ...],
    response_source: str | None = None,
) -> ArtifactRef:
    coverage = MoldCookCoverage(curd_ids=curd_ids)
    return _approval_ref(
        root,
        kind=MoldCookApprovalKind.SCOPE,
        spec_digest=spec_digest,
        coverage=coverage,
        proposal=canonical_mold_cook_proposal(
            request_id="cook-request",
            kind=MoldCookApprovalKind.SCOPE,
            spec_digest=spec_digest,
            coverage=coverage,
        ),
        name="scope",
        response_source=response_source,
    )


def test_scope_approval_cannot_widen_the_host_proposed_coverage(
    tmp_path: Path,
) -> None:
    """Finding 31: the scope envelope binds Cook's coverage, not the approval's."""
    root = tmp_path / "widened"
    spec = _landing_spec(root)
    widened = _scope_approval_ref(root, _digest(spec.read_bytes()), ("root", "extra"))

    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(scope_approval=widened),
    )

    assert result.outcome is CookPreparationOutcome.INVALID
    assert [item.code for item in result.findings] == ["invalid-evidence"]
    assert b"canonical envelope" in canonical_bytes(result)


def test_scope_approval_matching_the_host_proposal_is_accepted(
    tmp_path: Path,
) -> None:
    """Finding 31: the declared landing coverage is the approvable scope."""
    root = tmp_path / "matching"
    spec = _landing_spec(root)
    matching = _scope_approval_ref(root, _digest(spec.read_bytes()), ("root",))

    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(scope_approval=matching),
    )

    assert result.outcome is CookPreparationOutcome.NEEDS_PLANNING


def test_scope_round_previous_does_not_mis_fire_the_plan_guard(
    tmp_path: Path,
) -> None:
    """Finding 31: a scope round carried into a plan round proposes new bytes."""
    root = tmp_path / "carried"
    spec = _landing_spec(root)
    spec_digest = _digest(spec.read_bytes())
    scope = _scope_approval_ref(root, spec_digest, ("root",))
    plan = _signed_plan()
    planner = PlannerResult(
        contract_version=require_contract_version(PlannerResult),
        request_id="cook-request",
        disposition=PlannerDisposition.COMPLETE,
        plan=plan,
    )
    coverage = MoldCookCoverage(curd_ids=("root",))
    plan_approval = _approval_ref(
        root,
        kind=MoldCookApprovalKind.PLAN,
        spec_digest=spec_digest,
        coverage=coverage,
        proposal=canonical_mold_cook_proposal(
            request_id="cook-request",
            kind=MoldCookApprovalKind.PLAN,
            spec_digest=spec_digest,
            coverage=coverage,
            planner_result=planner,
            plan_digest=plan.digest,
        ),
        name="plan",
        plan_digest=plan.digest,
    )

    scope_round = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
    )
    assert scope_round.approval_kind is MoldCookApprovalKind.SCOPE

    carried = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(
            scope_approval=scope,
            planner_result=planner,
            plan_approval=plan_approval,
            previous=scope_round,
        ),
    )

    assert carried.outcome is CookPreparationOutcome.READY


def test_scope_resubmission_without_host_coverage_advances(tmp_path: Path) -> None:
    """A spec with no landing layers renders one proposal across both rounds."""
    root = tmp_path / "no-landing"
    root.mkdir(parents=True, exist_ok=True)
    spec = root / "spec.md"
    _ = spec.write_text(
        _SPEC_FIXTURE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    approval = _scope_approval_ref(root, _digest(spec.read_bytes()), ("root",))

    first = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
    )
    assert first.outcome is CookPreparationOutcome.NEEDS_APPROVAL
    assert first.approval_kind is MoldCookApprovalKind.SCOPE

    resubmitted = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(scope_approval=approval, previous=first),
    )

    assert resubmitted.outcome is CookPreparationOutcome.NEEDS_PLANNING


def test_response_source_may_name_the_response_uri(tmp_path: Path) -> None:
    """An approval that cites its own response URI is bound, not malformed."""
    root = tmp_path / "uri-source"
    spec = _landing_spec(root)
    response_uri = (root / "scope-response.txt").as_uri()
    approval = _scope_approval_ref(
        root, _digest(spec.read_bytes()), ("root",), response_source=response_uri
    )

    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(scope_approval=approval),
    )

    assert result.outcome is CookPreparationOutcome.NEEDS_PLANNING


def test_absolute_response_source_is_reported_as_invalid_evidence(
    tmp_path: Path,
) -> None:
    """An unusable response_source is bad evidence, not malformed host input."""
    root = tmp_path / "absolute-source"
    spec = _landing_spec(root)
    approval = _scope_approval_ref(
        root,
        _digest(spec.read_bytes()),
        ("root",),
        response_source=str(root / "scope-response.txt"),
    )

    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(scope_approval=approval),
    )

    assert result.outcome is CookPreparationOutcome.INVALID
    assert [item.code for item in result.findings] == ["invalid-evidence"]


def test_a_host_type_error_is_reported_as_internal_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A TypeError from a host defect must not read as bad user evidence."""

    def explode(_ctx: object) -> object:
        raise TypeError("host defect reached the preparation pipeline")

    monkeypatch.setattr(pipeline, "resolve_preparation_source", explode)

    result = prepare(
        "implement the approved change",
        request_id="internal-error",
        repository_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
    )

    assert result.outcome is CookPreparationOutcome.INVALID
    assert [item.code for item in result.findings] == ["internal-error"]
