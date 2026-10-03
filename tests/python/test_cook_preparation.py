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
    CookPreparationOutcome,
    CookSetupAuthorization,
    MoldCookCoverage,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese.shared import paths
from easy_cheese.skills.mold import validate_spec
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
    assert result.outcome is CookPreparationOutcome.NEEDS_PLANNING
    assert result.approved_scope_ref is not None
    assert result.approved_scope_ref.role == "approved_scope"
    assert result.approved_scope_ref.digest in {
        reference.digest for reference in result.references if reference.role == "spec"
    }


def test_direct_spec_without_execution_holds_reaches_planning(
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

    assert result.outcome is CookPreparationOutcome.NEEDS_PLANNING
    assert result.holds == ()


@pytest.mark.parametrize(
    "declaration",
    [
        "execution_holds:\n  - scope-audit-row-3-needs-a-verb\n",
        'execution_holds: ["scope-audit-row-3-needs-a-verb"]\n',
    ],
    ids=["block", "flow"],
)
def test_direct_spec_execution_holds_block_preparation(
    tmp_path: Path, declaration: str
) -> None:
    """A Mold draft's unresolved holds must survive the direct `/cook <spec>` path."""
    fixture = _SPEC_FIXTURE.read_text(encoding="utf-8")
    assert fixture.startswith("---\n")
    spec_path = tmp_path / f"{_SPEC_SLUG}.md"
    _ = spec_path.write_text(
        "---\n" + declaration + fixture[len("---\n") :],
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


def test_full_spec_reaches_planning_without_approval_evidence(
    tmp_path: Path,
) -> None:
    """Cook proceeds on invocation: a Full spec needs no scope approval."""
    root = tmp_path / "no-approval"
    spec = _landing_spec(root)

    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
    )

    assert result.outcome is CookPreparationOutcome.NEEDS_PLANNING
    assert result.approved_scope_ref is not None
    assert result.approved_scope_ref.digest == _digest(spec.read_bytes())
    assert result.planner_request is not None


def test_full_plan_reaches_ready_without_approval_evidence(tmp_path: Path) -> None:
    """A planner result carried into a second round is ready with no approval."""
    root = tmp_path / "carried"
    spec = _landing_spec(root)
    plan = _signed_plan()
    planner = PlannerResult(
        contract_version=require_contract_version(PlannerResult),
        request_id="cook-request",
        disposition=PlannerDisposition.COMPLETE,
        plan=plan,
    )

    scope_round = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
    )
    assert scope_round.outcome is CookPreparationOutcome.NEEDS_PLANNING

    carried = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        evidence=PreparationEvidence(planner_result=planner, previous=scope_round),
    )

    assert carried.outcome is CookPreparationOutcome.READY
    assert carried.coverage == MoldCookCoverage(curd_ids=("root",))
    assert [ref.role for ref in carried.references].count("curd_plan") == 1
    assert carried.requirements == ()


def test_light_plan_with_one_curd_reaches_ready_without_approval(
    tmp_path: Path,
) -> None:
    """Light scope is exactly one curd and needs no scope approval."""
    root = tmp_path / "light"
    spec = _landing_spec(root)
    plan = _signed_plan()
    planner = PlannerResult(
        contract_version=require_contract_version(PlannerResult),
        request_id="cook-request",
        disposition=PlannerDisposition.COMPLETE,
        plan=plan,
    )

    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        mode=MoldCookMode.LIGHT,
        evidence=PreparationEvidence(planner_result=planner),
    )

    assert result.outcome is CookPreparationOutcome.READY
    assert result.coverage == MoldCookCoverage(curd_ids=("root",))


def test_light_scope_without_a_declared_curd_holds_with_a_scope_requirement(
    tmp_path: Path,
) -> None:
    root = tmp_path / "light-none"
    root.mkdir()
    spec = root / "spec.md"
    _ = shutil.copy(_SPEC_FIXTURE, spec)

    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        mode=MoldCookMode.LIGHT,
    )

    assert [item.requirement_id for item in result.requirements] == [
        "light-scope-cook-request"
    ]
    assert result.outcome is CookPreparationOutcome.BLOCKED


def test_light_scope_with_two_curds_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "light-two"
    spec = _landing_spec(root)
    two_curds = spec.read_text(encoding="utf-8").replace(
        'layers: [["root"]]', 'layers: [["root"], ["second"]]'
    )
    _ = spec.write_text(two_curds, encoding="utf-8")

    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
        mode=MoldCookMode.LIGHT,
    )

    assert result.outcome is CookPreparationOutcome.INVALID
    assert [finding.message for finding in result.findings] == [
        "Light scope must name exactly one resolved curd"
    ]


def test_full_resubmission_rejects_changed_bound_spec(tmp_path: Path) -> None:
    root = tmp_path / "changed-bound-spec"
    spec = _landing_spec(root)
    first = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
    )
    assert first.outcome is CookPreparationOutcome.NEEDS_PLANNING

    _ = spec.write_text(spec.read_text(encoding="utf-8") + "\nChanged scope.\n")
    changed = pipeline.resubmit(
        first,
        source=spec,
        repository_root=tmp_path,
        artifact_root=root,
    )
    assert changed.outcome is CookPreparationOutcome.INVALID
    assert b"changed the bound spec" in canonical_bytes(changed)


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


def test_spec_with_a_removed_gate_applicability_block_still_validates_and_prepares(
    tmp_path: Path,
) -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "spec_format"
        / "legacy_gate_applicability_spec.md"
    )
    assert "gate_applicability:" in fixture.read_text(encoding="utf-8")

    errors, _notice = validate_spec.validate(fixture)
    assert errors == []

    root = tmp_path / "legacy-gate"
    root.mkdir()
    spec = root / "spec.md"
    _ = shutil.copy(fixture, spec)
    result = prepare(
        spec,
        request_id="cook-request",
        repository_root=tmp_path,
        artifact_root=root,
    )

    assert result.outcome is CookPreparationOutcome.NEEDS_PLANNING
