"""Direct tests for the surviving Mold-to-Cook artifact seam."""

from __future__ import annotations

import json
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
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared.mold_cook_handoff import (
    materialize_artifact_ref,
    resolve_contract,
    resolve_contract_value,
    request_directive,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("---\nrequest_directive: do-not-implement\n---\n", "do-not-implement"),
        ("---\nexecution_directive:\n  decision: DO_NOT_PROCEED\n---\n", "do-not-proceed"),
        ("---\nwhole_request_directive:\n  intent: do not implement\n---\n", "do-not-implement"),
        ("---\nstatus: approved\n---\n## Whole-request Directive\n- action: do-not-proceed\n", "do-not-proceed"),
    ],
)
def test_request_directive_accepts_existing_spellings(text: str, expected: str) -> None:
    assert request_directive(text) == expected


def _plan() -> CurdPlan:
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
                check="focused test passes",
            ),
        ),
        lineage=IdentityLineage(IdentityAction.NEW),
    )
    return CurdPlan.signed(
        contract_version=require_contract_version(CurdPlan),
        plan_id="bound-plan",
        revision=1,
        objective="Execute the selected work",
        curds=(curd,),
    )


@pytest.mark.parametrize("shape", ["instance", "bytes", "mapping", "path"])
def test_resolve_contract_value_validates_every_producer_input_shape(
    tmp_path: Path, shape: str
) -> None:
    plan = _plan()
    payload = canonical_bytes(plan)
    document = tmp_path / "plan.json"
    _ = document.write_bytes(payload)
    value: object = {
        "instance": plan,
        "bytes": payload,
        "mapping": cast(dict[str, object], json.loads(payload)),
        "path": document,
    }[shape]

    assert resolve_contract_value(value, CurdPlan, tmp_path) == plan


def test_resolve_contract_value_rejects_unsupported_and_wrong_content(
    tmp_path: Path,
) -> None:
    with pytest.raises(ContractValidationError, match="from a int value"):
        _ = resolve_contract_value(7, CurdPlan, tmp_path)
    with pytest.raises(ContractValidationError, match="not a valid CurdPlan"):
        _ = resolve_contract_value(b'{"kind":"other"}', CurdPlan, tmp_path)


def test_resolve_contract_value_rejects_symlinked_contract_path(
    tmp_path: Path,
) -> None:
    document = tmp_path / "plan.json"
    _ = document.write_bytes(canonical_bytes(_plan()))
    link = tmp_path / "link.json"
    link.symlink_to(document)

    with pytest.raises(ContractValidationError, match="is unreadable"):
        _ = resolve_contract_value(link, CurdPlan, tmp_path)


def test_resolve_contract_rejects_remote_and_stale_references(tmp_path: Path) -> None:
    plan = _plan()
    content = canonical_bytes(plan)
    document = tmp_path / "plan.json"
    _ = document.write_bytes(content)
    reference = materialize_artifact_ref(
        plan,
        artifact_id="plan",
        role="curd_plan",
        uri=document.as_uri(),
        media_type="application/json",
    )
    assert resolve_contract(reference, CurdPlan, tmp_path).value == plan

    remote = ArtifactRef(
        artifact_id="remote",
        role="curd_plan",
        uri="https://example.invalid/plan.json",
        digest=reference.digest,
        size_bytes=reference.size_bytes,
        media_type="application/json",
    )
    with pytest.raises(ContractValidationError, match="unsupported URI scheme"):
        _ = resolve_contract(remote, CurdPlan, tmp_path)

    _ = document.write_bytes(content.replace(b"bound-plan", b"other-plan"))
    with pytest.raises(ContractValidationError, match="stale or corrupt"):
        _ = resolve_contract(reference, CurdPlan, tmp_path)