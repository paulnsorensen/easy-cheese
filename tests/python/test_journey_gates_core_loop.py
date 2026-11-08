"""Journey-gate tests for the /age, /cure, /plate, and /wheypoint suites.

Each recorded fixture in `skills/<skill>/evals/journey-gates.json` runs the
shipped `kinds.journey.argv` program the way skillz does: case files at the
workspace root, the final snapshot under `output/`, and the trace at
`trace/events.jsonl`. Every Claude-shaped fixture also runs re-expressed as
Codex App Server messages, and both shapes must give the same verdict.
"""

# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false, reportDeprecated=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from __future__ import annotations

import ast
import importlib.util
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = ("age", "cure", "plate", "wheypoint")
FIXTURE_KEYS = {"name", "case", "output", "output_deleted", "trace", "score", "fails"}
REQUIRED_KEYS = FIXTURE_KEYS - {"output_deleted"}
SANDBOX_SECONDS = 20  # skillz runs the whole gate under this limit.


def load_compiler() -> ModuleType:
    path = REPO_ROOT / "scripts" / "journey_gate_compiler.py"
    spec = importlib.util.spec_from_file_location("journey_gate_compiler", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contract_argv(skill: str) -> list[str]:
    path = REPO_ROOT / "skills" / skill / "evals" / "autoimprove.json"
    return json.loads(path.read_text(encoding="utf-8"))["kinds"]["journey"]["argv"]


def load_fixtures(skill: str) -> list[dict[str, Any]]:
    path = REPO_ROOT / "skills" / skill / "evals" / "journey-gates.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_cases(skill: str) -> dict[str, dict[str, str]]:
    path = REPO_ROOT / "skills" / skill / "evals" / "journeys.json"
    return {case["id"]: case["files"] for case in json.loads(path.read_text(encoding="utf-8"))}


def _hidden(rel: str) -> bool:
    parts = rel.split("/")
    return any(part.startswith(".") for part in parts) or parts[0] in ("home", "tmp")


def _put(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def materialize(root: Path, skill: str, fixture: dict[str, Any], events: list[dict[str, Any]]) -> Path:
    """Replayed output is the case files overlaid by `output`, minus `output_deleted`."""
    case = load_cases(skill)[fixture["case"]]
    ws = root / "ws"
    for rel, text in case.items():
        _put(ws, rel, text)
    snapshot = {rel: text for rel, text in case.items() if not _hidden(rel)}
    snapshot.update(fixture["output"])
    for rel in fixture.get("output_deleted", []):
        del snapshot[rel]
    (ws / "output").mkdir()
    for rel, text in snapshot.items():
        _put(ws, "output/" + rel, text)
    for runtime in ("home", "tmp"):
        (ws / runtime).mkdir()
    _put(ws, "trace/events.jsonl", "".join(json.dumps(event) + "\n" for event in events))
    return ws


def run_program(argv: list[str], ws: Path) -> dict[str, Any]:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(ws / "home"), "TMPDIR": str(ws / "tmp")}
    done = subprocess.run(argv, cwd=ws, env=env, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.strip().splitlines()
    assert len(lines) == 1, done.stdout
    return json.loads(lines[0])


def _exit_codes(trace: list[dict[str, Any]]) -> dict[str, int]:
    codes: dict[str, int] = {}
    for event in trace:
        for block in (event.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                text = block.get("content")
                failed = block.get("is_error") or str(text).lstrip().startswith("Exit code")
                codes[str(block.get("tool_use_id"))] = 1 if failed else 0
    return codes


def claude_to_codex(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-express a Claude stream-json trace as raw Codex App Server messages."""
    codes = _exit_codes(trace)
    cwd = next((e.get("cwd") for e in trace if e.get("subtype") == "init" and e.get("cwd")), None)
    thread: dict[str, Any] = {"id": "th"}
    if cwd:
        thread["cwd"] = cwd
    events: list[dict[str, Any]] = [{"method": "thread/started", "params": {"thread": thread}}]
    params = {"threadId": "th", "turnId": "tu"}
    index = 0
    for event in trace:
        if event.get("type") != "assistant":
            continue
        for block in event["message"]["content"]:
            args = block.get("input") or {}
            base: dict[str, Any] = {"id": f"item-{index}"}
            if block["type"] == "text":
                item = {**base, "type": "agentMessage", "text": block["text"]}
            elif block.get("name") == "Bash":
                code = codes.get(str(block.get("id")), 0)
                command = "/bin/bash -lc " + shlex.quote(args["command"])
                item = {**base, "type": "commandExecution", "command": command, "exitCode": code}
            elif block.get("name") in ("Write", "Edit", "MultiEdit"):
                new = args.get("content", args.get("new_string", ""))
                diff = "".join("+" + line + "\n" for line in str(new).splitlines())
                change = {"path": args["file_path"], "kind": {"type": "update"}, "diff": diff}
                item = {**base, "type": "fileChange", "changes": [change], "status": "completed"}
            else:
                continue
            events.append({"method": "item/completed", "params": {**params, "item": item}})
            index += 1
    return events


def _fixture_params(claude_only: bool = False) -> list[Any]:
    found: list[Any] = []
    for skill in SKILLS:
        for fixture in load_fixtures(skill):
            codex = any("method" in event for event in fixture["trace"])
            if not (claude_only and codex):
                found.append(pytest.param(skill, fixture, id=f"{skill}:{fixture['name']}"))
    return found


@pytest.mark.parametrize("skill", SKILLS)
def test_contract_argv_is_the_compiled_source(skill: str) -> None:
    compiler = load_compiler()
    assert skill in compiler.skills(REPO_ROOT)
    assert contract_argv(skill) == ["python3", "-I", "-c", compiler.compiled_source(REPO_ROOT, skill)]


@pytest.mark.parametrize("skill", SKILLS)
def test_compiled_source_is_stdlib_only_and_python39_syntax(skill: str) -> None:
    tree = ast.parse(contract_argv(skill)[3], feature_version=(3, 9))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module is not None
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names) | {"__future__"}, imported


def test_compiler_check_passes_on_the_repository() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "journey_gate_compiler.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize(("skill", "fixture"), _fixture_params())
def test_recorded_fixture_replays_to_its_verdict(tmp_path: Path, skill: str, fixture: dict[str, Any]) -> None:
    ws = materialize(tmp_path, skill, fixture, fixture["trace"])
    started = time.monotonic()
    got = run_program(contract_argv(skill), ws)
    assert time.monotonic() - started < SANDBOX_SECONDS / 2
    assert got == {"score": fixture["score"], "fails": fixture["fails"]}


@pytest.mark.parametrize(("skill", "fixture"), _fixture_params(claude_only=True))
def test_claude_fixture_gives_the_same_verdict_as_codex(tmp_path: Path, skill: str, fixture: dict[str, Any]) -> None:
    events = claude_to_codex(fixture["trace"])
    assert all("type" not in event for event in events)
    ws = materialize(tmp_path, skill, fixture, events)
    assert run_program(contract_argv(skill), ws) == {"score": fixture["score"], "fails": fixture["fails"]}


@pytest.mark.parametrize(("skill", "fixture"), _fixture_params())
def test_fixture_schema(skill: str, fixture: dict[str, Any]) -> None:
    assert REQUIRED_KEYS <= set(fixture) <= FIXTURE_KEYS
    case = load_cases(skill).get(fixture["case"])
    assert case is not None, fixture["case"]
    fails = fixture["fails"]
    assert fails == sorted(set(fails))
    assert (fixture["score"] == 1) == (fails == [])
    for rel, text in fixture["output"].items():
        assert isinstance(text, str)
        assert case.get(rel) != text, f"{rel} is unchanged; leave it out of output"
    for rel in fixture.get("output_deleted", []):
        assert rel in case and not _hidden(rel) and rel not in fixture["output"], rel


@pytest.mark.parametrize("skill", SKILLS)
def test_fixtures_cover_pass_fail_and_both_trace_shapes(skill: str) -> None:
    fixtures = load_fixtures(skill)
    names = [fixture["name"] for fixture in fixtures]
    assert len(names) == len(set(names))
    assert {fixture["score"] for fixture in fixtures} == {0, 1}
    native = [fx for fx in fixtures if any("method" in event for event in fx["trace"])]
    assert {fx["score"] for fx in native} == {0, 1}, "record a native Codex pass and fail"


def test_no_trace_fails_every_gate(tmp_path: Path) -> None:
    for skill in SKILLS:
        ws = tmp_path / skill
        (ws / "output").mkdir(parents=True)
        assert run_program(contract_argv(skill), ws) == {"score": 0, "fails": ["no-trace"]}
