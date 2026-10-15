"""Finalize output, retry, and spec-input bounds on the Mold to Cook boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared.taste_test import MAX_SPEC_BYTES
from easy_cheese.skills.mold import producer
from easy_cheese.skills.mold.producer import FinalizationError, finalize_mold
from easy_cheese_schemas.schema_runtime import ContractValidationError
from tests.python.test_mold_cook_producer import finalize_fixture, make_spec

REPO = Path(__file__).parent.parent.parent


def test_finalize_command_matches_documented_dispatch_form(tmp_path: Path) -> None:
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "ready"
    command = cast(list[str], outcome.payload["command"])
    assert command == ["/cook", "--auto", "--result", str(outcome.result_path)]
    for doc in (
        "skills/mold/references/curdle.md",
        "skills/mold/references/handoff-menus.md",
        "skills/cheese/references/escalation.md",
    ):
        assert "/cook --auto --result" in (REPO / doc).read_text(encoding="utf-8")
    cook = (REPO / "skills/cook/SKILL.md").read_text(encoding="utf-8")
    assert "`--result <path>`" in cook
    saved = cast(
        dict[str, object],
        json.loads(cast(Path, outcome.result_path).read_text(encoding="utf-8")),
    )
    assert saved["command"] == command


def test_identical_finalize_retry_is_idempotent(tmp_path: Path) -> None:
    first = finalize_fixture(tmp_path)
    first_bytes = cast(Path, first.result_path).read_bytes()
    second = finalize_fixture(tmp_path)

    assert second.status == "ready"
    assert second.payload == first.payload
    assert cast(Path, second.result_path).read_bytes() == first_bytes


def test_invalid_bound_inputs_are_saved_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(**_: object) -> object:
        raise ContractValidationError("detached")

    monkeypatch.setattr(producer, "validate_bound_execution", refuse)
    outcome = finalize_fixture(tmp_path)

    assert outcome.status == "saved-not-ready"
    assert outcome.ready is False
    assert "command" not in outcome.payload
    requirements = cast(list[dict[str, object]], outcome.payload["requirements"])
    assert [r["requirement_id"] for r in requirements] == ["execution-inputs"]
    assert cast(Path, outcome.result_path).is_file()


def _finalize(spec: Path, tmp_path: Path) -> object:
    return finalize_mold(
        spec,
        artifact_root=tmp_path / "artifacts",
        operation_id="bounds",
        request_id="bounds-request",
    )


def test_spec_over_size_bound_is_refused(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    _ = spec.write_bytes(spec.read_bytes() + b"x" * (MAX_SPEC_BYTES + 1))

    with pytest.raises(FinalizationError):
        _ = _finalize(spec, tmp_path)


def test_non_utf8_spec_is_refused(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    _ = spec.write_bytes(spec.read_bytes() + b"\xff\xfe")

    with pytest.raises(FinalizationError):
        _ = _finalize(spec, tmp_path)


def test_non_regular_spec_is_refused(tmp_path: Path) -> None:
    directory = tmp_path / "spec-dir"
    directory.mkdir()

    with pytest.raises(FinalizationError):
        _ = _finalize(directory, tmp_path)


def test_saved_result_file_feeds_bound_validation(tmp_path: Path) -> None:
    from easy_cheese.shared.mold_cook_handoff import validate_bound_execution
    from easy_cheese_schemas import ArtifactRef, MoldCookCoverage
    from easy_cheese_schemas.schema_runtime import (
        _typed_host as structure,  # pyright: ignore[reportPrivateUsage]
    )

    outcome = finalize_fixture(tmp_path)
    saved = cast(
        dict[str, object],
        json.loads(Path(str(outcome.payload["result_path"])).read_text(encoding="utf-8")),
    )
    assert saved["status"] == "ready"
    refs = [
        structure(saved[name], ArtifactRef, name)
        for name in ("spec_ref", "planner_result_ref", "plan_ref")
    ]
    coverage = structure(saved["coverage"], MoldCookCoverage, "coverage")

    plan = validate_bound_execution(
        spec_ref=refs[0],
        planner_result_ref=refs[1],
        plan_ref=refs[2],
        coverage=coverage,
        artifact_root=tmp_path / "artifacts",
    )
    assert tuple(curd.curd_id for curd in plan.curds) == coverage.curd_ids
