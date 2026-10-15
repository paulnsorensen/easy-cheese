"""`cook.pyz validate-result` refuses unsafe finalization results before dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.skills.cook.commands import main
from easy_cheese_schemas.contracts import (
    _unstructure,  # pyright: ignore[reportPrivateUsage]
)
from tests.python.test_cook_execution import (
    _curd,  # pyright: ignore[reportPrivateUsage]
    _full_fixture,  # pyright: ignore[reportPrivateUsage]
    _FullFixture,  # pyright: ignore[reportPrivateUsage]
    _write_ref,  # pyright: ignore[reportPrivateUsage]
)


def _project(value: object) -> dict[str, object]:
    return cast(dict[str, object], _unstructure(value))


def _result(root: Path, fixture: _FullFixture, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "status": "ready",
        "ready": True,
        "request_id": "cook-request",
        "spec_ref": _project(fixture["spec_ref"]),
        "planner_result_ref": _project(fixture["planner_ref"]),
        "plan_ref": _project(fixture["plan_ref"]),
        "coverage": _project(fixture["coverage"]),
    }
    payload.update(overrides)
    path = root / "result.json"
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(result: Path, root: Path) -> int:
    return main(["validate-result", "--result", str(result), "--artifact-root", str(root)])


def test_valid_result_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "ok"
    fixture = _full_fixture(root, partial=False)
    assert _run(_result(root, fixture), root) == 0
    out = capsys.readouterr().out
    assert '"valid": true' in out.replace('\\"', '"')
    assert "curd_ids" in out


def test_tampered_spec_digest_refuses(tmp_path: Path) -> None:
    root = tmp_path / "digest"
    fixture = _full_fixture(root, partial=False)
    result = _result(root, fixture)
    _ = (root / "spec.md").write_bytes((root / "spec.md").read_bytes() + b"\n")
    assert _run(result, root) != 0


def test_tampered_scope_refuses(tmp_path: Path) -> None:
    root = tmp_path / "scope"
    fixture = _full_fixture(root, partial=False)
    coverage = _project(fixture["coverage"])
    coverage["curd_ids"] = ["leaf"]
    assert _run(_result(root, fixture, coverage=coverage), root) != 0


def test_spec_hold_refuses(tmp_path: Path) -> None:
    root = tmp_path / "hold"
    fixture = _full_fixture(root, partial=False, curds=(_curd("root"),))
    spec = (root / "spec.md").read_bytes().replace(
        b"gates_overridden: []\n",
        b'gates_overridden: []\nexecution_holds: ["operator review required"]\n',
        1,
    )
    fixture["spec_ref"] = _write_ref(
        root, spec, artifact_id="spec", role="spec", filename="spec.md",
        media_type="text/markdown",
    )
    assert _run(_result(root, fixture), root) != 0


def test_not_ready_result_refuses(tmp_path: Path) -> None:
    root = tmp_path / "not-ready"
    fixture = _full_fixture(root, partial=False)
    result = _result(root, fixture, status="saved-not-ready", ready=False)
    assert _run(result, root) != 0
