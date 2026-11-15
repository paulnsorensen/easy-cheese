from __future__ import annotations

import json
from pathlib import Path

import pytest

from easy_cheese.skills.plate import flat_carve


def _plan(shape: str = "orthogonal_flat", groups: int = 2) -> dict[str, object]:
    return {
        "contract_version": {
            "schema_uri": "https://schemas.easy-cheese.dev/pr-plan",
            "major": "1",
            "minor": "0",
        },
        "shape": shape,
        "groups": [
            {
                "branch": "feat/one",
                "title": "feat: one",
                "base": "main",
                "commits": ["abc1234", "def5678"],
                "depends_on": [],
            },
            {
                "branch": "fix/two",
                "title": "fix: two",
                "base": "main",
                "commits": ["0123456"],
                "depends_on": [],
            },
        ][:groups],
    }


def _write(tmp_path: Path, plan: dict[str, object]) -> str:
    path = tmp_path / "plan.json"
    _ = path.write_text(json.dumps(plan))
    return str(path)


def test_carve_emits_branch_picks_and_restore_per_group(tmp_path: Path) -> None:
    result = flat_carve.carve_cmd("work", pr_plan=_write(tmp_path, _plan()))

    groups = result["groups"]
    assert isinstance(groups, list)
    assert groups[0] == {
        "branch": "feat/one",
        "base": "main",
        "carve": [
            "git switch -c 'feat/one' 'main'",
            "git cherry-pick 'abc1234'",
            "git cherry-pick 'def5678'",
        ],
        "restore": "git switch 'work'",
    }
    assert groups[1]["carve"] == ["git switch -c 'fix/two' 'main'", "git cherry-pick '0123456'"]


def test_carve_never_pushes_or_creates_prs(tmp_path: Path) -> None:
    result = flat_carve.carve_cmd("work", pr_plan=_write(tmp_path, _plan()))

    text = json.dumps(result)
    assert "push" not in text
    assert "gh " not in text


def test_carve_rejects_other_shapes(tmp_path: Path) -> None:
    path = _write(tmp_path, _plan("single", groups=1))

    assert flat_carve.main(["--source-branch", "work", "--pr-plan", path]) == 2


def test_cli_prints_json_for_a_flat_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, _plan())

    assert flat_carve.main(["--source-branch", "work", "--pr-plan", path]) == 0

    assert json.loads(capsys.readouterr().out)["groups"][0]["branch"] == "feat/one"
