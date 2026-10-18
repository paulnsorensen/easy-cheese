"""Canonical CurdPlan publication through the generic gateway."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared import publication
from easy_cheese_schemas import (
    BoundedScope,
    Criterion,
    CurdPlan,
    IdentityAction,
    IdentityLineage,
    SemanticCurd,
    canonical_bytes,
    supported_version_for,
    validate_contract,
)

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"


def _plan() -> CurdPlan:
    version = supported_version_for(CurdPlan)
    assert version is not None
    return CurdPlan.signed(
        contract_version=version,
        plan_id="publication-plan",
        revision=1,
        objective="Publish one canonical plan",
        curds=(
            SemanticCurd(
                curd_id="curd-1",
                outcome="Complete the bounded change",
                scope=BoundedScope(paths=["src/change.py"]),
                inputs=(),
                outputs=("change",),
                dependencies=(),
                criteria=(
                    Criterion("criterion-1", "Change passes", "focused test passes"),
                ),
                lineage=IdentityLineage(IdentityAction.NEW),
            ),
        ),
    )


def _published_plan(root: Path) -> tuple[Path, CurdPlan]:
    plan = _plan()
    operation_id = "mold-cook-publication-1"
    _ = publication.publish_canonical(
        request_digest=publication.request_digest(
            "raw",
            {"plan_id": plan.plan_id},
            source_phase="mold",
            destination_phase="cook",
            payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        ),
        source_phase="mold",
        destination_phase="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        operation_id=operation_id,
        artifact_root=root,
        prepare=lambda: validate_contract(
            canonical_bytes(plan), CurdPlan, supported_version_for(CurdPlan)
        ),
    )
    return root / "pointers" / f"{operation_id}.json", plan


def test_publish_and_accept_preserve_canonical_plan_identity(tmp_path: Path) -> None:
    pointer_path, plan = _published_plan(tmp_path)

    accepted = publication.accept(
        pointer_path,
        destination_phase="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        artifact_root=tmp_path,
    )

    assert accepted.canonical.value == plan
    assert accepted.canonical.canonical_bytes == canonical_bytes(plan)


def test_accept_rejects_detached_pointer_payload(tmp_path: Path) -> None:
    pointer_path, _ = _published_plan(tmp_path)
    pointer = cast(
        dict[str, object], json.loads(pointer_path.read_text(encoding="utf-8"))
    )
    payload = cast(dict[str, object], pointer["payload"])
    uri = cast(str, payload["uri"])
    payload_path = Path(uri.removeprefix("file://"))
    _ = payload_path.write_bytes(
        payload_path.read_bytes().replace(b"curd-1", b"curd-2")
    )

    with pytest.raises(publication.PayloadDigestMismatchError, match="digest"):
        _ = publication.accept(
            pointer_path,
            destination_phase="cook",
            payload_schema_uri=CURD_PLAN_SCHEMA_URI,
            artifact_root=tmp_path,
        )
