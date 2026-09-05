"""These tests cover the `publish` command in `mold.pyz`."""
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

INVOCATION = {
    "plan_id": "curdplan-mold-cli-publish-1",
    "contract_version": {
        "schema_uri": CURD_PLAN_SCHEMA_URI,
        "major": "1",
        "minor": "0",
    },
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


def _write_fixtures(
    tmp_path: Path, *, doc: object = DOC, raw_text: str | None = None
) -> tuple[Path, Path]:
    document = tmp_path / "document.json"
    _ = document.write_text(
        raw_text if raw_text is not None else json.dumps(doc), encoding="utf-8"
    )
    invocation = tmp_path / "invocation.json"
    _ = invocation.write_text(json.dumps(INVOCATION), encoding="utf-8")
    return document, invocation


def test_mold_pyz_dispatches_publish_end_to_end(tmp_path: Path) -> None:
    mold_pyz = build_pyz.cached_bundle("mold")
    document, invocation = _write_fixtures(tmp_path)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "publish",
        str(document),
        "--invocation",
        str(invocation),
        "--operation-id",
        "op-e2e",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pointer = cast(dict[str, object], json.loads(result.stdout))
    assert pointer["operation_id"] == "op-e2e"
    pointer_path = artifact_root / "pointers" / "op-e2e.json"
    assert pointer_path.is_file()
    assert any((artifact_root / "payloads").glob("*.json"))


def test_mold_pyz_publish_recovers_syntax_error(tmp_path: Path) -> None:
    mold_pyz = build_pyz.cached_bundle("mold")
    # NBSP (U+00A0): json.loads rejects it as whitespace, str.strip removes it
    raw_text = chr(0xA0) + json.dumps(DOC) + chr(0xA0)
    document, invocation = _write_fixtures(tmp_path, raw_text=raw_text)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "publish",
        str(document),
        "--invocation",
        str(invocation),
        "--operation-id",
        "op-recovered",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pointer = cast(dict[str, object], json.loads(result.stdout))
    assert pointer["operation_id"] == "op-recovered"
    assert pointer["normalization_receipt"] is not None
    assert any((artifact_root / "receipts").glob("*.json"))


def test_mold_pyz_publish_rejects_bad_payload(tmp_path: Path) -> None:
    mold_pyz = build_pyz.cached_bundle("mold")
    bad_doc = {**DOC, "kind": "CURD_PLAN"}
    document, invocation = _write_fixtures(tmp_path, doc=bad_doc)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "publish",
        str(document),
        "--invocation",
        str(invocation),
        "--operation-id",
        "op-rejected",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ERROR:" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (artifact_root / "pointers" / "op-rejected.json").exists()


def test_mold_pyz_publish_pointer_names_the_mold_to_cook_route(tmp_path: Path) -> None:
    """The published pointer binds route identity, not just an operation id."""
    mold_pyz = build_pyz.cached_bundle("mold")
    document, invocation = _write_fixtures(tmp_path)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        mold_pyz,
        "publish",
        str(document),
        "--invocation",
        str(invocation),
        "--operation-id",
        "op-route",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pointer = cast(dict[str, object], json.loads(result.stdout))
    assert pointer["source_phase"] == "mold"
    assert pointer["destination_phase"] == "cook"
    contract_version = cast(dict[str, object], pointer["contract_version"])
    assert contract_version["schema_uri"] == (
        "https://schemas.easy-cheese.dev/handoff-pointer"
    )
    payload = cast(dict[str, object], pointer["payload"])
    assert payload["schema_uri"] == CURD_PLAN_SCHEMA_URI
    assert cast(str, payload["uri"]).startswith("file:")
    assert cast(str, pointer["request_digest"]).startswith("sha256:")
    stored = cast(
        dict[str, object],
        json.loads(
            (artifact_root / "pointers" / "op-route.json").read_text(encoding="utf-8")
        ),
    )
    assert stored == pointer
