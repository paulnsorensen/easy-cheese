"""Direct tests for the shared Mold-to-Cook validation seam."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import ArtifactRef, canonical_bytes
from easy_cheese_schemas.mold_cook import (
    CookSetupAuthorization,
    MoldCookApproval,
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookApprovalSource,
    MoldCookCoverage,
    MoldCookHandoff,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError

from easy_cheese.shared import mold_cook_handoff, taste_test
from easy_cheese.shared.mold_cook_handoff import (
    canonical_mold_cook_proposal,
    dialogue_authorizes_execution,
    materialize_artifact_ref,
    publish_mold_cook_handoff,
    resolve_contract_value,
    validate_mold_cook_approval,
    validate_mold_cook_handoff,
)

from tests.python.mold_cook_helpers import bind_mold_cook_approval

SPEC_DIGEST = "sha256:" + ("a" * 64)


def _write_ref(
    root: Path,
    value: object,
    *,
    artifact_id: str,
    role: str,
    filename: str,
    media_type: str,
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
    )


def _scope_approval(
    root: Path,
    *,
    response_text: str,
    response_ref: ArtifactRef,
    source: MoldCookApprovalSource = MoldCookApprovalSource.USER_RESPONSE,
) -> MoldCookApproval:
    coverage = MoldCookCoverage(curd_ids=["curd-1"])
    proposal_ref = _write_ref(
        root,
        canonical_mold_cook_proposal(
            request_id="request-1",
            kind=MoldCookApprovalKind.SCOPE,
            spec_digest=SPEC_DIGEST,
            coverage=coverage,
        ),
        artifact_id="proposal-1",
        role="proposal",
        filename="proposal.json",
        media_type="application/json",
    )
    return bind_mold_cook_approval(
        request_id="request-1",
        kind=MoldCookApprovalKind.SCOPE,
        decision=MoldCookApprovalDecision.APPROVED,
        source=source,
        spec_digest=SPEC_DIGEST,
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text=response_text,
        response_source=response_ref.artifact_id,
        coverage=coverage,
    )


@pytest.mark.parametrize(
    "validator", [validate_mold_cook_approval, validate_mold_cook_handoff]
)
def test_exported_validators_require_an_explicit_artifact_root(
    validator: Callable[..., object],
) -> None:
    """Finding 2: no root default, so validation never falls back to the cwd."""

    parameter = inspect.signature(validator).parameters["artifact_root"]

    assert cast("object", parameter.default) is inspect.Parameter.empty
    with pytest.raises(TypeError):
        _ = validator(object())


def test_validation_refuses_a_remote_artifact_scheme(tmp_path: Path) -> None:
    """Finding 5: a handoff-authored URI cannot choose an egress destination."""

    response_ref = materialize_artifact_ref(
        b"Approve",
        artifact_id="response-1",
        role="response",
        uri="https://example.invalid/response.txt",
        media_type="text/plain",
    )
    approval = _scope_approval(
        tmp_path, response_text="Approve", response_ref=response_ref
    )

    with pytest.raises(ContractValidationError, match="unsupported URI scheme"):
        _ = validate_mold_cook_approval(approval, tmp_path)


@pytest.mark.parametrize("response_text", ["nope", "not yet", "hold off", "No."])
def test_unrecognized_response_text_is_not_consent(
    tmp_path: Path, response_text: str
) -> None:
    """Finding 3: only a recognized affirmative token approves."""

    response_ref = _write_ref(
        tmp_path,
        response_text.encode("utf-8"),
        artifact_id="response-1",
        role="response",
        filename="response.txt",
        media_type="text/plain",
    )
    approval = _scope_approval(
        tmp_path, response_text=response_text, response_ref=response_ref
    )

    with pytest.raises(ContractValidationError, match="negative or unresolved"):
        _ = validate_mold_cook_approval(approval, tmp_path)


@pytest.mark.parametrize("affirmative", ["Approve", "approved", "yes", "LGTM."])
def test_recognized_affirmative_response_still_validates(
    tmp_path: Path, affirmative: str
) -> None:
    response_ref = _write_ref(
        tmp_path,
        affirmative.encode("utf-8"),
        artifact_id="response-1",
        role="response",
        filename="response.txt",
        media_type="text/plain",
    )
    approval = _scope_approval(
        tmp_path, response_text=affirmative, response_ref=response_ref
    )

    assert validate_mold_cook_approval(approval, tmp_path) is approval


@pytest.mark.parametrize(
    "dialogue",
    [
        {"question": "Approve?", "response": "Approve", "clear_holds": ["hold-1"]},
        {"question": "Approve?", "response": "Approve", "execution_authorized": True},
        {
            "question": "Approve?",
            "response": "Approve",
            "clear_holds": ["hold-1"],
            "execution_authorized": "yes",
        },
        {
            "question": "Approve?",
            "response": "Approve",
            "clear_holds": [],
            "execution_authorized": True,
        },
    ],
)
def test_dialogue_authorization_must_be_affirmative_and_explicit(
    tmp_path: Path, dialogue: dict[str, object]
) -> None:
    """Finding 4: a missing or untyped authorization key is never consent."""

    response_ref = _write_ref(
        tmp_path,
        dialogue,
        artifact_id="dialogue-1",
        role="dialogue",
        filename="dialogue.json",
        media_type="application/json",
    )
    approval = _scope_approval(
        tmp_path,
        response_text="Approve",
        response_ref=response_ref,
        source=MoldCookApprovalSource.LOCAL_DIALOGUE,
    )

    with pytest.raises(ContractValidationError, match="does not authorize execution"):
        _ = validate_mold_cook_approval(approval, tmp_path)


def test_dialogue_that_names_its_cleared_holds_authorizes_execution(
    tmp_path: Path,
) -> None:
    dialogue = {
        "question": "Approve?",
        "response": "Approve",
        "clear_holds": ["hold-1"],
        "execution_authorized": True,
    }
    response_ref = _write_ref(
        tmp_path,
        dialogue,
        artifact_id="dialogue-1",
        role="dialogue",
        filename="dialogue.json",
        media_type="application/json",
    )
    approval = _scope_approval(
        tmp_path,
        response_text="Approve",
        response_ref=response_ref,
        source=MoldCookApprovalSource.LOCAL_DIALOGUE,
    )

    assert dialogue_authorizes_execution(dialogue) is True
    assert validate_mold_cook_approval(approval, tmp_path) is approval


def test_runner_approval_is_bound_to_its_own_canonical_envelope(
    tmp_path: Path,
) -> None:
    """Finding 10: a widened setup envelope cannot ride an approval through."""

    coverage = MoldCookCoverage(curd_ids=["curd-1"])
    authorized = CookSetupAuthorization(
        prerequisite_curd_id="setup",
        allowed_paths=("src/",),
        allowed_commands=("just build",),
    )
    widened = CookSetupAuthorization(
        prerequisite_curd_id="setup",
        allowed_paths=("src/", "docs/"),
        allowed_commands=("just build", "curl"),
    )
    proposal_ref = _write_ref(
        tmp_path,
        canonical_mold_cook_proposal(
            request_id="request-1",
            kind=MoldCookApprovalKind.RUNNER,
            spec_digest=SPEC_DIGEST,
            coverage=coverage,
            setup_authorization=widened,
        ),
        artifact_id="proposal-1",
        role="proposal",
        filename="proposal.json",
        media_type="application/json",
    )
    response_ref = _write_ref(
        tmp_path,
        b"Approve",
        artifact_id="response-1",
        role="response",
        filename="response.txt",
        media_type="text/plain",
    )
    approval = bind_mold_cook_approval(
        request_id="request-1",
        kind=MoldCookApprovalKind.RUNNER,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=SPEC_DIGEST,
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source="response-1",
        coverage=coverage,
        setup_authorization=authorized,
    )

    with pytest.raises(ContractValidationError, match="canonical envelope"):
        _ = validate_mold_cook_approval(approval, tmp_path)


def test_typed_mold_document_is_a_public_taste_test_export() -> None:
    """Finding 75: the shared seam imports a supported name."""

    assert "typed_mold_document" in taste_test.__all__
    assert taste_test.typed_mold_document is not None


PLAN_DIGEST = "sha256:" + ("b" * 64)


def _plan_approval(root: Path, *, proposal_bytes: bytes) -> MoldCookApproval:
    coverage = MoldCookCoverage(curd_ids=["curd-1"])
    proposal_ref = _write_ref(
        root,
        proposal_bytes,
        artifact_id="plan-proposal-1",
        role="proposal",
        filename="plan-proposal.json",
        media_type="application/json",
    )
    response_ref = _write_ref(
        root,
        b"Approve",
        artifact_id="plan-response-1",
        role="response",
        filename="plan-response.txt",
        media_type="text/plain",
    )
    return bind_mold_cook_approval(
        request_id="request-1",
        kind=MoldCookApprovalKind.PLAN,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=SPEC_DIGEST,
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source=response_ref.artifact_id,
        coverage=coverage,
        plan_digest=PLAN_DIGEST,
    )


def test_a_supplied_envelope_binds_a_plan_approval(tmp_path: Path) -> None:
    """A plan approval cannot rebuild its envelope, so the caller supplies it."""

    envelope = b'{"kind": "plan", "request_id": "request-1"}'
    approval = _plan_approval(tmp_path, proposal_bytes=envelope)

    assert (
        validate_mold_cook_approval(approval, tmp_path, expected_proposal=envelope)
        is approval
    )


def test_a_plan_approval_is_rejected_when_the_supplied_envelope_differs(
    tmp_path: Path,
) -> None:
    """A supplied envelope binds every kind, including the plan kinds."""

    approval = _plan_approval(
        tmp_path, proposal_bytes=b'{"kind": "plan", "request_id": "request-1"}'
    )

    with pytest.raises(ContractValidationError, match="canonical envelope"):
        _ = validate_mold_cook_approval(
            approval,
            tmp_path,
            expected_proposal=b'{"kind": "plan", "request_id": "request-2"}',
        )


def test_a_plan_approval_stays_self_unbound_without_an_expected_envelope(
    tmp_path: Path,
) -> None:
    """Omitting the envelope keeps the pre-existing self-bound kinds only."""

    approval = _plan_approval(
        tmp_path, proposal_bytes=b'{"kind": "plan", "request_id": "request-1"}'
    )

    assert validate_mold_cook_approval(approval, tmp_path) is approval


@pytest.mark.parametrize("shape", ["instance", "bytes", "mapping", "path"])
def test_resolve_contract_value_validates_every_producer_input_shape(
    tmp_path: Path, shape: str
) -> None:
    """Finding 61: one seam types the four shapes a producer holds."""

    approval = _plan_approval(tmp_path, proposal_bytes=b'{"kind": "plan"}')
    payload = canonical_bytes(approval)
    document = tmp_path / "approval.json"
    _ = document.write_bytes(payload)
    value: object = {
        "instance": approval,
        "bytes": payload,
        "mapping": cast("dict[str, object]", json.loads(payload)),
        "path": document,
    }[shape]

    assert resolve_contract_value(value, MoldCookApproval, tmp_path) == approval


def test_resolve_contract_value_rejects_an_unsupported_input_type(
    tmp_path: Path,
) -> None:
    """A value the seam cannot type is never structured into a contract."""

    with pytest.raises(ContractValidationError, match="from a int value"):
        _ = resolve_contract_value(7, MoldCookApproval, tmp_path)


def test_resolve_contract_value_reads_a_path_outside_the_artifact_root(
    tmp_path: Path,
) -> None:
    """An operator names the contract path; the retention root does not bound it."""

    approval = _plan_approval(tmp_path, proposal_bytes=b'{"kind": "plan"}')
    document = tmp_path / "approval.json"
    _ = document.write_bytes(canonical_bytes(approval))
    root = tmp_path / "artifacts"
    root.mkdir()

    assert resolve_contract_value(document, MoldCookApproval, root) == approval


def test_resolve_contract_value_refuses_a_symlinked_contract_path(
    tmp_path: Path,
) -> None:
    """A symlink still cannot redirect the read to another file."""

    approval = _plan_approval(tmp_path, proposal_bytes=b'{"kind": "plan"}')
    document = tmp_path / "approval.json"
    _ = document.write_bytes(canonical_bytes(approval))
    link = tmp_path / "link.json"
    link.symlink_to(document)

    with pytest.raises(ContractValidationError, match="is unreadable"):
        _ = resolve_contract_value(link, MoldCookApproval, tmp_path)


def test_publish_reports_an_unsupported_host_version_as_a_contract_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The publish seam answers a host defect with its own error type."""

    def unsupported(_contract: object) -> str:
        raise TypeError("MoldCookHandoff has no supported contract version")

    monkeypatch.setattr(mold_cook_handoff, "require_contract_version", unsupported)

    with pytest.raises(ContractValidationError, match="no supported contract version"):
        _ = publish_mold_cook_handoff(
            cast("MoldCookHandoff", object()),
            request_digest=SPEC_DIGEST,
            operation_id="publish-host-defect",
            artifact_root=tmp_path,
        )


def test_resolve_contract_value_rejects_bytes_that_are_not_the_contract(
    tmp_path: Path,
) -> None:
    """Bytes of the wrong document fail against the host-supported version."""

    with pytest.raises(ContractValidationError, match="not a valid MoldCookApproval"):
        _ = resolve_contract_value(b'{"kind": "plan"}', MoldCookApproval, tmp_path)
