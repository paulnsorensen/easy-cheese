"""pr_plan_to_branches emits from the validated PrPlan v1 document (AC-8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared.fanout import pr_plan_to_branches
from easy_cheese_schemas import PrPlan, load

CONTRACT_VERSION = {
    "schema_uri": "https://schemas.easy-cheese.dev/pr-plan",
    "major": "1",
    "minor": "0",
}


def _group(body: object) -> dict[str, object]:
    return {
        "branch": "ultracook/foo/pr-1",
        "title": "feat(foo): ship",
        "base": "main",
        "commits": ["abc1234"],
        "body": body,
    }


def test_null_body_emits_an_empty_body() -> None:
    loaded = load(
        {"contract_version": CONTRACT_VERSION, "shape": "single", "groups": [_group(None)]},
        PrPlan,
        strict=True,
    )
    assert loaded.value is not None

    commands = pr_plan_to_branches.emit_commands(loaded.value)

    assert any("--body ''" in line for line in commands)


def test_unversioned_document_exits_nonzero_without_emitting(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan: dict[str, object] = {
        "shape": "single",
        "groups": [
            {
                "branch": "ultracook/foo/pr-1",
                "title": "feat(foo): ship",
                "base": "main",
                "commits": ["abc1234"],
            }
        ],
    }
    path = tmp_path / "plan.json"
    _ = path.write_text(json.dumps(plan))

    assert pr_plan_to_branches.main([str(path)]) == 1

    captured = capsys.readouterr()
    assert "contract_version" in captured.err
    assert "git checkout" not in captured.out


def test_convert_returns_commands_for_a_valid_plan(tmp_path: Path) -> None:
    plan = {"contract_version": CONTRACT_VERSION, "shape": "single", "groups": [_group(None)]}
    path = tmp_path / "plan.json"
    _ = path.write_text(json.dumps(plan))

    result = pr_plan_to_branches.convert(str(path))
    commands = cast("list[str]", result["commands"])

    assert any("git checkout -b" in line for line in commands)
