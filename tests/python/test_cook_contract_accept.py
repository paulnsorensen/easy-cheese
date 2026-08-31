"""End-to-end coverage for cook.pyz's `accept` contract command.

Each test publishes a real HandoffPointer through mold.pyz's `publish`, then
feeds that pointer (optionally tampered) into an isolated cook.pyz `accept`
subprocess, proving Cook executes only from a validated canonical pointer.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("pip") is None
    or (shutil.which("shiv") is None and importlib.util.find_spec("shiv") is None),
    reason="bundle integration requires requirements-build.txt",
)

DOC = {
    "kind": "curd_plan",
    "payload": {
        "objective": "Ship the approved behavior",
        "curds": [
            {
                "key": "runtime",
                "outcome": "Implement strict validation",
                "scope": {"paths": ["src/runtime.py"]},
                "outputs": ["Validated contract"],
                "criteria": [
                    {
                        "description": "Unknown fields reject",
                        "check": "uv run pytest tests/test_runtime.py",
                    }
                ],
            }
        ],
    },
}

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"

INVOCATION = {
    "plan_id": "curdplan-cook-accept-1",
    "contract_version": {
        "schema_uri": CURD_PLAN_SCHEMA_URI,
        "major": "1",
        "minor": "0",
    },
}


def _run(pyz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # Run from the bundle's own dir with PYTHONPATH stripped, so the only way
    # an import can resolve is from inside the .pyz itself.
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        cwd=str(pyz.parent),
        capture_output=True,
        text=True,
        env=env,
    )


def _publish(
    tmp_path: Path,
    operation_id: str,
    *,
    doc: object = DOC,
    raw_text: str | None = None,
) -> tuple[Path, dict[str, object]]:
    mold_pyz = build_pyz.cached_bundle("mold")
    document = tmp_path / f"{operation_id}-document.json"
    _ = document.write_text(
        raw_text if raw_text is not None else json.dumps(doc), encoding="utf-8"
    )
    invocation = tmp_path / f"{operation_id}-invocation.json"
    _ = invocation.write_text(json.dumps(INVOCATION), encoding="utf-8")
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "publish",
        str(document),
        "--invocation",
        str(invocation),
        "--operation-id",
        operation_id,
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pointer_path = artifact_root / "pointers" / f"{operation_id}.json"
    pointer = cast(dict[str, object], json.loads(pointer_path.read_text(encoding="utf-8")))
    return pointer_path, pointer


def _accept(pointer_path: Path) -> subprocess.CompletedProcess[str]:
    cook_pyz = build_pyz.cached_bundle("cook")
    return _run(cook_pyz, "accept", str(pointer_path))


def test_cook_pyz_accepts_a_real_mold_pointer(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-happy")
    result = _accept(pointer_path)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = cast(dict[str, object], json.loads(result.stdout))
    value = cast(dict[str, object], wrapper["value"])
    assert value["plan_id"] == INVOCATION["plan_id"]
    assert pointer["destination_phase"] == "cook"


def test_cook_pyz_accepts_a_receipt_bearing_pointer(tmp_path: Path) -> None:
    raw_text = json.dumps(DOC)[:-1] + ",}"
    pointer_path, pointer = _publish(tmp_path, "op-receipt", raw_text=raw_text)
    assert pointer["normalization_receipt"] is not None
    result = _accept(pointer_path)
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = cast(dict[str, object], json.loads(result.stdout))
    assert wrapper["normalization_receipt"] is not None


def test_cook_pyz_rejects_tampered_payload(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-tampered-payload")
    payload = cast(dict[str, object], pointer["payload"])
    payload_path = Path(cast(str, payload["uri"]).removeprefix("file://"))
    body = cast(dict[str, object], json.loads(payload_path.read_text(encoding="utf-8")))
    body["objective"] = "Tampered after publication"
    _ = payload_path.write_text(json.dumps(body), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "digest mismatch" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_wrong_route(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-wrong-route")
    pointer["source_phase"] = "press"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "press -> cook is not declared" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_missing_receipt_file(tmp_path: Path) -> None:
    raw_text = json.dumps(DOC)[:-1] + ",}"
    pointer_path, pointer = _publish(tmp_path, "op-missing-receipt", raw_text=raw_text)
    receipt = cast(dict[str, object], pointer["normalization_receipt"])
    receipt_path = Path(cast(str, receipt["uri"]).removeprefix("file://"))
    receipt_path.unlink()
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "is missing at" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_receipt_digest_mismatch(tmp_path: Path) -> None:
    raw_text = json.dumps(DOC)[:-1] + ",}"
    pointer_path, pointer = _publish(tmp_path, "op-receipt-mismatch", raw_text=raw_text)
    receipt = cast(dict[str, object], pointer["normalization_receipt"])
    receipt["digest"] = f"sha256:{'0' * 64}"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "digest mismatch" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_receipt_canonical_digest_mismatch(tmp_path: Path) -> None:
    raw_text = json.dumps(DOC)[:-1] + ",}"
    pointer_path, pointer = _publish(
        tmp_path, "op-receipt-canonical-mismatch", raw_text=raw_text
    )
    receipt_ref = cast(dict[str, object], pointer["normalization_receipt"])
    receipt_path = Path(cast(str, receipt_ref["uri"]).removeprefix("file://"))
    receipt_body = cast(
        dict[str, object], json.loads(receipt_path.read_text(encoding="utf-8"))
    )
    receipt_body["canonical_digest"] = f"sha256:{'0' * 64}"
    tampered_bytes = json.dumps(receipt_body).encode("utf-8")
    _ = receipt_path.write_text(json.dumps(receipt_body), encoding="utf-8")
    receipt_ref["digest"] = f"sha256:{hashlib.sha256(tampered_bytes).hexdigest()}"
    receipt_ref["size_bytes"] = len(tampered_bytes)
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "does not match the canonical payload" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_bare_payload(tmp_path: Path) -> None:
    cook_pyz = build_pyz.cached_bundle("cook")
    bare_payload = tmp_path / "bare-payload.json"
    _ = bare_payload.write_text(json.dumps(DOC), encoding="utf-8")
    result = _run(cook_pyz, "accept", str(bare_payload))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "$.contract_version is required" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_missing_payload_file(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-missing-payload")
    payload = cast(dict[str, object], pointer["payload"])
    payload_path = Path(cast(str, payload["uri"]).removeprefix("file://"))
    payload_path.unlink()
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "is missing at" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_unsafe_artifact_uri(tmp_path: Path) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-unsafe-uri")
    payload = cast(dict[str, object], pointer["payload"])
    payload["uri"] = "https://example.com/payload.json"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    result = _accept(pointer_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.startswith("ERROR:")
    assert "is not a file:// uri" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_rejects_missing_pointer_file(tmp_path: Path) -> None:
    missing_pointer = tmp_path / "does-not-exist.json"
    result = _accept(missing_pointer)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "pointer not found at" in result.stderr
    assert "Traceback" not in result.stderr


def test_cook_pyz_accepts_bare_relative_pointer_from_pointers_dir(
    tmp_path: Path,
) -> None:
    pointer_path, pointer = _publish(tmp_path, "op-relative")
    cook_pyz = build_pyz.cached_bundle("cook")
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(cook_pyz), "accept", pointer_path.name],
        cwd=str(pointer_path.parent),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wrapper = cast(dict[str, object], json.loads(result.stdout))
    value = cast(dict[str, object], wrapper["value"])
    assert value["plan_id"] == INVOCATION["plan_id"]
    assert pointer["destination_phase"] == "cook"