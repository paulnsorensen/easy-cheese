"""Journey eval suites for `/skillz autoimprove`.

A skill that ships `evals/journeys.json` holds multi-turn journey cases: a
simulated user converses with an agent that runs the skill, a command gate
checks the raw trace and the output files, and a judge grades each case's
EARS criteria. These tests hold the committed suite to the runner's intake
rules and check that the cases cover every behavior in `evals/journeys.md`.
The gate programs and their recorded traces have their own tests.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
SUITES = sorted(path.parents[1] for path in SKILLS_DIR.glob("*/evals/journeys.json"))

# The runner's `_intake.py` constants and `_cases.py` fixture rules.
HOLDOUT_MINIMUM = 6
MINIMUM_FAMILIES = 4
RESERVED_ROOTS = {"home", "tmp", "output", "capture", "answer.json", "response-schema.json", "AGENTS.md", "CLAUDE.md"}
CASE_FIELDS = {"id", "family", "kind", "request", "brief", "max_turns", "requirements", "files", "expected", "source", "regression"}
EXPECTED_FIELDS = {"must", "must_not", "questions", "final_stop", "criteria"}
CRITERION_FIELDS = {"id", "text", "must", "from"}
CONTRACT_FIELDS = {"schema_version", "status", "skill", "invocation", "kinds", "helper", "editable", "surface", "statistics", "harness_phrases"}
REQUIREMENT_ROW = re.compile(r"^\|\s*`?([A-Z][A-Z0-9]*-\d+)`?\s*\|")
CRITERION_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
# One optional WHEN/WHILE/IF/WHERE clause, then one `THE <subject> SHALL <response>`.
EARS = re.compile(r"^(?:(?:WHEN|WHILE|IF|WHERE) .+? )?THE .+? SHALL .+$", re.DOTALL)
SOURCE_ITEM = re.compile(r"^(must|must_not):(\d+)$")

JsonObject = dict[str, object]

def _load(path: Path) -> object:
    return cast(object, json.loads(path.read_text(encoding="utf-8")))


def _object(value: object, where: str) -> JsonObject:
    assert isinstance(value, dict), f"{where} must be a JSON object"
    return cast(JsonObject, value)


def _objects(value: object, where: str) -> list[JsonObject]:
    assert isinstance(value, list), f"{where} must be a JSON list"
    return [_object(item, where) for item in cast(list[object], value)]


def _text(item: JsonObject, field: str) -> str:
    value = item.get(field)
    return value if isinstance(value, str) else ""


def _texts(value: object) -> list[str] | None:
    """Return the list when it holds only nonblank strings, else None."""
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    texts = [item for item in items if isinstance(item, str) and item.strip()]
    return texts if len(texts) == len(items) else None


def _text_map(value: object, where: str) -> dict[str, str]:
    mapping = _object(value, where)
    assert all(isinstance(text, str) for text in mapping.values()), f"{where} must map paths to text"
    return {name: cast(str, text) for name, text in mapping.items()}


def _cases(skill: Path) -> list[JsonObject]:
    return _objects(_load(skill / "evals" / "journeys.json"), f"{skill.name} journeys.json")


def _contract(skill: Path) -> JsonObject:
    return _object(_load(skill / "evals" / "autoimprove.json"), f"{skill.name} autoimprove.json")


def _kinds(contract: JsonObject) -> dict[str, JsonObject]:
    kinds = _object(contract.get("kinds"), "contract kinds")
    return {name: _object(grader, f"kind {name}") for name, grader in kinds.items()}



def _param_id(value: object) -> str:
    if isinstance(value, Path):
        return value.name
    if isinstance(value, dict):
        return _text(cast(JsonObject, value), "name")
    return str(value)


def test_journey_suites_exist() -> None:
    assert SUITES, "no skill ships evals/journeys.json"


@pytest.mark.parametrize("skill", SUITES, ids=_param_id)
def test_journey_cases_follow_the_runner_rules(skill: Path) -> None:
    cases = _cases(skill)
    assert cases, "journeys.json must hold a nonempty list"
    duplicates = sorted(name for name, count in Counter(_text(case, "id") for case in cases).items() if count > 1)
    assert not duplicates, f"duplicate case ids: {duplicates}"
    for case in cases:
        name = _text(case, "id")
        unknown = sorted(set(case) - CASE_FIELDS)
        assert not unknown, f"{name}: unknown fields {unknown}"
        assert case.get("kind") == "journey", f"{name}: kind must be journey"
        assert case.get("source") in ("skill", "session"), f"{name}: source must be skill or session"
        for field in ("id", "family", "request", "brief"):
            assert _text(case, field).strip(), f"{name}: {field} must be nonempty text"
        assert _text(case, "request").startswith(f"/{skill.name}"), f"{name}: request must invoke /{skill.name}"
        turns = case.get("max_turns", 8)
        assert isinstance(turns, int) and not isinstance(turns, bool) and 1 <= turns <= 8, (
            f"{name}: max_turns must be an integer from 1 to 8"
        )
        assert _texts(case.get("requirements")), f"{name}: requirements must be a nonempty list of ids"
        expected = case.get("expected")
        assert isinstance(expected, dict) and expected, f"{name}: expected must be a nonempty object"
        files = _text_map(case.get("files"), f"{name} files")
        assert files, f"{name}: files must be a nonempty map"
        for file_name in files:
            path = PurePosixPath(file_name)
            parts = path.parts
            assert parts and not path.is_absolute() and ".." not in parts, f"{name}: bad path {file_name}"
            assert not any(part.startswith(".") for part in parts), f"{name}: hidden fixture path {file_name}"
            assert parts[0] not in RESERVED_ROOTS and "AGENTS.md" not in parts, f"{name}: reserved fixture path {file_name}"


@pytest.mark.parametrize("skill", SUITES, ids=_param_id)
def test_journey_holdout_can_fill(skill: Path) -> None:
    """Splits go by family: one family to train, one to validation, the rest to holdout."""
    families = Counter(_text(case, "family") for case in _cases(skill))
    assert len(families) >= MINIMUM_FAMILIES, f"{len(families)} families; the runner needs {MINIMUM_FAMILIES}"
    largest = sum(count for _, count in families.most_common(2))
    assert families.total() - largest >= HOLDOUT_MINIMUM, (
        f"family sizes {dict(families)} can leave fewer than {HOLDOUT_MINIMUM} holdout cases"
    )


@pytest.mark.parametrize("skill", SUITES, ids=_param_id)
def test_journey_criteria_are_ears_and_trace_to_the_reference(skill: Path) -> None:
    """skillz intake stops a judged case without valid `expected.criteria`."""
    for case in _cases(skill):
        name = _text(case, "id")
        expected = _object(case.get("expected"), f"{name} expected")
        assert not set(expected) - EXPECTED_FIELDS, f"{name}: unknown expected fields"
        assert expected.get("must") or expected.get("must_not"), f"{name}: expected needs must or must_not"
        criteria = _objects(expected.get("criteria"), f"{name} criteria")
        assert criteria, f"{name}: no criteria"
        ids = [_text(item, "id") for item in criteria]
        assert len(ids) == len(set(ids)), f"{name}: duplicate criterion ids"
        assert any(item.get("must") is True for item in criteria), f"{name}: no dealbreaker criterion"
        for item in criteria:
            label = f"{name}/{_text(item, 'id')}"
            assert not set(item) - CRITERION_FIELDS, f"{label}: unknown fields"
            assert CRITERION_ID.match(_text(item, "id")), f"{label}: bad id"
            assert EARS.match(_text(item, "text")), f"{label}: not one EARS statement"
            assert item.get("must", False) in (True, False), f"{label}: must is a boolean"
            source = SOURCE_ITEM.match(_text(item, "from"))
            if source:
                items = cast(list[object], expected.get(source.group(1)) or [])
                assert int(source.group(2)) < len(items), f"{label}: from points past the list"


@pytest.mark.parametrize("skill", SUITES, ids=_param_id)
def test_journeys_cover_the_behavior_suite(skill: Path) -> None:
    lines = (skill / "evals" / "journeys.md").read_text(encoding="utf-8").splitlines()
    declared = [match.group(1) for line in lines if (match := REQUIREMENT_ROW.match(line))]
    assert declared, "journeys.md declares no behavior rows"
    assert len(declared) == len(set(declared)), "journeys.md repeats a behavior id"
    used = {item for case in _cases(skill) for item in _texts(case.get("requirements")) or []}
    assert not set(declared) - used, f"behaviors without a journey: {sorted(set(declared) - used)}"
    assert not used - set(declared), f"journeys cite undeclared behaviors: {sorted(used - set(declared))}"


@pytest.mark.parametrize("skill", SUITES, ids=_param_id)
def test_journey_contract_pairs_the_journey_grader(skill: Path) -> None:
    contract = _contract(skill)
    unknown = sorted(set(contract) - CONTRACT_FIELDS)
    assert not unknown, f"unknown contract fields {unknown}"
    assert contract.get("schema_version") == 1
    assert contract.get("status") in ("draft", "approved")
    assert contract.get("skill") == skill.name
    assert contract.get("invocation") == f"/{skill.name}"
    kinds = _kinds(contract)
    assert "journey" in kinds, "the contract declares no journey kind"
    journey = kinds["journey"]
    assert journey.get("grader") == "journey"
    assert _texts(journey.get("argv")), "the journey gate argv must be a nonempty list of text"
    assert "reference" in _text(journey, "rubric"), "the rubric must grade against reference"
    for kind, grader in kinds.items():
        assert (kind == "journey") == (grader.get("grader") == "journey"), f"kind {kind} pairs the wrong grader"
    assert set(kinds) == {"journey"}, "a journey contract scores only the journey kind"
    seeds = skill / "evals" / "evals.json"
    if seeds.exists():
        document = _load(seeds)
        if isinstance(document, dict):
            document = cast(JsonObject, document).get("evals")
        # skillz checks the family of every seed task entry, even in a journey-only run.
        for entry in _objects(document, f"{skill.name} evals.json"):
            if entry.get("kind", "task") == "task":
                assert _text(entry, "family").strip(), f"evals.json task entry {_text(entry, 'name')} has no family"


@pytest.mark.parametrize("skill", SUITES, ids=_param_id)
def test_journey_gate_has_pass_and_fail_traces(skill: Path) -> None:
    path = skill / "evals" / "journey-gates.json"
    assert path.exists(), "every journey suite records gate traces in evals/journey-gates.json"
    scenarios = _objects(_load(path), path.name)
    assert {scenario.get("score") for scenario in scenarios} == {0, 1}, "the gate traces must show a pass and a fail"
    case_ids = {_text(case, "id") for case in _cases(skill)}
    assert {_text(scenario, "case") for scenario in scenarios} <= case_ids, "a gate trace names an unknown case"


