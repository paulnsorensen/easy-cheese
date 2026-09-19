"""End-to-end coverage for the Cook bundle's canonical handoff acceptance."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import ArtifactRef, ContractVersion, canonical_bytes
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
    bind_mold_cook_approval,
    canonical_mold_cook_proposal,
    materialize_artifact_ref,
    validate_mold_cook_approval,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared.publication import (
    publish_mold_cook_handoff,
    request_digest,
)

COOK_PYZ = (
    Path(__file__).resolve().parents[2] / "skills" / "cook" / "scripts" / "cook.pyz"
)

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("pip") is None
    or (shutil.which("shiv") is None and importlib.util.find_spec("shiv") is None),
    reason="bundle integration requires requirements-build.txt",
)


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


def published_handoff(
    root: Path, operation_id: str
) -> tuple[Path, MoldCookHandoff, Path]:
    root.mkdir(parents=True, exist_ok=True)
    spec_path = root / "spec.md"
    spec_bytes = (
        Path(__file__).parent / "fixtures" / "spec_format" / "valid_spec.md"
    ).read_bytes()
    spec_ref = _write_ref(
        root,
        spec_bytes,
        artifact_id="spec-1",
        role="spec",
        filename="spec.md",
        media_type="text/markdown",
    )
    coverage_factory = cast("Callable[..., MoldCookCoverage]", MoldCookCoverage)
    coverage = coverage_factory(curd_ids=["curd-1"])
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
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.USER_RESPONSE,
        spec_digest=spec_ref.digest,
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source="response.txt",
        coverage=coverage,
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
    approval_ref = _write_ref(
        root,
        approval,
        artifact_id="approval-1",
        role="approval",
        filename="approval.json",
        media_type="application/json",
        schema_uri=MOLD_COOK_APPROVAL_SCHEMA_URI,
    )
    version_factory = cast("Callable[..., ContractVersion]", ContractVersion)
    handoff_factory = cast("Callable[..., MoldCookHandoff]", MoldCookHandoff)
    handoff = handoff_factory(
        contract_version=version_factory(
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
    return root / "pointers" / f"{operation_id}.json", handoff, spec_path


@pytest.mark.parametrize(
    ("dialogue", "message"),
    [
        ({"response": "Approve"}, "presented question"),
        ({"question": "Approve this plan?"}, "absent from or detached"),
    ],
)
def test_local_dialogue_requires_the_question_and_exact_response(
    tmp_path: Path, dialogue: dict[str, str], message: str
) -> None:
    proposal_ref = _write_ref(
        tmp_path,
        b'{"decision":"approve"}',
        artifact_id="proposal-1",
        role="proposal",
        filename="proposal.json",
        media_type="application/json",
    )
    response_ref = _write_ref(
        tmp_path,
        dialogue,
        artifact_id="dialogue-1",
        role="dialogue",
        filename="dialogue.json",
        media_type="application/json",
    )
    coverage_factory = cast("Callable[..., MoldCookCoverage]", MoldCookCoverage)
    approval = bind_mold_cook_approval(
        request_id="request-1",
        kind=MoldCookApprovalKind.SCOPE,
        decision=MoldCookApprovalDecision.APPROVED,
        source=MoldCookApprovalSource.LOCAL_DIALOGUE,
        spec_digest="sha256:" + ("a" * 64),
        proposal_ref=proposal_ref,
        response_ref=response_ref,
        response_text="Approve",
        response_source="dialogue.json",
        coverage=coverage_factory(curd_ids=["curd-1"]),
    )

    with pytest.raises(ContractValidationError, match=message):
        _ = validate_mold_cook_approval(approval, tmp_path)


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(COOK_PYZ), *args],
        cwd=str(COOK_PYZ.parent if cwd is None else cwd),
        capture_output=True,
        text=True,
        env=env,
    )


def _accept(pointer_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return _run("accept", str(pointer_path), *extra_args)


def _assert_canonical_wrapper(stdout: str) -> dict[str, object]:
    wrapper = cast(dict[str, object], json.loads(stdout))
    assert sorted(wrapper) == ["digest", "normalization_receipt", "value"]
    digest = cast(str, wrapper["digest"])
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
    value = cast(dict[str, object], wrapper["value"])
    assert value["request_id"] == "request-1"
    assert value["input_kind"] == MoldCookInputKind.DIRECT_SPEC.value
    assert value["mode"] == MoldCookMode.LIGHT.value
    coverage = cast(dict[str, object], value["coverage"])
    assert coverage["curd_ids"] == ["curd-1"]
    assert coverage["unresolved_work"] == []
    return wrapper


def test_cook_pyz_accepts_a_real_mold_handoff_pointer(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-happy"
    )

    result = _accept(pointer_path)

    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = _assert_canonical_wrapper(result.stdout)
    assert wrapper["normalization_receipt"] is None


def test_cook_pyz_accepts_the_same_pointer_idempotently(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-repeat"
    )

    first = _accept(pointer_path)
    second = _accept(pointer_path)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert second.stdout == first.stdout


def test_cook_pyz_rejects_a_tampered_payload(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-tampered"
    )
    pointer = cast(
        dict[str, object], json.loads(pointer_path.read_text(encoding="utf-8"))
    )
    payload = cast(dict[str, object], pointer["payload"])
    payload_path = Path(cast(str, payload["uri"]).removeprefix("file://"))
    _ = payload_path.write_bytes(b"tampered handoff")

    result = _accept(pointer_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "mismatch" in result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_wrong_destination_route(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-route"
    )
    pointer = cast(
        dict[str, object], json.loads(pointer_path.read_text(encoding="utf-8"))
    )
    pointer["destination_phase"] = "age"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    result = _accept(pointer_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "'age'" in result.stderr
    assert "'cook'" in result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_pointer_with_the_old_plan_schema(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-old-plan"
    )
    pointer = cast(
        dict[str, object], json.loads(pointer_path.read_text(encoding="utf-8"))
    )
    payload = cast(dict[str, object], pointer["payload"])
    payload["schema_uri"] = "https://schemas.easy-cheese.dev/curd-plan"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    result = _accept(pointer_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "https://schemas.easy-cheese.dev/curd-plan" in result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_bare_handoff_payload(tmp_path: Path) -> None:
    pointer_path, handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-bare"
    )
    bare_payload = tmp_path / "bare-handoff.json"
    _ = bare_payload.write_bytes(canonical_bytes(handoff))

    result = _accept(bare_payload)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "schema" in result.stderr
    assert result.stdout == ""
    assert pointer_path.is_file()


def test_cook_pyz_rejects_a_missing_payload_file(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-missing-payload"
    )
    pointer = cast(
        dict[str, object], json.loads(pointer_path.read_text(encoding="utf-8"))
    )
    payload = cast(dict[str, object], pointer["payload"])
    payload_path = Path(cast(str, payload["uri"]).removeprefix("file://"))
    payload_path.unlink()

    result = _accept(pointer_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "artifact is not readable" in result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_missing_pointer_file(tmp_path: Path) -> None:
    missing_pointer = tmp_path / "does-not-exist.json"

    result = _accept(missing_pointer)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "pointer not found at" in result.stderr
    assert result.stdout == ""


def test_cook_pyz_accepts_a_relative_pointer_with_an_explicit_artifact_root(
    tmp_path: Path,
) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-relative"
    )

    result = _run(
        "accept",
        pointer_path.name,
        "--artifact-root",
        str(pointer_path.parent.parent),
        cwd=pointer_path.parent,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    _ = _assert_canonical_wrapper(result.stdout)


def test_cook_pyz_uses_spec_only_as_a_digest_assertion(tmp_path: Path) -> None:
    pointer_path, _handoff, spec_path = published_handoff(
        tmp_path / "artifacts", "op-spec"
    )
    matching = _accept(pointer_path, "--spec", str(spec_path))
    mismatch_path = tmp_path / "different.md"
    _ = mismatch_path.write_text("# Different spec\n", encoding="utf-8")
    mismatched = _accept(pointer_path, "--spec", str(mismatch_path))

    assert matching.returncode == 0, matching.stdout + matching.stderr
    _ = _assert_canonical_wrapper(matching.stdout)
    assert mismatched.returncode == 1, mismatched.stdout + mismatched.stderr
    assert "--spec does not match" in mismatched.stderr
    assert mismatched.stdout == ""


def test_cook_pyz_rejects_a_missing_spec_file(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-missing-spec"
    )
    missing_spec = tmp_path / "does-not-exist.md"

    result = _accept(pointer_path, "--spec", str(missing_spec))

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_non_utf8_spec_without_a_traceback(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-binary-spec"
    )
    spec_path = tmp_path / "binary.md"
    _ = spec_path.write_bytes(b"\xff\xfe")

    result = _accept(pointer_path, "--spec", str(spec_path))

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_spec_that_is_not_a_regular_file(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-dir-spec"
    )

    result = _accept(pointer_path, "--spec", str(tmp_path))

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cook_pyz_rejects_a_spec_larger_than_the_byte_cap(tmp_path: Path) -> None:
    pointer_path, _handoff, _spec_path = published_handoff(
        tmp_path / "artifacts", "op-huge-spec"
    )
    spec_path = tmp_path / "huge.md"
    _ = spec_path.write_bytes(b"x" * 1_000_001)

    result = _accept(pointer_path, "--spec", str(spec_path))

    assert result.returncode == 1, result.stdout + result.stderr
    assert "larger than 1000000 bytes" in result.stderr
    assert result.stdout == ""
