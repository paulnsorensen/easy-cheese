from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import (
    ArtifactRef,
    ContractVersion,
    canonical_bytes,
)
from easy_cheese_schemas.mold_cook import (
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    MOLD_COOK_HANDOFF_SCHEMA_URI,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
    MoldCookCoverage,
    MoldCookHandoff,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese.shared.mold_cook_handoff import (
    accept_mold_cook_handoff,
    canonical_mold_cook_proposal,
    materialize_artifact_ref,
    publish_mold_cook_handoff,
)
from easy_cheese.shared.publication import (
    PayloadDigestMismatchError,
    request_digest,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError

from tests.python.mold_cook_helpers import bind_mold_cook_approval


def _write_ref(
    root: Path,
    value: object,
    *,
    artifact_id: str,
    role: str,
    filename: str,
    media_type: str,
    schema_uri: str | None = None,
) -> ArtifactRef:
    payload = value if isinstance(value, bytes) else canonical_bytes(value)
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(payload)
    return materialize_artifact_ref(
        value,
        artifact_id=artifact_id,
        role=role,
        uri=f"repo://{filename}",
        media_type=media_type,
        schema_uri=schema_uri,
    )


def _published_handoff(
    root: Path,
    *,
    decision: MoldCookApprovalDecision = MoldCookApprovalDecision.APPROVED,
) -> tuple[Path, MoldCookHandoff]:
    spec_ref = _write_ref(
        root,
        (
            Path(__file__).parent / "fixtures" / "spec_format" / "valid_spec.md"
        ).read_bytes(),
        artifact_id="spec-1",
        role="spec",
        filename="spec.md",
        media_type="text/markdown",
    )
    coverage = MoldCookCoverage(curd_ids=["curd-1"])
    proposal_ref = _write_ref(
        root,
        canonical_mold_cook_proposal(
            request_id="request-1",
            kind=MoldCookApprovalKind.SCOPE,
            spec_digest=spec_ref.digest,
            coverage=coverage,
        ),
        artifact_id="proposal-1",
        role="proposal",
        filename="proposal.json",
        media_type="application/json",
    )
    response_ref = _write_ref(
        root,
        b"Approve",
        artifact_id="response-1",
        role="response",
        filename="response.txt",
        media_type="text/plain",
    )
    approval = bind_mold_cook_approval(
        request_id="request-1",
        kind=MoldCookApprovalKind.SCOPE,
        decision=decision,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=spec_ref.digest,
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source="response.txt",
        coverage=coverage,
    )
    approval_ref = _write_ref(
        root,
        approval,
        artifact_id="approval-1",
        role="approval",
        filename="approval.json",
        media_type="application/json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    taste_verdict_ref = _write_ref(
        root,
        b'{"verdict":"pass"}',
        artifact_id="taste-verdict",
        role="taste_verdict",
        filename="taste-verdict.json",
        media_type="application/json",
        schema_uri="https://schemas.easy-cheese.dev/fork-taste-verdict",
    )
    taste_ledger_ref = _write_ref(
        root,
        b"[]",
        artifact_id="taste-ledger",
        role="taste_ledger",
        filename="taste-ledger.json",
        media_type="application/json",
        schema_uri="https://schemas.easy-cheese.dev/taste-ledger",
    )
    handoff = MoldCookHandoff(
        contract_version=ContractVersion(
            schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI,
            major="1",
            minor="0",
        ),
        request_id="request-1",
        input_kind=MoldCookInputKind.DIRECT_SPEC,
        mode=MoldCookMode.LIGHT,
        spec_ref=spec_ref,
        approval_ref=approval_ref,
        coverage=coverage,
        taste_verdict_ref=taste_verdict_ref,
        taste_ledger_ref=taste_ledger_ref,
    )
    operation_id = "mold-cook-publication-1"
    digest = request_digest(
        "raw",
        {"request_id": handoff.request_id},
        source_phase="mold",
        destination_phase="cook",
        payload_schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI,
    )
    _ = publish_mold_cook_handoff(
        handoff,
        request_digest=digest,
        operation_id=operation_id,
        artifact_root=root,
    )
    return root / "pointers" / f"{operation_id}.json", handoff


def test_publish_and_accept_preserve_canonical_handoff_identity(tmp_path: Path) -> None:
    pointer_path, handoff = _published_handoff(tmp_path)

    accepted = accept_mold_cook_handoff(pointer_path, artifact_root=tmp_path)

    assert accepted.canonical.value == handoff
    assert accepted.canonical.canonical_bytes == canonical_bytes(handoff)
    assert accepted.normalization_receipt is None


def test_accept_rejects_stale_approval_reference(tmp_path: Path) -> None:
    pointer_path, _ = _published_handoff(tmp_path)
    approval_path = tmp_path / "approval.json"
    _ = approval_path.write_bytes(
        approval_path.read_bytes().replace(b"Approve", b"Reject!")
    )

    with pytest.raises(ContractValidationError, match="stale or corrupt"):
        _ = accept_mold_cook_handoff(pointer_path, artifact_root=tmp_path)


def test_accept_rejects_detached_pointer_payload(tmp_path: Path) -> None:
    pointer_path, _ = _published_handoff(tmp_path)
    pointer = cast(object, json.loads(pointer_path.read_text(encoding="utf-8")))
    assert isinstance(pointer, dict)
    payload = cast(dict[str, object], pointer)["payload"]
    assert isinstance(payload, dict)
    uri = cast(dict[str, object], payload)["uri"]
    assert isinstance(uri, str)
    payload_path = Path(uri.removeprefix("file://"))
    _ = payload_path.write_bytes(
        payload_path.read_bytes().replace(b"curd-1", b"curd-2")
    )

    with pytest.raises(PayloadDigestMismatchError, match="digest"):
        _ = accept_mold_cook_handoff(pointer_path, artifact_root=tmp_path)


def test_publish_rejects_approval_that_does_not_authorize_execution(
    tmp_path: Path,
) -> None:
    with pytest.raises(ContractValidationError, match="rejected response"):
        _ = _published_handoff(
            tmp_path,
            decision=MoldCookApprovalDecision.REJECTED,
        )
