"""These tests cover the `remediate-plan` command in `cure.pyz`.

The command accepts the age->cure `HandoffPointer` (produced by `age.pyz
publish-review`), checks the selected finding ids against the published
`ReviewResult`, and persists a remediate child `CurdPlan` before any coder
runs. An unknown finding id halts the command and writes nothing.
"""
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
CURE_PYZ = REPO_ROOT / "skills" / "cure" / "scripts" / "cure.pyz"

pytestmark = pytest.mark.skipif(  # noqa: V107
    importlib.util.find_spec("build") is None
    or importlib.util.find_spec("pip") is None
    or (shutil.which("shiv") is None and importlib.util.find_spec("shiv") is None),
    reason="bundle integration requires requirements-build.txt",
)

ENVELOPE = {
    "view": {
        "kind": "review_result",
        "payload": {
            "disposition": "findings",
            "findings": [
                {
                    "severity": "high",
                    "summary": "Unvalidated path joined into fs.read",
                    "evidence_keys": ["review-log"],
                    "location": {
                        "path": "src/handler.py",
                        "start_line": 40,
                        "end_line": 42,
                    },
                }
            ],
            "coverage": [{"target": "security", "disposition": "covered"}],
        },
    },
    "evidence": {
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
    },
}


def _run(pyz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    _ = env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        cwd=str(pyz.parent),
        capture_output=True,
        text=True,
        env=env,
    )


def _publish_pointer(tmp_path: Path, slug: str) -> Path:
    """Publish a ReviewResult via age.pyz and return the HandoffPointer path."""
    view = tmp_path / "view.json"
    _ = view.write_text(json.dumps(ENVELOPE), encoding="utf-8")
    artifact_root = tmp_path / "artifacts"
    result = _run(
        AGE_PYZ,
        "publish-review",
        "--view",
        str(view),
        "--slug",
        slug,
        "--operation-id",
        f"op-{slug}",
        "--artifact-root",
        str(artifact_root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    pointer = artifact_root / "pointers" / f"op-{slug}.json"
    assert pointer.is_file()
    return pointer


def test_remediate_plan_persists_a_child_curd_plan(tmp_path: Path) -> None:
    slug = "rev-remediate"
    pointer = _publish_pointer(tmp_path, slug)
    result = _run(
        CURE_PYZ,
        "remediate-plan",
        "--pointer",
        str(pointer),
        "--finding-ids",
        f"{slug}/finding/1",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    plan_path = Path(result.stdout.strip())
    assert plan_path.is_file(), f"expected persisted plan at {plan_path}"
    assert plan_path == tmp_path / "artifacts" / "plans" / f"{slug}-remediate.curd-plan.json"
    plan = cast(dict[str, object], json.loads(plan_path.read_text(encoding="utf-8")))
    # A remediate child plan cites the plan under review and derives its curd.
    assert plan["parent_plan_ref"] is not None
    curds = cast(list[object], plan["curds"])
    assert len(curds) == 1
    curd = cast(dict[str, object], curds[0])
    lineage = cast(dict[str, object], curd["lineage"])
    assert lineage["identity_action"] == "derive"
    # One criterion per selected finding.
    assert len(cast(list[object], curd["criteria"])) == 1


def test_remediate_plan_unknown_finding_id_halts_and_writes_nothing(
    tmp_path: Path,
) -> None:
    slug = "rev-unknown"
    pointer = _publish_pointer(tmp_path, slug)
    result = _run(
        CURE_PYZ,
        "remediate-plan",
        "--pointer",
        str(pointer),
        "--finding-ids",
        f"{slug}/finding/9",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{slug}/finding/9" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "artifacts" / "plans").exists()
