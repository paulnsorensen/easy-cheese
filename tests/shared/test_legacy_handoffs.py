from __future__ import annotations

import json

import pytest

from easy_cheese_schemas.contracts import ContractVersion
from easy_cheese.shared.handoffs import (
    LEGACY_SCHEMA_URI,
    LEGACY_SOURCE_VERSION,
    LegacyHandoff,
    canonical_bytes,
    migrate,
)
from easy_cheese_schemas.schema_runtime import normalize_agent_output
from tests.schemas.python.test_handoff_contracts import writer_and_invocation


def legacy_handoff(tmp_path) -> LegacyHandoff:
    writer, invocation = writer_and_invocation(tmp_path)
    payload = json.loads(
        canonical_bytes(normalize_agent_output(writer, invocation.as_mapping()).value)
    )
    return LegacyHandoff(
        payload=payload,
        source_schema_uri=LEGACY_SCHEMA_URI,
        source_version=LEGACY_SOURCE_VERSION,
        invocation=invocation,
    )


def test_exact_version_only(tmp_path):
    legacy = legacy_handoff(tmp_path)
    migrated = migrate(legacy, "legacy-op")
    assert migrated.normalization_receipt is not None
    with pytest.raises(ValueError, match="version"):
        migrate(
            LegacyHandoff(
                payload=legacy.payload,
                source_schema_uri=LEGACY_SCHEMA_URI,
                source_version=ContractVersion(LEGACY_SCHEMA_URI, "1", "1"),
                invocation=legacy.invocation,
            ),
            "legacy-op2",
        )


def test_adapter_sunset_blocks_migration(tmp_path, monkeypatch):
    import easy_cheese.shared.handoffs as module

    monkeypatch.setattr(module, "PACKAGE_VERSION", (2, 0, 0))
    with pytest.raises(ValueError, match="sunset"):
        migrate(legacy_handoff(tmp_path), "legacy-op")


def test_receipt_records_legacy_source(tmp_path):
    migrated = migrate(legacy_handoff(tmp_path), "legacy-op")
    receipt = migrated.normalization_receipt
    assert receipt is not None
    assert receipt.source_schema_uri == LEGACY_SCHEMA_URI
    assert receipt.source_version == LEGACY_SOURCE_VERSION


def test_interrupted_publication_recovers_after_revalidation(tmp_path, monkeypatch):
    import easy_cheese.shared.handoffs as module

    legacy = legacy_handoff(tmp_path)
    original = module._write_atomic

    def fail_pointer(path, data):
        if path.parent.name == "pointers":
            raise OSError("interrupted")
        original(path, data)

    monkeypatch.setattr(module, "_write_atomic", fail_pointer)
    with pytest.raises(OSError):
        migrate(legacy, "legacy-op")
    monkeypatch.setattr(module, "_write_atomic", original)
    recovered = migrate(legacy, "legacy-op")
    assert recovered.pointer.operation_id == "legacy-op"


def test_no_legacy_execution_accepts_legacy_records(tmp_path):
    from easy_cheese.skills.cook.commands import contract_accept

    with pytest.raises(ValueError, match="HandoffPointer"):
        contract_accept(legacy_handoff(tmp_path))
