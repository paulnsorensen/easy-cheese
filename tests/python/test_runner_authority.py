"""Runner authority stays bound to a retained response and exact setup limits."""

from pathlib import Path

import pytest

from easy_cheese_schemas import ArtifactRef, canonical_bytes, canonical_digest
from easy_cheese_schemas.mold_cook import CookSetupAuthorization, MoldCookCoverage
from easy_cheese.shared.mold_cook_handoff import validate_runner_authority
from easy_cheese.shared.wheypoint.canonical import digest_bytes


def _ref(root: Path, name: str, content: bytes, role: str) -> ArtifactRef:
    digest = digest_bytes(content)
    path = root / f"sha256-{digest.removeprefix('sha256:')}"
    _ = path.write_bytes(content)
    return ArtifactRef(
        artifact_id=name,
        role=role,
        uri=path.as_uri(),
        digest=digest_bytes(content),
        size_bytes=len(content),
        media_type="application/json",
    )


def test_runner_response_binds_authorization_and_work(tmp_path: Path) -> None:
    authorization = CookSetupAuthorization(
        prerequisite_curd_id="setup",
        allowed_paths=("src/limited",),
        allowed_commands=("just setup",),
    )
    authorization_ref = _ref(
        tmp_path, "authorization.json", canonical_bytes(authorization), "runner_authorization"
    )
    coverage = MoldCookCoverage(curd_ids=("curd-1",))
    response_ref = _ref(
        tmp_path,
        "response.json",
        canonical_bytes({
            "question": f"Approve setup {canonical_digest(authorization)} for sha256:{'a' * 64} and curd-1?",
            "response": "Approve",
            "execution_authorized": True,
            "spec_digest": "sha256:" + "a" * 64,
            "curd_ids": ["curd-1"],
            "authorization_digest": canonical_digest(authorization),
        }),
        "dialogue",
    )
    assert validate_runner_authority(
        authorization_ref, response_ref, tmp_path,
        spec_digest="sha256:" + "a" * 64, coverage=coverage,
    ) == authorization
    with pytest.raises(ValueError, match="different spec"):
        _ = validate_runner_authority(
            authorization_ref, response_ref, tmp_path,
            spec_digest="sha256:" + "b" * 64, coverage=coverage,
        )
    with pytest.raises(ValueError, match="different coverage"):
        _ = validate_runner_authority(
            authorization_ref, response_ref, tmp_path,
            spec_digest="sha256:" + "a" * 64,
            coverage=MoldCookCoverage(curd_ids=("curd-2",)),
        )


def test_runner_rejects_non_retained_response(tmp_path: Path) -> None:
    authorization = CookSetupAuthorization(
        prerequisite_curd_id="setup",
        allowed_paths=("src/limited",),
        allowed_commands=("just setup",),
    )
    authorization_ref = _ref(
        tmp_path, "authorization", canonical_bytes(authorization), "runner_authorization"
    )
    response = canonical_bytes({
        "question": f"Approve {canonical_digest(authorization)} for sha256:{'a' * 64} and curd-1?",
        "response": "Approve",
        "execution_authorized": True,
        "spec_digest": "sha256:" + "a" * 64,
        "curd_ids": ["curd-1"],
        "authorization_digest": canonical_digest(authorization),
    })
    response_path = tmp_path / "arbitrary.json"
    _ = response_path.write_bytes(response)
    response_ref = ArtifactRef(
        artifact_id="dialogue", role="dialogue", uri=response_path.as_uri(),
        digest=digest_bytes(response), size_bytes=len(response),
        media_type="application/json",
    )
    with pytest.raises(ValueError, match="retained host artifact"):
        _ = validate_runner_authority(
            authorization_ref, response_ref, tmp_path,
            spec_digest="sha256:" + "a" * 64,
            coverage=MoldCookCoverage(curd_ids=("curd-1",)),
        )


@pytest.mark.parametrize("response,authorized", [("Reject", True), ("Approve", False)])
def test_runner_rejects_non_approval(
    tmp_path: Path, response: str, authorized: bool
) -> None:
    authorization = CookSetupAuthorization(
        prerequisite_curd_id="setup",
        allowed_paths=("src/limited",),
        allowed_commands=("just setup",),
    )
    authorization_ref = _ref(
        tmp_path, "authorization", canonical_bytes(authorization), "runner_authorization"
    )
    spec_digest = "sha256:" + "a" * 64
    response_ref = _ref(
        tmp_path, "dialogue",
        canonical_bytes({
            "question": f"Approve {canonical_digest(authorization)} for {spec_digest} and curd-1?",
            "response": response,
            "execution_authorized": authorized,
            "spec_digest": spec_digest,
            "curd_ids": ["curd-1"],
            "authorization_digest": canonical_digest(authorization),
        }),
        "dialogue",
    )
    with pytest.raises(ValueError, match="not explicit approval|does not authorize"):
        _ = validate_runner_authority(
            authorization_ref, response_ref, tmp_path,
            spec_digest=spec_digest,
            coverage=MoldCookCoverage(curd_ids=("curd-1",)),
        )


def test_runner_rejects_widened_authorization(tmp_path: Path) -> None:
    authorized = CookSetupAuthorization(
        prerequisite_curd_id="setup",
        allowed_paths=("src/limited",),
        allowed_commands=("just setup",),
    )
    widened = CookSetupAuthorization(
        prerequisite_curd_id="setup",
        allowed_paths=("src/limited", "src/other"),
        allowed_commands=("just setup", "curl remote"),
    )
    widened_ref = _ref(
        tmp_path, "widened", canonical_bytes(widened), "runner_authorization"
    )
    spec_digest = "sha256:" + "a" * 64
    response_ref = _ref(
        tmp_path, "dialogue",
        canonical_bytes({
            "question": f"Approve {canonical_digest(authorized)} for {spec_digest} and curd-1?",
            "response": "Approve",
            "execution_authorized": True,
            "spec_digest": spec_digest,
            "curd_ids": ["curd-1"],
            "authorization_digest": canonical_digest(authorized),
        }),
        "dialogue",
    )
    with pytest.raises(ValueError, match="different authorization"):
        _ = validate_runner_authority(
            widened_ref, response_ref, tmp_path,
            spec_digest=spec_digest,
            coverage=MoldCookCoverage(curd_ids=("curd-1",)),
        )
