"""End-to-end coverage for mold.pyz's `migrate` contract command."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import (
    CanonicalArtifact,
    CurdPlan,
    supported_version_for,
    validate_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("pip") is None
    or (shutil.which("shiv") is None and importlib.util.find_spec("shiv") is None),
    reason="bundle integration requires requirements-build.txt",
)

CURD_PLAN_SCHEMA_URI = "https://schemas.easy-cheese.dev/curd-plan"

LEGACY_DOC = {
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


def _run(pyz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # Run from the bundle's own dir with PYTHONPATH stripped, so the only way an
    # import can resolve is from inside the .pyz itself.
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        cwd=str(pyz.parent),
        capture_output=True,
        text=True,
        env=env,
    )


def _write_document(tmp_path: Path, doc: object = LEGACY_DOC) -> Path:
    document = tmp_path / "document.json"
    _ = document.write_text(json.dumps(doc), encoding="utf-8")
    return document


def test_mold_pyz_dispatches_migrate_end_to_end(tmp_path: Path) -> None:
    mold_pyz = build_pyz.cached_bundle("mold")
    document = _write_document(tmp_path)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "migrate",
        str(document),
        "--source-schema-uri",
        CURD_PLAN_SCHEMA_URI,
        "--source-major",
        "0",
        "--source-minor",
        "9",
        "--operation-id",
        "op-migrate-e2e",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pointer = cast(dict[str, object], json.loads(result.stdout))
    assert pointer["operation_id"] == "op-migrate-e2e"
    assert pointer["normalization_receipt"] is not None
    pointer_path = artifact_root / "pointers" / "op-migrate-e2e.json"
    assert pointer_path.is_file()
    payload_paths = list((artifact_root / "payloads").glob("*.json"))
    assert payload_paths

    payload_bytes = payload_paths[0].read_bytes()
    validated = validate_contract(
        payload_bytes, CURD_PLAN_SCHEMA_URI, supported_version_for(CURD_PLAN_SCHEMA_URI)
    )
    assert isinstance(validated, CanonicalArtifact)
    payload = cast(CurdPlan, validated.value)
    assert payload.objective == LEGACY_DOC["goal"]
    assert payload.curds[0].curd_id == "runtime"


@pytest.mark.parametrize(
    ("source_major", "source_minor"),
    [("0", "8"), ("1", "1")],
)
def test_mold_pyz_migrate_rejects_unsupported_version(
    tmp_path: Path, source_major: str, source_minor: str
) -> None:
    mold_pyz = build_pyz.cached_bundle("mold")
    document = _write_document(tmp_path)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "migrate",
        str(document),
        "--source-schema-uri",
        CURD_PLAN_SCHEMA_URI,
        "--source-major",
        source_major,
        "--source-minor",
        source_minor,
        "--operation-id",
        "op-migrate-unsupported",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ERROR:" in result.stderr
    assert not (artifact_root / "pointers" / "op-migrate-unsupported.json").exists()


def test_mold_pyz_migrate_rejects_unprovable_route(tmp_path: Path) -> None:
    mold_pyz = build_pyz.cached_bundle("mold")
    document = _write_document(tmp_path)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "migrate",
        str(document),
        "--source-schema-uri",
        CURD_PLAN_SCHEMA_URI,
        "--source-major",
        "0",
        "--source-minor",
        "9",
        "--destination-phase",
        "not-a-real-phase",
        "--operation-id",
        "op-migrate-unprovable",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ERROR:" in result.stderr
    assert "not declared" in result.stderr
    assert not (artifact_root / "pointers" / "op-migrate-unprovable.json").exists()
