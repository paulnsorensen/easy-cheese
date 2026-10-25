"""Journey eval suites for `/skillz autoimprove`.

A skill that ships `evals/journeys.json` holds multi-turn journey cases: a
simulated user converses with an agent that runs the skill, a command gate
checks the raw trace and the output files, and a judge scores the transcript.
The runner reads cases only from a run's `cases.draft.json`, so these tests
hold the committed suite to the runner's documented rules, check that the
cases cover every behavior in `evals/journeys.md`, and run each gate on the
recorded pass and fail traces in `evals/journey-gates.json`.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
SUITES = sorted(path.parents[1] for path in SKILLS_DIR.glob("*/evals/journeys.json"))

# The runner's `_intake.py` constants and `_cases.py` fixture rules.
HOLDOUT_MINIMUM = 6
MINIMUM_FAMILIES = 3
RESERVED_ROOTS = {"home", "tmp", "output", "capture", "answer.json", "response-schema.json", "AGENTS.md", "CLAUDE.md"}
CASE_FIELDS = {"id", "family", "kind", "request", "brief", "max_turns", "requirements", "files", "expected", "source"}
CONTRACT_FIELDS = {"schema_version", "status", "skill", "invocation", "kinds", "helper", "editable", "surface", "statistics"}
GATE_SECONDS = 20
REQUIREMENT_ROW = re.compile(r"^\|\s*`?([A-Z][A-Z0-9]*-\d+)`?\s*\|")

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


def _scored_kind(contract: JsonObject) -> str:
    kinds = _kinds(contract)
    return "task" if "task" in kinds else next(iter(kinds))


def _gate_score(code: int, stdout: str) -> float:
    """Mirror the runner's `_command_score`: exit 0 and a JSON object with a score from 0 to 1."""
    if code != 0:
        return 0.0
    try:
        data = cast(object, json.loads(stdout))
    except ValueError:
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    score = cast(JsonObject, data).get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
        return 0.0
    return float(score)


def _scenarios() -> list[tuple[Path, JsonObject]]:
    found: list[tuple[Path, JsonObject]] = []
    for skill in SUITES:
        path = skill / "evals" / "journey-gates.json"
        if path.exists():
            found += [(skill, scenario) for scenario in _objects(_load(path), f"{skill.name} journey-gates.json")]
    return found


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
    if _scored_kind(_contract(skill)) == "journey":
        largest = sum(count for _, count in families.most_common(2))
        assert families.total() - largest >= HOLDOUT_MINIMUM, (
            f"family sizes {dict(families)} can leave fewer than {HOLDOUT_MINIMUM} holdout cases"
        )


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
    seeds = skill / "evals" / "evals.json"
    if seeds.exists():
        document = _load(seeds)
        if isinstance(document, dict):
            document = cast(JsonObject, document).get("evals")
        entries = _objects(document, f"{skill.name} evals.json")
        tasks = [entry for entry in entries if entry.get("assertions") and entry.get("expected_skill", skill.name) is not None]
        assert not tasks or "task" in kinds, "evals.json seeds task cases, so the contract needs a task kind"


@pytest.mark.parametrize("skill", SUITES, ids=_param_id)
def test_journey_gate_has_pass_and_fail_traces(skill: Path) -> None:
    path = skill / "evals" / "journey-gates.json"
    assert path.exists(), "every journey suite records gate traces in evals/journey-gates.json"
    scenarios = _objects(_load(path), path.name)
    assert {scenario.get("score") for scenario in scenarios} == {0, 1}, "the gate traces must show a pass and a fail"
    case_ids = {_text(case, "id") for case in _cases(skill)}
    assert {_text(scenario, "case") for scenario in scenarios} <= case_ids, "a gate trace names an unknown case"


@pytest.mark.parametrize(("skill", "scenario"), _scenarios(), ids=_param_id)
def test_journey_gate_verdict(skill: Path, scenario: JsonObject, tmp_path: Path) -> None:
    """Run the gate as the runner does: fixtures at the root, output/ files, trace/events.jsonl."""
    case = next(case for case in _cases(skill) if _text(case, "id") == _text(scenario, "case"))
    workspace = tmp_path / "workspace"
    files = _text_map(case.get("files"), "case files")
    outputs = {f"output/{name}": text for name, text in _text_map(scenario.get("output"), "scenario output").items()}
    for name, text in {**files, **outputs}.items():
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(text, encoding="utf-8")
    trace = _objects(scenario.get("trace"), "scenario trace")
    (workspace / "trace").mkdir(parents=True)
    _ = (workspace / "trace" / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in trace), encoding="utf-8"
    )
    for runtime in ("home", "tmp"):
        (workspace / runtime).mkdir()
    argv = _texts(_kinds(_contract(skill))["journey"].get("argv")) or []
    env = {"PATH": "/usr/bin:/bin", "HOME": str(workspace / "home"), "TMPDIR": str(workspace / "tmp")}
    proc = subprocess.run(argv, cwd=workspace, env=env, capture_output=True, text=True, timeout=GATE_SECONDS, check=False)
    assert _gate_score(proc.returncode, proc.stdout) == scenario.get("score"), (
        f"gate scored {proc.stdout.strip()!r} (exit {proc.returncode}); stderr: {proc.stderr[-800:]}"
    )
