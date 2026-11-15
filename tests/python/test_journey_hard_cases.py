"""Regression guard: each harder journey fixture holds a real, solvable trap.

`tests/fixtures/journey_answers/<skill>.json` maps a journey case id to its
reported loop, the loop's success text, a reference fix, and an optional decoy
fix. A decoy fix is the plausible wrong repair that the case criteria forbid.

For every listed case, the fixture loop fails, the decoy fix leaves the loop
failing, and the reference fix makes the loop and the fixture's own unit tests
pass. So a case cannot pass through a symptom repair, and its criteria grade a
failure that exists.

Every journey case names only requirement ids that its `journeys.md` table
defines, and every criterion `from` points at an existing must or must_not item.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ANSWERS = REPO_ROOT / "tests" / "fixtures" / "journey_answers"
SUITES = ("mold", "pasteurize")

Json = dict[str, Any]


def _suite(skill: str) -> list[Json]:
    path = REPO_ROOT / "skills" / skill / "evals" / "journeys.json"
    return cast("list[Json]", json.loads(path.read_text(encoding="utf-8")))


def _answer_params() -> list[Any]:
    params: list[Any] = []
    for path in sorted(ANSWERS.glob("*.json")):
        cases = {case["id"]: case for case in _suite(path.stem)}
        answers = cast("dict[str, Json]", json.loads(path.read_text(encoding="utf-8")))
        for case_id, answer in answers.items():
            params.append(pytest.param(cases[case_id], answer, id=case_id))
    return params


def _workspace(root: Path, files: dict[str, str], overlay: dict[str, str] | None) -> Path:
    for rel, text in {**files, **(overlay or {})}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _run(workspace: Path, command: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ["PATH"], "HOME": str(workspace), "LANG": "C.UTF-8", "TZ": "UTC"}
    return subprocess.run(
        ["bash", "-c", command],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _loop_passes(workspace: Path, answer: Json) -> bool:
    result = _run(workspace, answer["loop"])
    return result.returncode == 0 and answer["loop_ok"] in result.stdout + result.stderr


@pytest.mark.parametrize(("case", "answer"), _answer_params())
def test_fixture_reproduces_the_reported_failure(tmp_path: Path, case: Json, answer: Json) -> None:
    workspace = _workspace(tmp_path, case["files"], None)
    assert not _loop_passes(workspace, answer)


@pytest.mark.parametrize(("case", "answer"), _answer_params())
def test_reference_fix_passes_the_loop_and_the_fixture_tests(
    tmp_path: Path, case: Json, answer: Json
) -> None:
    workspace = _workspace(tmp_path, case["files"], answer["fix"])
    assert _loop_passes(workspace, answer)
    tests = _run(workspace, "python3 -m unittest")
    assert tests.returncode == 0, tests.stderr


@pytest.mark.parametrize(("case", "answer"), _answer_params())
def test_decoy_fix_leaves_the_loop_failing(tmp_path: Path, case: Json, answer: Json) -> None:
    if not answer.get("decoy"):
        pytest.skip("no file-level decoy for this case")
    workspace = _workspace(tmp_path, case["files"], answer["decoy"])
    assert not _loop_passes(workspace, answer)


def _requirement_ids(skill: str) -> set[str]:
    table = (REPO_ROOT / "skills" / skill / "evals" / "journeys.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| `([A-Z]+-\d+)` \|", table, flags=re.MULTILINE))


@pytest.mark.parametrize("skill", SUITES)
def test_cases_name_defined_requirements(skill: str) -> None:
    defined = _requirement_ids(skill)
    for case in _suite(skill):
        assert set(case["requirements"]) <= defined, case["id"]


@pytest.mark.parametrize("skill", SUITES)
def test_journeys_table_lists_each_case_under_its_requirements(skill: str) -> None:
    table = (REPO_ROOT / "skills" / skill / "evals" / "journeys.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| `([A-Z]+-\d+)` \|[^|]*\| (.*) \|$", table, flags=re.MULTILINE))
    for case in _suite(skill):
        for requirement in case["requirements"]:
            assert f"`{case['id']}`" in rows[requirement], (case["id"], requirement)


@pytest.mark.parametrize("skill", SUITES)
def test_criteria_sources_point_at_existing_items(skill: str) -> None:
    for case in _suite(skill):
        expected = case["expected"]
        ids = [criterion["id"] for criterion in expected["criteria"]]
        assert len(ids) == len(set(ids)), case["id"]
        for criterion in expected["criteria"]:
            source = criterion.get("from")
            if source is None or ":" not in source:
                continue
            field, index = source.split(":")
            assert int(index) < len(expected[field]), (case["id"], source)
