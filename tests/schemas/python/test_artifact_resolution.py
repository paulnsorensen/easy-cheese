from __future__ import annotations

import hashlib
import json
import os
from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, build_opener

import pytest
from attrs import asdict, evolve, fields

import easy_cheese_schemas.artifacts as artifacts_module
from easy_cheese_schemas.artifacts import (
    ArtifactResolutionError,
    resolve_artifact,
)
from easy_cheese_schemas.contracts import ArtifactRef


def artifact_ref(
    uri: str,
    content: bytes,
    *,
    media_type: str = "text/plain",
    schema_uri: str | None = None,
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="artifact-1",
        role="source",
        uri=uri,
        digest=f"sha256:{hashlib.sha256(content).hexdigest()}",
        size_bytes=len(content),
        media_type=media_type,
        schema_uri=schema_uri,
    )


def test_resolves_repository_artifact_to_durable_atomic_snapshot(tmp_path) -> None:
    content = b"trusted input"
    source = tmp_path / "artifacts" / "input.txt"
    source.parent.mkdir()
    source.write_bytes(content)
    artifact_directory = tmp_path / "resolved"

    resolved = resolve_artifact(
        artifact_ref("repo://artifacts/input.txt", content),
        repository_root=tmp_path,
        artifact_directory=artifact_directory,
    )

    resolved_path = Path(resolved.path)
    assert {field.name for field in fields(type(resolved))} == {
        "role",
        "path",
        "media_type",
    }
    assert set(asdict(resolved)) == {"role", "path", "media_type"}
    assert resolved.role == "source"
    assert resolved.media_type == "text/plain"
    assert isinstance(resolved.path, str)
    assert resolved_path.read_bytes() == content
    assert resolved_path.parent == artifact_directory.resolve()
    assert resolved_path.name == f"sha256-{hashlib.sha256(content).hexdigest()}"
    assert not hasattr(resolved, "artifact_id")
    assert not hasattr(resolved, "digest")
    assert not hasattr(resolved, "size_bytes")
    assert not hasattr(resolved, "schema_uri")
    assert not hasattr(resolved, "uri")

    replacement = source.with_name("replacement.txt")
    replacement.write_bytes(b"tampered replacement")
    os.replace(replacement, source)
    assert resolved_path.read_bytes() == content

    serialized = json.loads(json.dumps(asdict(resolved)))
    copied_path = Path(serialized["path"])
    assert copied_path.read_bytes() == content

    if os.name == "posix":
        assert os.stat(artifact_directory).st_mode & 0o777 == 0o700
        assert os.stat(resolved_path).st_mode & 0o777 == 0o600


def test_replaces_invalid_existing_snapshot(tmp_path) -> None:
    content = b"trusted input"
    source = tmp_path / "input.txt"
    source.write_bytes(content)
    artifact_directory = tmp_path / "resolved"
    artifact_directory.mkdir()
    destination = (
        artifact_directory / f"sha256-{hashlib.sha256(content).hexdigest()}"
    )
    destination.write_bytes(b"stale snapshot")

    resolved = resolve_artifact(
        artifact_ref(source.as_uri(), content),
        artifact_directory=artifact_directory,
    )

    assert Path(resolved.path) == destination
    assert destination.read_bytes() == content
    assert list(artifact_directory.glob("*.tmp")) == []



def test_replaces_symlinked_snapshot_without_touching_target(tmp_path) -> None:
    content = b"trusted input"
    source = tmp_path / "input.txt"
    source.write_bytes(content)
    artifact_directory = tmp_path / "resolved"
    artifact_directory.mkdir()
    destination = (
        artifact_directory / f"sha256-{hashlib.sha256(content).hexdigest()}"
    )
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"do not overwrite")
    destination.symlink_to(outside)

    resolved = resolve_artifact(
        artifact_ref(source.as_uri(), content),
        artifact_directory=artifact_directory,
    )

    assert Path(resolved.path) == destination
    assert not destination.is_symlink()
    assert destination.read_bytes() == content
    assert outside.read_bytes() == b"do not overwrite"

def test_resolves_local_file_artifact(tmp_path) -> None:
    content = b"trusted input"
    source = tmp_path / "input.txt"
    source.write_bytes(content)
    artifact_directory = tmp_path / "resolved"

    resolved = resolve_artifact(
        artifact_ref(source.as_uri(), content),
        artifact_directory=artifact_directory,
    )

    resolved_path = Path(resolved.path)
    assert resolved.role == "source"
    assert resolved.media_type == "text/plain"
    assert resolved_path.read_bytes() == content
    assert resolved_path != source.resolve()


def test_requires_artifact_directory_lifecycle_owner(tmp_path) -> None:
    content = b"trusted input"
    source = tmp_path / "input.txt"
    source.write_bytes(content)
    with pytest.raises(TypeError):
        resolve_artifact(artifact_ref(source.as_uri(), content))


@pytest.mark.parametrize(
    ("uri", "message"),
    [
        ("https://[invalid/input.txt", "artifact URI is invalid"),
        ("ftp://example.test/input.txt", "unsupported artifact URI scheme"),
        ("repo://../outside.txt", "escapes repository root"),
        ("repo://artifacts/input.txt?download=1", "query or fragment"),
        (
            "https://user:secret@example.test/input.txt",
            "host without credentials",
        ),
        ("file://remotehost/tmp/input.txt", "local file URI"),
    ],
)
def test_rejects_uri_outside_policy(tmp_path, uri: str, message: str) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (tmp_path / "outside.txt").write_bytes(b"trusted input")

    with pytest.raises(ArtifactResolutionError, match=message):
        resolve_artifact(
            artifact_ref(uri, b"trusted input"),
            repository_root=repository,
            artifact_directory=tmp_path / "resolved",
        )


def test_rejects_repository_symlink_escape(tmp_path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"trusted input")
    (repository / "input.txt").symlink_to(outside)

    with pytest.raises(ArtifactResolutionError, match="escapes repository root"):
        resolve_artifact(
            artifact_ref("repo:input.txt", b"trusted input"),
            repository_root=repository,
            artifact_directory=tmp_path / "resolved",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("digest", f"sha256:{'0' * 64}", "digest mismatch"),
        ("size_bytes", 999, "size mismatch"),
        ("media_type", "application/json", "media type mismatch"),
    ],
)
def test_rejects_integrity_mismatch_before_exposure(
    tmp_path, field: str, value: object, message: str
) -> None:
    source = tmp_path / "input.txt"
    source.write_bytes(b"trusted input")
    calls = []
    reference = evolve(
        artifact_ref(source.as_uri(), b"trusted input"),
        schema_uri="urn:example:input",
        **{field: value},
    )

    def schema_validator(_raw, _schema_uri):
        calls.append((_raw, _schema_uri))

        resolve_artifact(
            reference,
            artifact_directory=tmp_path / "resolved",
            schema_validator=schema_validator,
        )

    assert calls == []


class HttpsResponse(BytesIO):
    def __init__(
        self, content: bytes, url: str, media_type: str | None
    ) -> None:
        super().__init__(content)
        self._url = url
        self.headers = Message()
        if media_type is not None:
            self.headers["Content-Type"] = media_type

    def geturl(self) -> str:
        return self._url


class TrackingHTTPError(HTTPError):
    def __init__(self, url: str, code: int, headers: Message) -> None:
        super().__init__(url, code, "error", headers, BytesIO())
        self.was_closed = False

    def close(self) -> None:
        self.was_closed = True
        super().close()


def test_closes_http_error_before_raising(tmp_path, monkeypatch) -> None:
    content = b"trusted input"
    uri = "https://example.test/input.txt"
    error = TrackingHTTPError(uri, 500, Message())

    def raise_error(_request, *, timeout):
        raise error

    monkeypatch.setattr("easy_cheese_schemas.artifacts.urlopen", raise_error)

    with pytest.raises(ArtifactResolutionError, match="could not be fetched"):
        resolve_artifact(artifact_ref(uri, content), artifact_directory=tmp_path)

    assert error.was_closed


def test_closes_http_error_before_following_redirect(tmp_path, monkeypatch) -> None:
    content = b"trusted input"
    uri = "https://example.test/input.txt"
    redirected_uri = "https://example.test/next.txt"
    headers = Message()
    headers["Location"] = "/next.txt"
    error = TrackingHTTPError(uri, 302, headers)
    calls = []

    def open_https(request, *, timeout):
        calls.append((request.full_url, timeout))
        if len(calls) == 1:
            raise error
        return HttpsResponse(content, redirected_uri, "text/plain")

    monkeypatch.setattr("easy_cheese_schemas.artifacts.urlopen", open_https)

    resolved = resolve_artifact(
        artifact_ref(uri, content),
        artifact_directory=tmp_path / "resolved",
    )

    assert error.was_closed
    assert calls == [(uri, 30), (redirected_uri, 30)]
    assert Path(resolved.path).read_bytes() == content


def test_resolves_https_artifact_to_durable_snapshot(tmp_path, monkeypatch) -> None:
    content = b"trusted input"
    uri = "https://example.test/input.txt"
    calls = []

    def open_https(request, *, timeout):
        calls.append((request.full_url, timeout))
        return HttpsResponse(content, uri, "text/plain")

    monkeypatch.setattr("easy_cheese_schemas.artifacts.urlopen", open_https)

    resolved = resolve_artifact(
        artifact_ref(uri, content),
        artifact_directory=tmp_path / "resolved",
    )

    resolved_path = Path(resolved.path)
    assert resolved.role == "source"
    assert resolved.media_type == "text/plain"
    assert resolved_path.read_bytes() == content
    assert calls == [(uri, 30)]


def test_rejects_https_response_without_media_type(
    tmp_path, monkeypatch
) -> None:
    content = b"trusted input"
    uri = "https://example.test/input.txt"
    monkeypatch.setattr(
        "easy_cheese_schemas.artifacts.urlopen",
        lambda _request, *, timeout: HttpsResponse(content, uri, None),
    )
    artifact_directory = tmp_path / "resolved"

    with pytest.raises(ArtifactResolutionError, match="declare a Content-Type"):
        resolve_artifact(
            artifact_ref(uri, content),
            artifact_directory=artifact_directory,
        )

    assert not artifact_directory.exists()


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "http://example.test/input.txt",
        "https://example.test/input.txt?download=1",
        "https:///input.txt",
    ],
)
def test_rejects_https_redirect_outside_policy(
    tmp_path, monkeypatch, redirect_uri: str
) -> None:
    content = b"trusted input"
    uri = "https://example.test/input.txt"
    monkeypatch.setattr(
        "easy_cheese_schemas.artifacts.urlopen",
        lambda _request, *, timeout: HttpsResponse(
            content, redirect_uri, "text/plain"
        ),
    )
    artifact_directory = tmp_path / "resolved"

    with pytest.raises(ArtifactResolutionError, match="redirected outside URI policy"):
        resolve_artifact(
            artifact_ref(uri, content),
            artifact_directory=artifact_directory,
        )


    assert not artifact_directory.exists()

class RedirectResponse(HttpsResponse):
    def __init__(self, url: str, redirect_uri: str) -> None:
        super().__init__(b"", url, "text/plain")
        self.status = 302
        self.code = 302
        self.msg = "Found"
        self.headers["Location"] = redirect_uri

    def info(self) -> Message:
        return self.headers

    def read(self, *_args, **_kwargs):
        raise AssertionError("redirect response body must not be read")


def test_rejects_forbidden_redirect_before_opening_or_reading(
    tmp_path, monkeypatch
) -> None:
    content = b"trusted input"
    uri = "https://example.test/input.txt"
    forbidden_uri = "http://attacker.test/input.txt"
    opened = []

    def open_https(request, *, timeout):
        opened.append(request.full_url)
        if len(opened) > 1:
            raise AssertionError("forbidden redirect must not be contacted")
        return RedirectResponse(uri, forbidden_uri)

    monkeypatch.setattr("easy_cheese_schemas.artifacts.urlopen", open_https)

    with pytest.raises(ArtifactResolutionError, match="redirected outside URI policy"):
        resolve_artifact(artifact_ref(uri, content), artifact_directory=tmp_path / "resolved")

    assert opened == [uri]


def test_rejects_forbidden_redirect_with_no_redirect_opener(
    tmp_path, monkeypatch
) -> None:
    content = b"trusted input"
    uri = "https://example.test/input.txt"
    forbidden_uri = "https://attacker.test/input.txt?download=1"
    opened = []

    class FixtureHTTPSHandler(HTTPSHandler):
        def https_open(self, request):
            opened.append(request.full_url)
            if len(opened) > 1:
                raise AssertionError("forbidden redirect must not be contacted")
            return RedirectResponse(request.full_url, forbidden_uri)

    opener = build_opener(
        artifacts_module._NoRedirectHandler(),
        FixtureHTTPSHandler(),
    )
    monkeypatch.setattr(artifacts_module, "urlopen", opener.open)

    with pytest.raises(ArtifactResolutionError, match="redirected outside URI policy"):
        resolve_artifact(
            artifact_ref(uri, content),
            artifact_directory=tmp_path / "resolved",
        )

    assert opened == [uri]


def test_validates_declared_schema_before_exposure(tmp_path) -> None:
    document = {"contract_version": {"schema_uri": "urn:example:input"}, "value": 1}
    content = json.dumps(document).encode()
    source = tmp_path / "input.json"
    source.write_bytes(content)
    calls = []

    def validate_schema(raw, schema_uri):
        calls.append((raw, schema_uri))

    artifact_directory = tmp_path / "resolved"
    resolved = resolve_artifact(
        artifact_ref(
            source.as_uri(),
            content,
            media_type="application/json",
            schema_uri="urn:example:input",
        ),
        artifact_directory=artifact_directory,
        schema_validator=validate_schema,
    )

    resolved_path = Path(resolved.path)
    assert resolved_path.read_bytes() == content
    assert resolved_path != source.resolve()
    assert calls == [(content, "urn:example:input")]


def test_rejects_schema_mismatch_before_exposure(tmp_path) -> None:
    content = b'{"value": 1}'
    source = tmp_path / "input.json"
    source.write_bytes(content)

    def reject_schema(_raw, _schema_uri):
        raise ValueError("required property is missing")

    with pytest.raises(ArtifactResolutionError, match="artifact schema mismatch"):
        resolve_artifact(
            artifact_ref(
                source.as_uri(),
                content,
                media_type="application/json",
                schema_uri="urn:example:input",
            ),
            artifact_directory=tmp_path / "resolved",
            schema_validator=reject_schema,
        )


def test_rejects_unknown_schema_uri_from_default_registry(tmp_path) -> None:
    content = b'{"value": 1}'
    source = tmp_path / "input.json"
    source.write_bytes(content)
    schema_uri = "https://schemas.easy-cheese.dev/not-registered"
    artifact_directory = tmp_path / "resolved"

    with pytest.raises(ArtifactResolutionError, match="artifact schema mismatch"):
        resolve_artifact(
            artifact_ref(
                source.as_uri(),
                content,
                media_type="application/json",
                schema_uri=schema_uri,
            ),
            artifact_directory=artifact_directory,
        )

    assert not artifact_directory.exists()


def test_rejects_invalid_json_before_schema_validator(tmp_path) -> None:
    content = b"not JSON"
    source = tmp_path / "input.json"
    source.write_bytes(content)

    def unexpected_validation(_raw, _schema_uri):
        raise AssertionError("validator must not receive invalid JSON")

    with pytest.raises(ArtifactResolutionError, match="not valid JSON"):
        resolve_artifact(
            artifact_ref(
                source.as_uri(),
                content,
                media_type="application/json",
                schema_uri="urn:example:input",
            ),
            artifact_directory=tmp_path / "resolved",
            schema_validator=unexpected_validation,
        )


def test_https_integrity_failure_is_not_materialized(tmp_path, monkeypatch) -> None:
    content = b"untrusted input"
    uri = "https://example.test/input.txt"
    monkeypatch.setattr(
        "easy_cheese_schemas.artifacts.urlopen",
        lambda _request, *, timeout: HttpsResponse(content, uri, "text/plain"),
    )
    reference = evolve(
        artifact_ref(uri, content),
        digest=f"sha256:{'0' * 64}",
    )
    artifact_directory = tmp_path / "resolved"

    with pytest.raises(ArtifactResolutionError, match="digest mismatch"):
        resolve_artifact(reference, artifact_directory=artifact_directory)

    assert not artifact_directory.exists()

def test_resolves_registered_versioned_json_with_default_schema_validation(
    tmp_path,
) -> None:
    schema_uri = "https://schemas.easy-cheese.dev/phase-contract"
    document = {
        "contract_version": {
            "schema_uri": schema_uri,
            "major": "1",
            "minor": "0",
        },
        "source": "cook",
        "input_schema_uris": ["https://schemas.easy-cheese.dev/curd-plan"],
        "outputs": [
            {
                "destination": "cure",
                "payload_schema_uri": "https://schemas.easy-cheese.dev/curd-result",
            }
        ],
    }
    content = json.dumps(document).encode()
    source = tmp_path / "input.json"
    source.write_bytes(content)
    artifact_directory = tmp_path / "resolved"

    resolved = resolve_artifact(
        artifact_ref(
            source.as_uri(),
            content,
            media_type="application/json",
            schema_uri=schema_uri,
        ),
        artifact_directory=artifact_directory,
    )

    resolved_path = Path(resolved.path)
    assert resolved_path.read_bytes() == content


def test_rejects_artifact_larger_than_ceiling_before_local_open(tmp_path, monkeypatch):
    content = b"small"
    source = tmp_path / "input.txt"
    source.write_bytes(content)
    artifact = object.__new__(ArtifactRef)
    object.__setattr__(artifact, "artifact_id", "artifact-1")
    object.__setattr__(artifact, "role", "source")
    object.__setattr__(artifact, "uri", source.as_uri())
    object.__setattr__(artifact, "digest", f"sha256:{hashlib.sha256(content).hexdigest()}")
    object.__setattr__(
        artifact,
        "size_bytes",
        artifacts_module.MAX_ARTIFACT_BYTES + 1,
    )
    object.__setattr__(artifact, "media_type", "text/plain")
    object.__setattr__(artifact, "schema_uri", None)
    monkeypatch.setattr(
        artifacts_module.os,
        "open",
        lambda *_args, **_kwargs: pytest.fail("oversized artifact must not open"),
    )

    with pytest.raises(ArtifactResolutionError, match="maximum size"):
        resolve_artifact(artifact, artifact_directory=tmp_path / "resolved")


def test_rejects_duplicate_json_keys_before_registered_validation(tmp_path):
    content = b'{"value": 1, "value": 2}'
    source = tmp_path / "input.json"
    source.write_bytes(content)
    called = []

    def validator(raw, _schema_uri):
        called.append(raw)

    with pytest.raises(ArtifactResolutionError, match="duplicate key"):
        resolve_artifact(
            artifact_ref(
                source.as_uri(),
                content,
                media_type="application/json",
                schema_uri="urn:example:input",
            ),
            artifact_directory=tmp_path / "resolved",
            schema_validator=validator,
        )

    assert called == []


def test_permission_failure_is_not_silenced_for_existing_snapshot(
    tmp_path, monkeypatch
):
    content = b"trusted input"
    source = tmp_path / "input.txt"
    source.write_bytes(content)
    artifact_directory = tmp_path / "resolved"
    artifact_directory.mkdir()
    destination = artifact_directory / f"sha256-{hashlib.sha256(content).hexdigest()}"
    destination.write_bytes(content)

    def fail_chmod(*_args, **_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(artifacts_module.os, "chmod", fail_chmod)
    with pytest.raises(ArtifactResolutionError, match="private permissions"):
        resolve_artifact(
            artifact_ref(source.as_uri(), content),
            artifact_directory=artifact_directory,
        )


def test_repository_ancestor_symlink_is_rejected(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "input.txt").write_bytes(b"trusted input")
    (repository / "nested").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ArtifactResolutionError, match="escapes repository root"):
        resolve_artifact(
            artifact_ref("repo:nested/input.txt", b"trusted input"),
            repository_root=repository,
            artifact_directory=tmp_path / "resolved",
        )


def test_local_file_final_symlink_is_rejected(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"trusted input")
    source = tmp_path / "input.txt"
    source.symlink_to(outside)

    with pytest.raises(ArtifactResolutionError, match="not readable"):
        resolve_artifact(
            artifact_ref(source.as_uri(), b"trusted input"),
            artifact_directory=tmp_path / "resolved",
        )
