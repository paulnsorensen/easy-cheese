"""In-process coverage for the shared legacy migration boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import ContractValidationError, PublishedArtifact

from easy_cheese.shared import publication
from easy_cheese.shared.migrate import UnsupportedLegacySourceError, migrate

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"

LEGACY_DOC: dict[str, object] = {
    "plan_id": "curdplan-legacy-migrate-1",
    "revision": 1,
    "goal": "Ship the approved behavior",
    "curds": [
        {
            "key": "runtime",
            "goal": "Implement strict validation",
            "paths": ["src/runtime.py"],
            "outputs": ["Validated contract"],
            "criteria": [
                {
                    "description": "Unknown fields reject",
                    "check": "uv run pytest tests/test_runtime.py",
                }
            ],
        }
    ],
}


def _migrate(
    payload: dict[str, object], tmp_path: Path, operation_id: str
) -> PublishedArtifact:
    return migrate(
        payload,
        source_schema_uri=CURD_PLAN_SCHEMA_URI,
        source_major="0",
        source_minor="9",
        source_phase="mold",
        destination_phase="cook",
        operation_id=operation_id,
        artifact_root=tmp_path,
        reference_date=date(2026, 1, 1),
    )


def test_migrate_publishes_matching_legacy_source_identity(tmp_path: Path) -> None:
    artifact = _migrate(dict(LEGACY_DOC), tmp_path, "op-legacy-ok")
    receipt = artifact.normalization_receipt
    assert receipt is not None
    assert artifact.pointer.source_phase == "mold"
    assert artifact.pointer.destination_phase == "cook"


@pytest.mark.parametrize("missing", ["curds", "plan_id", "goal", "revision"])
def test_migrate_reports_malformed_legacy_payload(
    tmp_path: Path, missing: str
) -> None:
    """A legacy document that the adapter cannot read must fail as a named
    contract error, never as a raw converter exception."""
    payload = {key: value for key, value in LEGACY_DOC.items() if key != missing}

    with pytest.raises(UnsupportedLegacySourceError, match="does not convert"):
        _ = _migrate(payload, tmp_path, f"op-legacy-{missing}")


def test_accept_rejects_two_legacy_source_identities(tmp_path: Path) -> None:
    """A legacy receipt names one source. A receipt whose two source fields
    disagree must fail acceptance."""
    artifact = _migrate(dict(LEGACY_DOC), tmp_path, "op-legacy-identity")
    receipt_ref = artifact.pointer.normalization_receipt
    assert receipt_ref is not None
    receipt_path = Path(receipt_ref.uri.removeprefix("file://"))
    receipt = cast("dict[str, object]", json.loads(receipt_path.read_text()))
    receipt["source_schema_uri"] = "https://schemas.easy-cheese.dev/other"
    tampered = json.dumps(receipt).encode("utf-8")
    _ = receipt_path.write_bytes(tampered)

    pointer_path = tmp_path / "pointers" / "op-legacy-identity.json"
    pointer = cast("dict[str, object]", json.loads(pointer_path.read_text()))
    ref = cast("dict[str, object]", pointer["normalization_receipt"])
    ref["digest"] = f"sha256:{hashlib.sha256(tampered).hexdigest()}"
    ref["size_bytes"] = len(tampered)
    _ = pointer_path.write_text(json.dumps(pointer))

    with pytest.raises(
        ContractValidationError, match="two legacy source identities"
    ):
        _ = publication.accept(
            pointer_path,
            destination_phase="cook",
            payload_schema_uri=CURD_PLAN_SCHEMA_URI,
            artifact_root=tmp_path,
        )
