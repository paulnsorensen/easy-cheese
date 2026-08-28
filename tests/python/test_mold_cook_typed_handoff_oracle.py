"""Protected outer tracers for the typed Mold to Cook handoff boundary."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from easy_cheese_schemas import CurdPlan, canonical_bytes, curd_plan_digest, load


ROOT = Path(__file__).resolve().parents[2]
MOLD = ROOT / "skills" / "mold" / "scripts" / "mold.pyz"
COOK = ROOT / "skills" / "cook" / "scripts" / "cook.pyz"

WITNESS_NORMALIZATION = (
    "Mold publish lacks bounded writer normalization and a bound "
    "NormalizationReceipt"
)
WITNESS_PUBLICATION = "Mold publish lacks pointer-last idempotent publication"
WITNESS_MIGRATION = (
    "Mold migration lacks exact-version and adapter-sunset enforcement"
)
WITNESS_ACCEPTANCE = "Cook lacks pointer-only validated handoff acceptance"


def _run(bundle: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(bundle), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _canonical_plan() -> dict[str, object]:
    plan: dict[str, object] = {
        "contract_version": {
            "schema_uri": "https://schemas.easy-cheese.dev/curd-plan",
            "major": "1",
            "minor": "0",
        },
        "plan_id": "plan-handoff-oracle",
        "revision": 1,
        "digest": (
            "sha256:"
            "a000000000000000000000000000000000000000000000000000000000000000"
        ),
        "objective": "Prove the typed handoff boundary",
        "curds": [
            {
                "curd_id": "curd-handoff",
                "outcome": "Accept the canonical handoff",
                "scope": {"paths": ["src/handoff.py"]},
                "inputs": [],
                "outputs": ["Accepted handoff"],
                "dependencies": [],
                "criteria": [
                    {
                        "criterion_id": "criterion-handoff",
                        "description": "The typed handoff is accepted",
                        "check": "pytest tests/test_handoff.py",
                    }
                ],
                "lineage": {"identity_action": "new"},
            }
        ],
    }
    loaded = load(plan, CurdPlan, strict=True)
    assert loaded.value is not None, loaded.problems
    plan["digest"] = curd_plan_digest(loaded.value)
    return plan


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _artifact_path(reference: object) -> Path:
    assert isinstance(reference, dict)
    uri = reference.get("uri")
    assert isinstance(uri, str) and uri.startswith("file://")
    return Path(uri.removeprefix("file://"))


def _write_strict_plan(path: Path) -> None:
    path.write_text(json.dumps(_canonical_plan()), encoding="utf-8")


def _write_deviant_plan(path: Path) -> None:
    strict = json.dumps(_canonical_plan(), indent=2)
    deviant = (
        "// agent writer comment\n"
        + strict.replace('"plan_id"', "plan_id", 1)
        .replace('"revision"', "'revision'", 1)
        .replace("\n}", ",\n}", 1)
    )
    path.write_text(deviant, encoding="utf-8")


def _publish(
    writer: Path, out_dir: Path, operation_id: str, witness: str
) -> dict[str, object]:
    result = _run(
        MOLD,
        "contract",
        "publish",
        "--writer-view",
        str(writer),
        "--destination",
        "cook",
        "--operation-id",
        operation_id,
        "--out-dir",
        str(out_dir),
    )
    assert result.returncode == 0, f"{witness}\n{result.stdout}\n{result.stderr}"
    return json.loads(result.stdout)


def _pointer_path(published: dict[str, object]) -> Path:
    value = published.get("pointer_path")
    assert isinstance(value, str) and value
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def test_ac_1_mold_normalizes_only_bounded_writer_syntax_and_binds_receipt(
    tmp_path: Path,
) -> None:
    deviant = tmp_path / "writer-view.jsonc"
    _write_deviant_plan(deviant)

    published = _publish(deviant, tmp_path / "published", "op-normalize", WITNESS_NORMALIZATION)

    receipt = published.get("normalization_receipt")
    pointer = published.get("pointer")
    assert isinstance(receipt, dict), WITNESS_NORMALIZATION
    assert isinstance(pointer, dict), WITNESS_NORMALIZATION
    payload = pointer.get("payload")
    assert isinstance(payload, dict), WITNESS_NORMALIZATION
    assert receipt.get("canonical_digest") == payload.get("digest"), WITNESS_NORMALIZATION
    assert receipt.get("source_digest") != receipt.get("canonical_digest"), WITNESS_NORMALIZATION
    assert receipt.get("actions"), WITNESS_NORMALIZATION

    ambiguous = tmp_path / "ambiguous.jsonc"
    ambiguous.write_text("{plan_id: 'a' plan_id: 'b'}", encoding="utf-8")
    rejected = _run(
        MOLD,
        "contract",
        "publish",
        "--writer-view",
        str(ambiguous),
        "--destination",
        "cook",
        "--operation-id",
        "op-ambiguous",
        "--out-dir",
        str(tmp_path / "ambiguous-out"),
    )
    assert rejected.returncode != 0, WITNESS_NORMALIZATION


def test_ac_2_mold_publishes_pointer_last_idempotently_and_revalidates(
    tmp_path: Path,
) -> None:
    writer = tmp_path / "writer-view.json"
    _write_strict_plan(writer)
    out_dir = tmp_path / "published"

    first = _publish(writer, out_dir, "op-idempotent", WITNESS_PUBLICATION)
    pointer_path = _pointer_path(first)
    assert pointer_path.is_file(), WITNESS_PUBLICATION

    second = _publish(writer, out_dir, "op-idempotent", WITNESS_PUBLICATION)
    assert second == first, WITNESS_PUBLICATION

    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    payload_uri = pointer["payload"]["uri"]
    payload_path = Path(payload_uri.removeprefix("file://"))
    payload_path.write_bytes(payload_path.read_bytes() + b"\ncorrupt")

    rejected = _run(
        MOLD,
        "contract",
        "publish",
        "--writer-view",
        str(writer),
        "--destination",
        "cook",
        "--operation-id",
        "op-idempotent",
        "--out-dir",
        str(out_dir),
    )
    assert rejected.returncode != 0, WITNESS_PUBLICATION


def test_ac_3_mold_migrates_only_exact_legacy_version_before_sunset(
    tmp_path: Path,
) -> None:
    legacy = {
        "schema_uri": "https://schemas.easy-cheese.dev/legacy-handoff",
        "version": {"major": "1", "minor": "0"},
        "source_phase": "mold",
        "destination_phase": "cook",
        "payload": _canonical_plan(),
    }
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")

    migrated = _run(
        MOLD,
        "contract",
        "migrate",
        "--legacy-handoff",
        str(legacy_path),
        "--operation-id",
        "op-migrate",
        "--out-dir",
        str(tmp_path / "migrated"),
    )
    assert migrated.returncode == 0, (
        f"{WITNESS_MIGRATION}\n{migrated.stdout}\n{migrated.stderr}"
    )
    published = json.loads(migrated.stdout)
    receipt = published.get("normalization_receipt")
    assert isinstance(receipt, dict), WITNESS_MIGRATION
    assert receipt.get("ingress_kind") == "legacy_artifact", WITNESS_MIGRATION
    assert receipt.get("source_version") == {"major": "1", "minor": "0"}, (
        WITNESS_MIGRATION
    )
    assert receipt.get("remove_after"), WITNESS_MIGRATION

    legacy["version"] = {"major": "1", "minor": "1"}
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    unsupported = _run(
        MOLD,
        "contract",
        "migrate",
        "--legacy-handoff",
        str(legacy_path),
        "--operation-id",
        "op-unsupported",
        "--out-dir",
        str(tmp_path / "unsupported"),
    )
    assert unsupported.returncode != 0, WITNESS_MIGRATION


def test_ac_4_cook_rejects_bare_payload_and_accepts_only_valid_pointer(
    tmp_path: Path,
) -> None:
    writer = tmp_path / "writer-view.json"
    _write_strict_plan(writer)
    published = _publish(
        writer, tmp_path / "published", "op-accept", WITNESS_ACCEPTANCE
    )
    pointer_path = _pointer_path(published)

    bare = _run(COOK, "contract", "accept", "--pointer", str(writer))
    assert bare.returncode != 0, WITNESS_ACCEPTANCE

    accepted = _run(COOK, "contract", "accept", "--pointer", str(pointer_path))
    assert accepted.returncode == 0, (
        f"{WITNESS_ACCEPTANCE}\n{accepted.stdout}\n{accepted.stderr}"
    )
    result = json.loads(accepted.stdout)
    canonical = result.get("canonical")
    assert isinstance(canonical, dict), WITNESS_ACCEPTANCE
    assert canonical.get("plan_id") == "plan-handoff-oracle", WITNESS_ACCEPTANCE

    deviant = tmp_path / "writer-view.jsonc"
    _write_deviant_plan(deviant)

    invalid = _publish(
        deviant,
        tmp_path / "invalid-plan",
        "op-invalid-plan",
        WITNESS_ACCEPTANCE,
    )
    invalid_pointer_path = _pointer_path(invalid)
    invalid_pointer = json.loads(invalid_pointer_path.read_text(encoding="utf-8"))
    payload_path = _artifact_path(invalid_pointer["payload"])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["digest"] = "sha256:" + "0" * 64
    payload_bytes = canonical_bytes(payload)
    payload_path.write_bytes(payload_bytes)
    payload_digest = _digest(payload_bytes)
    invalid_pointer["payload"]["digest"] = payload_digest

    receipt_path = _artifact_path(invalid_pointer["normalization_receipt"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["canonical_digest"] = payload_digest
    receipt_bytes = canonical_bytes(receipt)
    receipt_path.write_bytes(receipt_bytes)
    invalid_pointer["normalization_receipt"]["digest"] = _digest(receipt_bytes)
    invalid_pointer_path.write_bytes(canonical_bytes(invalid_pointer))

    rejected_plan = _run(
        COOK, "contract", "accept", "--pointer", str(invalid_pointer_path)
    )
    assert rejected_plan.returncode != 0, WITNESS_ACCEPTANCE

    unbound = _publish(
        deviant,
        tmp_path / "unbound-receipt",
        "op-unbound-receipt",
        WITNESS_ACCEPTANCE,
    )
    unbound_pointer_path = _pointer_path(unbound)
    unbound_pointer = json.loads(unbound_pointer_path.read_text(encoding="utf-8"))
    unbound_receipt_path = _artifact_path(unbound_pointer["normalization_receipt"])
    unbound_receipt = json.loads(unbound_receipt_path.read_text(encoding="utf-8"))
    unbound_receipt["source_digest"] = "sha256:" + "0" * 64
    unbound_receipt_bytes = canonical_bytes(unbound_receipt)
    unbound_receipt_path.write_bytes(unbound_receipt_bytes)
    unbound_pointer["normalization_receipt"]["digest"] = _digest(
        unbound_receipt_bytes
    )
    unbound_pointer_path.write_bytes(canonical_bytes(unbound_pointer))

    rejected_receipt = _run(
        COOK, "contract", "accept", "--pointer", str(unbound_pointer_path)
    )
    assert rejected_receipt.returncode != 0, WITNESS_ACCEPTANCE
