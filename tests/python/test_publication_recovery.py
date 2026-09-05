"""Unit coverage for crash-then-retry recovery in the publication gateway.

:func:`publish_canonical` writes payload and receipt files at digest-addressed
paths before revealing the pointer, so an interrupted publication leaves
intact leftovers a retry can reuse. A leftover that was tampered with between
the crash and the retry must be rejected as :class:`CorruptLeftoverError`,
not silently overwritten -- and the rejection must clean the tampered file so
a further retry starts clean.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from easy_cheese_schemas import (
    CanonicalArtifact,
    NormalizationReceipt,
    PublishedArtifact,
    canonical_digest,
    supported_version_for,
    validate_contract,
)

from easy_cheese.shared import publication

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"

_UNSIGNED_DOC: dict[str, object] = {
    "contract_version": {
        "schema_uri": CURD_PLAN_SCHEMA_URI,
        "major": "1",
        "minor": "0",
    },
    "plan_id": "curdplan-recovery-1",
    "revision": 1,
    "objective": "Ship the approved behavior",
    "curds": [
        {
            "curd_id": "runtime",
            "outcome": "Implement strict validation",
            "scope": {"paths": ["src/runtime.py"], "excluded_paths": []},
            "inputs": [],
            "outputs": ["Validated contract"],
            "dependencies": [],
            "criteria": [
                {
                    "criterion_id": "recovery-1",
                    "description": "Unknown fields reject",
                    "check": "uv run pytest tests/test_runtime.py",
                }
            ],
            "lineage": {"identity_action": "new", "source_curd_ids": []},
        }
    ],
    "context": None,
    "parent_plan_ref": None,
}

DOC: dict[str, object] = {**_UNSIGNED_DOC, "digest": canonical_digest(_UNSIGNED_DOC)}


def _prepare() -> tuple[CanonicalArtifact, NormalizationReceipt | None]:
    validated = validate_contract(
        DOC, CURD_PLAN_SCHEMA_URI, supported_version_for(CURD_PLAN_SCHEMA_URI)
    )
    return validated, None


def _publish_canonical(
    tmp_path: Path,
    *,
    operation_id: str,
    _before_reveal: object = None,
) -> PublishedArtifact:
    return publication.publish_canonical(
        request_digest=publication.request_digest(
            "raw",
            {"operation_id": operation_id},
            source_phase="mold",
            destination_phase="cook",
            payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        ),
        source_phase="mold",
        destination_phase="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        operation_id=operation_id,
        artifact_root=tmp_path,
        prepare=_prepare,
        _before_reveal=_before_reveal,  # pyright: ignore[reportArgumentType]
    )


def test_crash_then_retry_succeeds_with_intact_leftovers(tmp_path: Path) -> None:
    def _boom() -> None:
        raise RuntimeError("simulated crash before pointer reveal")

    with pytest.raises(RuntimeError, match="simulated crash"):
        _ = _publish_canonical(tmp_path, operation_id="op-crash", _before_reveal=_boom)

    pointer_path = tmp_path / "pointers" / "op-crash.json"
    assert not pointer_path.exists()
    payload_paths = list((tmp_path / "payloads").glob("*.json"))
    assert payload_paths
    leftover_bytes = payload_paths[0].read_bytes()

    artifact = _publish_canonical(tmp_path, operation_id="op-crash")
    assert pointer_path.exists()
    assert artifact.pointer.operation_id == "op-crash"
    assert payload_paths[0].read_bytes() == leftover_bytes


def test_crash_tamper_retry_raises_corrupt_leftover_and_cleans(tmp_path: Path) -> None:
    def _boom() -> None:
        raise RuntimeError("simulated crash before pointer reveal")

    with pytest.raises(RuntimeError, match="simulated crash"):
        _ = _publish_canonical(tmp_path, operation_id="op-tamper", _before_reveal=_boom)

    payload_paths = list((tmp_path / "payloads").glob("*.json"))
    assert payload_paths
    tampered_path = payload_paths[0]
    _ = tampered_path.write_bytes(b"not the original content")

    with pytest.raises(publication.CorruptLeftoverError):
        _ = _publish_canonical(tmp_path, operation_id="op-tamper")

    assert not tampered_path.exists()

    artifact = _publish_canonical(tmp_path, operation_id="op-tamper")
    assert (tmp_path / "pointers" / "op-tamper.json").exists()
    assert artifact.pointer.operation_id == "op-tamper"
    assert tampered_path.exists()


def test_corrupt_repair_keeps_a_concurrent_valid_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validated, _ = _prepare()
    digest = canonical_digest(validated.value)
    payload_path = tmp_path / "payloads" / f"{digest.replace(':', '-')}.json"
    payload_path.parent.mkdir()
    _ = payload_path.write_bytes(b"corrupt")
    original_read_bytes = Path.read_bytes
    replaced = False

    def _read_bytes(path: Path) -> bytes:
        nonlocal replaced
        content = original_read_bytes(path)
        if path == payload_path and not replaced:
            replaced = True
            publication._atomic_write(  # pyright: ignore[reportPrivateUsage]
                path, validated.canonical_bytes
            )
        return content

    monkeypatch.setattr(Path, "read_bytes", _read_bytes)
    with pytest.raises(publication.CorruptLeftoverError, match="changed during repair"):
        _ = publication._retain_content(  # pyright: ignore[reportPrivateUsage]
            payload_path.parent, digest, validated.canonical_bytes
        )
    assert payload_path.read_bytes() == validated.canonical_bytes


def test_corrupt_repair_restores_a_valid_post_read_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validated, _ = _prepare()
    digest = canonical_digest(validated.value)
    payload_path = tmp_path / "payloads" / f"{digest.replace(':', '-')}.json"
    payload_path.parent.mkdir()
    _ = payload_path.write_bytes(b"corrupt")
    original_replace = os.replace
    replaced = False

    def _replace(source: Path, destination: Path) -> None:
        nonlocal replaced
        if source == payload_path and not replaced:
            replaced = True
            publication._atomic_write(  # pyright: ignore[reportPrivateUsage]
                payload_path, validated.canonical_bytes
            )
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", _replace)
    with pytest.raises(publication.CorruptLeftoverError, match="retained"):
        _ = publication._retain_content(  # pyright: ignore[reportPrivateUsage]
            payload_path.parent, digest, validated.canonical_bytes
        )
    assert replaced
    assert payload_path.read_bytes() == validated.canonical_bytes
