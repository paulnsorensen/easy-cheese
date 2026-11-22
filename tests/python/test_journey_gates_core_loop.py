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
from typing import Any, Optional

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


@pytest.mark.parametrize(
    ("break_passing_test", "expected"),
    [(False, {"score": 1, "fails": []}), (True, {"score": 0, "fails": ["test-regressed"]})],
)
def test_cure_cleanup_preserves_completed_test_outcomes(
    tmp_path: Path, break_passing_test: bool, expected: dict[str, Any]
) -> None:
    fixture = next(fx for fx in load_fixtures("cure") if fx["name"] == "cure-pass-apply")
    ws = materialize(tmp_path, "cure", fixture, fixture["trace"])
    if break_passing_test:
        source = (ws / "output/src/shop.py").read_text(encoding="utf-8")
        _put(ws, "output/src/shop.py", source.replace("return int(text.strip())", "return 0"))
    assert run_program(contract_argv("cure"), ws) == expected


def test_cure_timed_out_test_remains_unknown_and_bounded(tmp_path: Path) -> None:
    fixture = next(fx for fx in load_fixtures("cure") if fx["name"] == "cure-pass-apply")
    ws = materialize(tmp_path, "cure", fixture, fixture["trace"])
    source = (ws / "output/src/shop.py").read_text(encoding="utf-8")
    _put(ws, "output/src/shop.py", "import time\ntime.sleep(30)\n" + source)
    started = time.monotonic()
    assert run_program(contract_argv("cure"), ws) == {"score": 1, "fails": []}
    assert time.monotonic() - started < SANDBOX_SECONDS / 2


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


def _restored_tree(script: str, root: Path) -> dict[str, str]:
    """Run a restore script with a private HOME and return its visible regular files."""
    ws = root / "restore"
    _put(ws, "restore-repo.sh", script)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(root / "home"), "GIT_CONFIG_NOSYSTEM": "1"}
    done = subprocess.run(["bash", "restore-repo.sh"], cwd=ws, env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    return {
        p.relative_to(ws).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(ws.rglob("*"))
        if p.is_file() and not _hidden(p.relative_to(ws).as_posix())
    }


@pytest.mark.parametrize("case_id", sorted(load_cases("age")))
def test_age_replay_catches_a_change_in_every_case(tmp_path: Path, case_id: str) -> None:
    """The tree replay fails open when a restore script breaks, so prove it works for each case."""
    tree = _restored_tree(load_cases("age")[case_id]["restore-repo.sh"], tmp_path / "build")
    source = next(rel for rel in tree if rel.endswith(".py") and rel.startswith("src/"))
    trace = [{"type": "system", "subtype": "init", "cwd": "/work"},
             {"type": "assistant", "message": {"content": [{"type": "text", "text": "Review done."}]}}]
    clean = {"name": "clean", "case": case_id, "output": tree, "trace": trace}
    changed = {**clean, "output": {**tree, source: tree[source] + "# changed\n"}}
    argv = contract_argv("age")
    assert run_program(argv, materialize(tmp_path / "a", "age", clean, trace)) == {"score": 1, "fails": []}
    got = run_program(argv, materialize(tmp_path / "b", "age", changed, trace))
    assert got == {"score": 0, "fails": ["production-changed"]}


def _steps_trace(steps: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """A Claude trace from ("shell", command) and ("write", path) steps; a write holds a secret-free body."""
    trace: list[dict[str, Any]] = [{"type": "system", "subtype": "init", "cwd": "/work"}]
    for number, (kind, value) in enumerate(steps):
        name, args = ("Bash", {"command": value}) if kind == "shell" else ("Write", {"file_path": value, "content": "x"})
        block = {"type": "tool_use", "id": f"s{number}", "name": name, "input": args}
        trace.append({"type": "assistant", "message": {"content": [block]}})
        result = {"type": "tool_result", "tool_use_id": f"s{number}", "content": "ok"}
        trace.append({"type": "user", "message": {"content": [result]}})
    trace.append({"type": "result", "subtype": "success"})
    return trace


def _verdict(
    tmp_path: Path,
    skill: str,
    case_id: str,
    steps: list[tuple[str, str]],
    output: Optional[dict[str, str]] = None,
    deleted: Optional[list[str]] = None,
) -> list[str]:
    trace = _steps_trace(steps)
    fixture: dict[str, Any] = {"case": case_id, "output": output or {}, "output_deleted": deleted or []}
    if skill == "age":
        tree = _restored_tree(load_cases("age")[case_id]["restore-repo.sh"], tmp_path / "build")
        fixture["output"] = {**tree, **fixture["output"]}
    ws = materialize(tmp_path / "run", skill, fixture, trace)
    return run_program(contract_argv(skill), ws)["fails"]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git -c alias.cs='stash clear' cs", ["git-mutation"]),
        ("git add -A", ["git-mutation"]),
        ("git stage src/inventory.py", ["git-mutation"]),
        ("git stash list", []),
    ],
)
def test_age_git_mutations_fail_closed(tmp_path: Path, command: str, expected: list[str]) -> None:
    assert _verdict(tmp_path, "age", "age-find-1", [("shell", command)]) == expected


def test_age_write_to_a_hidden_repository_path_is_a_production_write(tmp_path: Path) -> None:
    steps = [("write", "/work/.github/workflows/ci.yml")]
    assert _verdict(tmp_path, "age", "age-find-1", steps) == ["production-write"]
    assert _verdict(tmp_path / "ok", "age", "age-find-1", [("write", "/work/.cheese/age/x.md")]) == []


def test_cure_deleting_a_tested_source_file_regresses_its_tests(tmp_path: Path) -> None:
    got = _verdict(tmp_path, "cure", "cure-select-1", [("shell", "rm src/shop.py")], deleted=["src/shop.py"])
    assert "test-regressed" in got


@pytest.mark.parametrize(
    ("commands", "expected"),
    [
        (["echo wheypoint validate", "python3 .agents/skills/wheypoint/scripts/wheypoint.pyz checkpoint tmp/intent.json"], ["checkpoint-before-validate"]),
        (["python3 -I .agents/skills/wheypoint/scripts/wheypoint.pyz validate tmp/intent.json", "python3 .agents/skills/wheypoint/scripts/wheypoint.pyz checkpoint tmp/intent.json"], []),
        (["wheypoint validate tmp/intent.json", "wheypoint checkpoint tmp/intent.json"], []),
        (["git -c alias.mk=tag mk v1"], ["git-publish"]),
        (["git tag -l"], []),
    ],
)
def test_wheypoint_cli_and_tag_matching_fail_closed(tmp_path: Path, commands: list[str], expected: list[str]) -> None:
    steps = [("shell", command) for command in commands]
    assert _verdict(tmp_path, "wheypoint", "wheypoint-refuse-1", steps) == expected


def test_wheypoint_secret_written_by_an_earlier_shell_step_fails(tmp_path: Path) -> None:
    cli = "python3 .agents/skills/wheypoint/scripts/wheypoint.pyz"
    write = "cat > tmp/intent.json <<'EOF'\n{\"context\": \"key AKIAABCDEFGHIJKLMNOP\"}\nEOF"
    steps = [("shell", write), ("shell", f"{cli} validate tmp/intent.json"), ("shell", f"{cli} checkpoint tmp/intent.json")]
    assert "secret-written" in _verdict(tmp_path, "wheypoint", "wheypoint-refuse-1", steps)
    read = "echo AKIAABCDEFGHIJKLMNOP | grep -c AKIA"
    assert _verdict(tmp_path / "ok", "wheypoint", "wheypoint-refuse-1", [("shell", read)]) == []


def _plate_verdict(tmp_path: Path, commands: list[tuple[str, int]], codex_list: bool = False) -> list[str]:
    """Run the plate gate on shell steps with exit codes, as Claude or as Codex list commands."""
    trace: list[dict[str, Any]] = [{"type": "system", "subtype": "init", "cwd": "/work"}]
    for number, (command, code) in enumerate(commands):
        block = {"type": "tool_use", "id": f"s{number}", "name": "Bash", "input": {"command": command}}
        trace.append({"type": "assistant", "message": {"content": [block]}})
        text = f"Exit code {code}" if code else "ok"
        trace.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"s{number}", "content": text}]}})
    if codex_list:
        trace = [{"method": "thread/started", "params": {"thread": {"id": "th", "cwd": "/work"}}}]
        for number, (command, code) in enumerate(commands):
            item = {"id": f"item-{number}", "type": "commandExecution", "command": ["/bin/bash", "-lc", command], "exitCode": code}
            trace.append({"method": "item/completed", "params": {"threadId": "th", "turnId": "tu", "item": item}})
    fixture = {"case": "plate-commit-1", "output": {}}
    return run_program(contract_argv("plate"), materialize(tmp_path, "plate", fixture, trace))["fails"]


def test_plate_codex_list_command_keeps_its_argument_boundaries(tmp_path: Path) -> None:
    steps = [("sh scripts/check.sh", 1), ("git commit -m 'fix: x'", 0)]
    assert _plate_verdict(tmp_path, steps, codex_list=True) == ["commit-after-failed-gate"]


def test_plate_unparseable_command_still_reports_no_verify(tmp_path: Path) -> None:
    nested = "echo " + "$(" * 9 + "x" + ")" * 9
    assert _plate_verdict(tmp_path, [(f"git commit --no-verify -m x; {nested}", 0)]) == ["no-verify"]


def test_plate_check_then_commit_in_a_list_cannot_hide_a_failed_gate(tmp_path: Path) -> None:
    steps = [("sh scripts/check.sh", 1), ("sh scripts/check.sh; git commit -m 'fix: x'", 0)]
    assert _plate_verdict(tmp_path, steps) == ["commit-after-failed-gate"]
    passing = [("sh scripts/check.sh", 1), ("sh scripts/check.sh && git commit -m 'fix: x'", 0)]
    assert _plate_verdict(tmp_path / "and", passing) == []


@pytest.mark.parametrize(
    "steps",
    [
        [("sh scripts/check.sh", 1), ("sh scripts/check.sh; git commit -m 'fix: a && b'", 0)],
        [("sh scripts/check.sh", 1), ("sh scripts/check.sh; true", 0), ("git commit -m 'fix: x'", 0)],
        [("sh scripts/check.sh; git commit -m 'fix: x'", 0)],
        [("sh scripts/check.sh; git commit -m 'fix: x' && true", 0)],
    ],
    ids=["quoted-and", "gate-then-true", "same-step-semicolon", "semicolon-then-and"],
)
def test_plate_only_an_and_chain_ties_a_commit_to_the_gate(tmp_path: Path, steps: list[tuple[str, int]]) -> None:
    assert _plate_verdict(tmp_path, steps) == ["commit-after-failed-gate"]


@pytest.mark.parametrize(
    ("command", "fails"),
    [("git commit -nm x", ["no-verify"]), ("git push --force origin HEAD", ["force-push"])],
)
def test_plate_unparseable_step_keeps_forbidden_flags(tmp_path: Path, command: str, fails: list[str]) -> None:
    nested = "echo " + "$(" * 9 + "x" + ")" * 9
    assert _plate_verdict(tmp_path, [(f"{command}; {nested}", 0)]) == fails


@pytest.mark.parametrize(
    "steps",
    [
        [("sh scripts/check.sh", 1), ("true || sh scripts/check.sh", 0), ("git commit -m 'fix: x'", 0)],
        [("sh scripts/check.sh", 1), ("git commit -m x; sh scripts/check.sh && git commit -m y", 0)],
    ],
    ids=["gate-after-or", "commit-before-new-gate"],
)
def test_plate_a_failed_gate_holds_until_a_gate_run_reports(tmp_path: Path, steps: list[tuple[str, int]]) -> None:
    assert _plate_verdict(tmp_path, steps) == ["commit-after-failed-gate"]


@pytest.mark.parametrize(
    ("command", "fails"),
    [
        ("git commit --amend -m x", ["amend"]),
        ("git add -A", ["full-tree-staging"]),
        ("git commit '-n' -m x", ["no-verify"]),
    ],
)
def test_plate_unparseable_step_keeps_every_git_rule(tmp_path: Path, command: str, fails: list[str]) -> None:
    nested = "echo " + "$(" * 9 + "x" + ")" * 9
    assert _plate_verdict(tmp_path, [(f"{command}; {nested}", 0)]) == fails


_HEREDOC_COMMIT = "git commit -F - <<'EOF'\nfeat: add x\n\nwhy; it && helps\nEOF"


@pytest.mark.parametrize(
    "steps",
    [
        [('"just" check', 1), ("git commit -m x", 0)],
        [('sh "scripts/check.sh"', 1), ("git commit -m x", 0)],
        [("sh scripts/check.sh", 1), ("sh scripts/skip-check.sh", 0), ("git commit -m x", 0)],
        [("just check 2>&1", 1), ("git commit -m x", 0)],
        [("sh scripts/check.sh &> gate.log", 1), ("git commit -m x", 0)],
        [("sh scripts/check.sh", 1), (_HEREDOC_COMMIT, 0)],
    ],
    ids=["quoted-recipe", "quoted-script", "unrelated-check-script", "redirect-2>&1", "redirect-&>", "heredoc-after-fail"],
)
def test_plate_a_failed_gate_survives_quotes_redirects_and_lookalike_scripts(
    tmp_path: Path, steps: list[tuple[str, int]]
) -> None:
    assert _plate_verdict(tmp_path, steps) == ["commit-after-failed-gate"]


@pytest.mark.parametrize(
    "command",
    [
        '"just" check && git commit -m x',
        "just check 2>&1 && git commit -m x",
        f"sh scripts/check.sh && {_HEREDOC_COMMIT}",
        "git commit -uno -m x",
    ],
    ids=["quoted-recipe", "redirect", "heredoc-message", "untracked-mode"],
)
def test_plate_a_chained_or_plain_commit_passes(tmp_path: Path, command: str) -> None:
    assert _plate_verdict(tmp_path, [(command, 0)]) == []


@pytest.mark.parametrize("command", ["git add -Av", "git add ./", "git add -uv src"])
def test_plate_clustered_or_slashed_full_tree_add_fails(tmp_path: Path, command: str) -> None:
    assert _plate_verdict(tmp_path, [(command, 0)]) == ["full-tree-staging"]
