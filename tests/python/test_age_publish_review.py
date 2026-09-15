"""These tests cover the `publish-review` command in `age.pyz`."""
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
AGE_PYZ = REPO_ROOT / "skills" / "age" / "scripts" / "age.pyz"

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("pip") is None
    or (shutil.which("shiv") is None and importlib.util.find_spec("shiv") is None),
    reason="bundle integration requires requirements-build.txt",
)

REVIEW_RESULT_SCHEMA_URI = "https://schemas.easy-cheese.dev/review-result"

VIEW = {
    "kind": "review_result",
    "payload": {
        "disposition": "findings",
        "findings": [
            {
                "severity": "high",
                "summary": "Unknown fields are not rejected",
                "evidence_keys": ["review-log"],
                "location": {
                    "path": "src/runtime.py",
                    "start_line": 40,
                    "end_line": 42,
                },
            }
        ],
        "coverage": [
            {"target": "correctness", "disposition": "covered"},
            {"target": "security", "disposition": "covered"},
        ],
    },
}

EVIDENCE = {
    "review-log": {
        "evidence_id": "evidence-review-log",
        "kind": "review",
        "artifact": {
            "artifact_id": "artifact-review-log",
            "role": "review",
            "uri": "repo://evidence/review-log.json",
            "digest": (
                "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            ),
            "size_bytes": 64,
            "media_type": "application/json",
        },
        "summary": "The failing review trace",
    }
}

ENVELOPE = {"view": VIEW, "evidence": EVIDENCE}


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


def _write_view(tmp_path: Path, *, envelope: object = ENVELOPE) -> Path:
    view = tmp_path / "view.json"
    _ = view.write_text(json.dumps(envelope), encoding="utf-8")
    return view


def test_age_pyz_publish_review_routes_age_to_cure(tmp_path: Path) -> None:
    view = _write_view(tmp_path)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        AGE_PYZ,
        "publish-review",
        "--view",
        str(view),
        "--slug",
        "review-normalized",
        "--operation-id",
        "op-review",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pointer = cast(dict[str, object], json.loads(result.stdout))
    assert pointer["source_phase"] == "age"
    assert pointer["destination_phase"] == "cure"
    payload = cast(dict[str, object], pointer["payload"])
    assert payload["schema_uri"] == REVIEW_RESULT_SCHEMA_URI

    pointer_path = artifact_root / "pointers" / "op-review.json"
    assert pointer_path.is_file()
    stored = cast(
        dict[str, object], json.loads(pointer_path.read_text(encoding="utf-8"))
    )
    assert stored == pointer

    payload_files = list((artifact_root / "payloads").glob("*.json"))
    assert len(payload_files) == 1
    persisted = cast(dict[str, object], json.loads(payload_files[0].read_text(encoding="utf-8")))
    assert persisted["review_id"] == "review-normalized"
    assert persisted["disposition"] == "findings"
    findings = cast(list[object], persisted["findings"])
    assert len(findings) == 1
    coverage = cast(list[object], persisted["coverage"])
    assert [cast(dict[str, object], row)["target"] for row in coverage] == [
        "correctness",
        "security",
    ]


def test_age_pyz_publish_review_rejects_bad_envelope(tmp_path: Path) -> None:
    bad_envelope = {"view": VIEW}  # missing "evidence"
    view = _write_view(tmp_path, envelope=bad_envelope)
    artifact_root = tmp_path / "artifacts"
    result = _run(
        AGE_PYZ,
        "publish-review",
        "--view",
        str(view),
        "--slug",
        "review-normalized",
        "--operation-id",
        "op-rejected",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ERROR:" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (artifact_root / "pointers" / "op-rejected.json").exists()
