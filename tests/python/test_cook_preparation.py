"""The retained runner evidence must match the selected plan and limits."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import ArtifactRef, canonical_bytes, require_contract_version
from easy_cheese_schemas.contracts import (
    BoundedScope,
    Criterion,
    CurdPlan,
    IdentityAction,
    IdentityLineage,
    SemanticCurd,
)
from easy_cheese_schemas.mold_cook import CookSetupAuthorization
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared.mold_cook_handoff import (
    SETUP_EVIDENCE_SCHEMA_URI,
    SetupEvidence,
    SetupEvidenceExecutionError,
    validate_mold_cook_setup_evidence,
)
from easy_cheese.shared.wheypoint.canonical import digest_bytes


def _plan() -> CurdPlan:
    curd = SemanticCurd(
        curd_id="setup",
        outcome="Run setup",
        scope=BoundedScope(paths=["tests/setup.py"]),
        inputs=(),
        outputs=("setup-result",),
        dependencies=(),
        criteria=(
            Criterion(
                criterion_id="setup-criterion",
                description="setup passes",
                check="focused test passes",
            ),
        ),
        lineage=IdentityLineage(IdentityAction.NEW),
    )
    return CurdPlan.signed(
        contract_version=require_contract_version(CurdPlan),
        plan_id="setup-plan",
        revision=1,
        objective="Run bounded setup",
        curds=(curd,),
    )


def _retain(root: Path, content: bytes, *, role: str, schema_uri: str | None = None) -> ArtifactRef:
    digest = digest_bytes(content)
    path = root / f"sha256-{digest.removeprefix('sha256:')}"
    _ = path.write_bytes(content)
    return ArtifactRef(
        artifact_id=role,
        role=role,
        uri=path.as_uri(),
        digest=digest,
        size_bytes=len(content),
        media_type="application/json",
        schema_uri=schema_uri,
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"plan_digest": "sha256:" + "0" * 64}, "stale for this plan"),
        ({"runner_command": "curl remote"}, "outside approved commands"),
        ({"fixture_path": "other/setup.py"}, "outside approved paths"),
        ({"exit_code": 1}, "setup runner did not pass"),
    ],
)
def test_setup_evidence_enforces_plan_and_runner_limits(
    tmp_path: Path, change: dict[str, object], reason: str
) -> None:
    plan = _plan()
    authorization = CookSetupAuthorization(
        prerequisite_curd_id="setup",
        allowed_paths=("tests/setup.py",),
        allowed_commands=("python -m pytest tests/setup.py",),
    )
    output = b"setup passed\n"
    _ = _retain(tmp_path, output, role="setup_output")
    values: dict[str, object] = {
        "prerequisite_curd_id": "setup",
        "plan_digest": plan.digest,
        "authorization_digest": digest_bytes(canonical_bytes(authorization)),
        "runner_command": "python -m pytest tests/setup.py",
        "fixture_path": "tests/setup.py",
        "environment_id": "test-env",
        "exit_code": 0,
        "captured_output_digest": digest_bytes(output),
    }
    reference = _retain(
        tmp_path,
        canonical_bytes(SetupEvidence.from_mapping(values)),
        role="setup_evidence",
        schema_uri=SETUP_EVIDENCE_SCHEMA_URI,
    )
    assert validate_mold_cook_setup_evidence(
        reference, authorization=authorization, plan=plan, artifact_root=tmp_path
    ).plan_digest == plan.digest

    values.update(change)
    changed_ref = _retain(
        tmp_path,
        canonical_bytes(SetupEvidence.from_mapping(values)),
        role="setup_evidence",
        schema_uri=SETUP_EVIDENCE_SCHEMA_URI,
    )
    error = SetupEvidenceExecutionError if "exit_code" in change else ContractValidationError
    with pytest.raises(error, match=reason):
        _ = validate_mold_cook_setup_evidence(
            changed_ref, authorization=authorization, plan=plan, artifact_root=tmp_path
        )
