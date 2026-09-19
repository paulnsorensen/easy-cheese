"""Media-type agreement and non-oracular integrity messages.

The `repo:` and `file:` ingresses must admit exactly the same artifacts for
one `ArtifactRef`, and an integrity failure must not echo the observed digest
or size: the message is persisted into caller-visible artifacts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import attrs
import pytest

from easy_cheese.shared.artifacts import ArtifactResolutionError, resolve_artifact
from easy_cheese_schemas.contracts import ArtifactRef


def artifact_ref(
    uri: str, content: bytes, *, media_type: str = "text/plain"
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="artifact-1",
        role="source",
        uri=uri,
        digest=f"sha256:{hashlib.sha256(content).hexdigest()}",
        size_bytes=len(content),
        media_type=media_type,
    )


def test_extensionless_retained_artifact_resolves_through_both_ingresses(
    tmp_path: Path,
) -> None:
    content = b"retained workflow bytes\n"
    repository = tmp_path / "repository"
    repository.mkdir()
    # Every retained artifact is named `sha256-<hex>` with no extension, so
    # `mimetypes.guess_type` cannot type it through either ingress.
    name = f"sha256-{hashlib.sha256(content).hexdigest()}"
    source = repository / name
    _ = source.write_bytes(content)

    through_repo = resolve_artifact(
        artifact_ref(f"repo://{name}", content, media_type="text/markdown"),
        repository_root=repository,
        artifact_directory=tmp_path / "repo-resolved",
    )
    through_file = resolve_artifact(
        artifact_ref(source.as_uri(), content, media_type="text/markdown"),
        repository_root=repository,
        artifact_directory=tmp_path / "file-resolved",
    )

    assert through_repo.media_type == "text/markdown"
    assert through_file.media_type == through_repo.media_type
    assert Path(through_repo.path).read_bytes() == content
    assert Path(through_file.path).read_bytes() == content


@pytest.mark.parametrize("scheme", ["repo", "file"])
def test_typed_extension_still_rejects_a_mismatched_declaration(
    tmp_path: Path, scheme: str
) -> None:
    content = b"trusted input"
    repository = tmp_path / "repository"
    repository.mkdir()
    source = repository / "input.txt"
    _ = source.write_bytes(content)
    uri = "repo://input.txt" if scheme == "repo" else source.as_uri()

    # A typed extension gives an independently derived type, so the declaration
    # is still checked against it on both ingresses.
    with pytest.raises(ArtifactResolutionError, match="media type mismatch"):
        _ = resolve_artifact(
            artifact_ref(uri, content, media_type="application/json"),
            repository_root=repository,
            artifact_directory=tmp_path / "resolved",
        )


def test_digest_mismatch_does_not_echo_the_observed_digest(tmp_path: Path) -> None:
    content = b"trusted input"
    source = tmp_path / "input.txt"
    _ = source.write_bytes(content)
    observed = hashlib.sha256(content).hexdigest()
    reference = attrs.evolve(
        artifact_ref(source.as_uri(), content), digest=f"sha256:{'0' * 64}"
    )

    with pytest.raises(ArtifactResolutionError) as raised:
        _ = resolve_artifact(reference, artifact_directory=tmp_path / "resolved")

    message = str(raised.value)
    assert "digest mismatch" in message
    assert observed not in message


def test_size_mismatch_does_not_echo_the_observed_size(tmp_path: Path) -> None:
    content = b"trusted input"
    source = tmp_path / "input.txt"
    _ = source.write_bytes(content)
    reference = attrs.evolve(artifact_ref(source.as_uri(), content), size_bytes=999)

    with pytest.raises(ArtifactResolutionError) as raised:
        _ = resolve_artifact(reference, artifact_directory=tmp_path / "resolved")

    message = str(raised.value)
    assert "size mismatch" in message
    assert f"got {len(content)}" not in message
    assert str(len(content)) not in message


@pytest.mark.parametrize("scheme", ["repo", "file"])
def test_undeterminable_type_outside_the_retained_name_fails_closed(
    tmp_path: Path, scheme: str
) -> None:
    content = b"untyped bytes\n"
    repository = tmp_path / "repository"
    repository.mkdir()
    source = repository / "artifact"
    _ = source.write_bytes(content)
    uri = "repo://artifact" if scheme == "repo" else source.as_uri()

    # Only the retained `sha256-<hex>` name is extensionless by design. Any
    # other untypeable path is refused on both ingresses, so a declaration
    # is never accepted without an independently derived type.
    with pytest.raises(
        ArtifactResolutionError, match="media type cannot be determined"
    ):
        _ = resolve_artifact(
            artifact_ref(uri, content),
            repository_root=repository,
            artifact_directory=tmp_path / "resolved",
        )
