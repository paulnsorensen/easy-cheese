from __future__ import annotations

import json

import pytest

from easy_cheese_schemas.contracts import ContractVersion
import easy_cheese.shared.handoffs as handoffs

from easy_cheese_schemas.schema_runtime import normalize_agent_output
from tests.schemas.python.test_handoff_contracts import writer_and_invocation


def legacy_handoff(tmp_path) -> handoffs.LegacyHandoff:
    writer, invocation = writer_and_invocation(tmp_path)
    payload = json.loads(
        handoffs.canonical_bytes(normalize_agent_output(writer, invocation.as_mapping()).value)
    )
    return handoffs.LegacyHandoff(
        payload=payload,
        source_schema_uri=handoffs.LEGACY_SCHEMA_URI,
        source_version=handoffs.LEGACY_SOURCE_VERSION,
        invocation=invocation,
    )


def test_exact_version_only(tmp_path):
    legacy = legacy_handoff(tmp_path)
    migrated = handoffs.migrate(legacy, "legacy-op")
    assert migrated.normalization_receipt is not None
    with pytest.raises(ValueError, match="version"):
        handoffs.migrate(
            handoffs.LegacyHandoff(
                payload=legacy.payload,
                source_schema_uri=handoffs.LEGACY_SCHEMA_URI,
                source_version=ContractVersion(handoffs.LEGACY_SCHEMA_URI, "1", "1"),
                invocation=legacy.invocation,
            ),
            "legacy-op2",
        )


def test_adapter_sunset_blocks_migration(tmp_path, monkeypatch):
    monkeypatch.setattr(handoffs.easy_cheese_schemas, "__version__", "2.0.0")
    with pytest.raises(ValueError, match="sunset"):
        handoffs.migrate(legacy_handoff(tmp_path), "legacy-op")


def test_receipt_records_legacy_source(tmp_path):
    migrated = handoffs.migrate(legacy_handoff(tmp_path), "legacy-op")
    receipt = migrated.normalization_receipt
    assert receipt is not None
    assert receipt.source_schema_uri == handoffs.LEGACY_SCHEMA_URI
    assert receipt.source_version == handoffs.LEGACY_SOURCE_VERSION


def test_interrupted_publication_recovers_after_revalidation(tmp_path, monkeypatch):
    module = handoffs

    legacy = legacy_handoff(tmp_path)
    original = module._write_atomic_noclobber

    def fail_pointer(path, data, **kwargs):
        if path.parent.name == "pointers":
            raise OSError("interrupted")
        original(path, data, **kwargs)

    monkeypatch.setattr(module, "_write_atomic_noclobber", fail_pointer)
    with pytest.raises(OSError):
        handoffs.migrate(legacy, "legacy-op")
    monkeypatch.setattr(module, "_write_atomic_noclobber", original)
    recovered = handoffs.migrate(legacy, "legacy-op")
    assert recovered.pointer.operation_id == "legacy-op"


def test_no_legacy_execution_accepts_legacy_records(tmp_path):
    from easy_cheese.skills.cook.commands import contract_accept

    with pytest.raises(ValueError, match="HandoffPointer"):
        contract_accept(legacy_handoff(tmp_path), tmp_path)
