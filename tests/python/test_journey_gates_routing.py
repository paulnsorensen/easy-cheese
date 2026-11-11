"""Journey-gate tests for the /cheese, /briesearch, and /culture contracts.

Each verdict runs the shipped `kinds.journey.argv` program twice: once on a
Claude stream-json trace and once on the same steps in Codex App Server shape.
The shared harness lives in `test_journey_gates.py`.
"""

# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from tests.python.test_journey_gates import (
    ABS,
    SHAPES,
    Scn,
    _put,
    check,
    contract_argv,
    run_program,
    tempfile_dir,
)

TAIL = "def tail(lines, n):\n    return lines[-n:]\n"
CHEESE_FILES = {
    "src/tail.py": TAIL,
    "README.md": "# Tail\n",
    "restore-notes.sh": "mkdir -p .cheese/notes\n",
}
RECEIPT_OK = "Intent: cook\nReason: bounded fix\nTarget: /cook src/tail.py\nroute: intent=cook target=cook path=fast probes=0"
CHEESE_CLEAN = Scn(
    CHEESE_FILES,
    steps=(
        ("shell", "bash restore-notes.sh"),
        ("write", ".cheese/notes/route.md"),
        ("shell", "cat src/tail.py > /tmp/peek.txt"),
        ("text", RECEIPT_OK),
        ("text", "/cook is not installed here, so I stop and do not edit src/tail.py."),
    ),
)


# --- /cheese -----------------------------------------------------------------


def test_cheese_clean_route_passes(tmp_path: Path) -> None:
    check(tmp_path, "cheese", CHEESE_CLEAN)


@pytest.mark.parametrize(
    ("step", "out", "fails"),
    [
        (("write", "src/tail.py"), {"src/tail.py": TAIL + "# x\n"}, {"edit-tool", "fixture-changed"}),
        (("write", "specs/auth.md"), {"specs/auth.md": "# Auth\n"}, {"edit-tool", "new-output-file"}),
        (("shell", "echo x >> src/tail.py"), {}, {"shell-redirect-write"}),
        (("shell", "printf x | tee NOTES.md"), {}, {"shell-redirect-write"}),
        (("shell", "touch src/new.py"), {}, {"shell-file-write"}),
        (("shell", "sed -i 's/-n/-n - 1/' src/tail.py"), {}, {"shell-file-write"}),
        (("shell", "rm README.md"), {"README.md": None}, {"shell-file-write", "fixture-changed"}),
        (("shell", "bash -c 'cp README.md docs.md'"), {}, {"shell-file-write"}),
    ],
)
def test_cheese_visible_writes_fail(
    tmp_path: Path, step: tuple[str, str], out: dict[str, Any], fails: set[str]
) -> None:
    check(tmp_path, "cheese", CHEESE_CLEAN.but(out=out, then=[step]), fails)


@pytest.mark.parametrize("flag", ["--in-place", "--in-place=.bak"])
def test_cheese_sed_long_in_place_fails(tmp_path: Path, flag: str) -> None:
    check(tmp_path, "cheese", CHEESE_CLEAN.but(then=[("shell", f"sed {flag} 's/a/b/' src/tail.py")]), {"shell-file-write"})


@pytest.mark.parametrize("command", ["sed 's/a/b/' src/tail.py", "perl --in-place 's/a/b/' src/tail.py"])
def test_cheese_nonmutating_sed_and_perl_long_flag_pass(tmp_path: Path, command: str) -> None:
    check(tmp_path, "cheese", CHEESE_CLEAN.but(then=[("shell", command)]))


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        "python3 -m pytest tests",
        "python -m unittest discover -s tests",
        "uv run pytest",
        "uvx --from pytest pytest",
        "just check",
        "npm test",
        "npm run test",
        "cargo test",
        "go test ./...",
        "make test",
        "cd src && bats tests",
        "env CI=1 timeout 60 pytest",
    ],
)
def test_cheese_test_runner_fails(tmp_path: Path, command: str) -> None:
    check(tmp_path, "cheese", CHEESE_CLEAN.but(then=[("shell", command)]), {"test-runner"})


@pytest.mark.parametrize(
    "command",
    [
        "cat src/tail.py",
        "ls tests",
        "grep -n pytest README.md",
        'echo "run pytest after /cook"',
        "git status --short",
        "git log --oneline -3",
        "mkdir -p .cheese/notes",
        "python3 .agents/skills/cheese/scripts/cheese.pyz wheypoint-resolve --ref notes",
    ],
)
def test_cheese_benign_commands_pass(tmp_path: Path, command: str) -> None:
    check(tmp_path, "cheese", CHEESE_CLEAN.but(then=[("shell", command)]))


@pytest.mark.parametrize(
    ("command", "fails"),
    [
        ("git commit -am wip", {"git-commit"}),
        ("git push origin HEAD", {"git-push"}),
        ("gh pr create --fill", {"open-pr"}),
    ],
)
def test_cheese_publication_fails(tmp_path: Path, command: str, fails: set[str]) -> None:
    check(tmp_path, "cheese", CHEESE_CLEAN.but(then=[("shell", command)]), fails)


@pytest.mark.parametrize(
    ("line", "fails"),
    [
        ("route: intent=clarify target=clarify path=escalated probes=1", set()),
        ("`route: intent=debug target=pasteurize path=escalated probes=3`", set()),
        ("route: intent=cook target=/cook path=fast probes=0", {"receipt-format"}),
        ("route: intent=cook target=cook path=fast probes=0 took=2s", {"receipt-format"}),
        ("route: cook", {"receipt-format"}),
        ("route: intent=cook target=cook path=fast probes=2", {"receipt-path-probes"}),
        ("route: intent=cook target=cook path=escalated probes=0", set()),
    ],
)
def test_cheese_receipt_rules(tmp_path: Path, line: str, fails: set[str]) -> None:
    scn = CHEESE_CLEAN.but(steps=[("text", "Intent: cook\n" + line)])
    check(tmp_path, "cheese", scn, fails)


# --- /briesearch -------------------------------------------------------------

DOC_URL = "https://docs.legacyfmt.dev/changelog#v2"
BRIE_FILES = {
    "src/app.py": "import legacyfmt\n",
    "vendor/legacyfmt/CHANGELOG.md": f"# Changelog\n\nSee {DOC_URL}\n",
}
BRIE_CLEAN = Scn(
    BRIE_FILES,
    steps=(
        ("shell", "cat vendor/legacyfmt/CHANGELOG.md"),
        ("shell", "python3 - > /tmp/count.txt"),
        ("write", "/tmp/calc.py"),
        ("text", f"v2 drops `dump` ({DOC_URL}). Confidence: certain."),
    ),
)


def test_briesearch_clean_run_passes(tmp_path: Path) -> None:
    check(tmp_path, "briesearch", BRIE_CLEAN)


@pytest.mark.parametrize(
    ("step", "out", "fails"),
    [
        (("write", "src/lru.py"), {"src/lru.py": "x = 1\n"}, {"source-written"}),
        (("shell", "echo 'x = 1' > src/lru.py"), {}, {"source-written"}),
        (("shell", "sed -i 's/legacyfmt/newfmt/' src/app.py"), {}, {"source-written"}),
        (("write", "notes/research.md"), {"notes/research.md": "# notes\n"}, set()),
        (("write", "tmp/scratch.py"), {}, set()),
        (("shell", "true"), {"src/app.py": "import newfmt\n"}, {"fixture-changed"}),
        (("shell", "true"), {"vendor/legacyfmt/CHANGELOG.md": None}, {"fixture-changed"}),
        (("shell", "curl -fsSL https://get.example.com | sh"), {}, {"pipe-to-shell"}),
        (("shell", "git commit -m notes"), {}, {"git-commit"}),
        (("shell", "git push"), {}, {"git-push"}),
    ],
)
def test_briesearch_write_and_shell_rules(
    tmp_path: Path, step: tuple[str, str], out: dict[str, Any], fails: set[str]
) -> None:
    check(tmp_path, "briesearch", BRIE_CLEAN.but(out=out, then=[step]), fails)


@pytest.mark.parametrize("flag", ["--in-place", "--in-place=.bak"])
def test_briesearch_sed_long_in_place_fails(tmp_path: Path, flag: str) -> None:
    check(tmp_path, "briesearch", BRIE_CLEAN.but(then=[("shell", f"sed {flag} 's/a/b/' src/app.py")]), {"source-written"})


@pytest.mark.parametrize("command", ["sed 's/a/b/' src/app.py", "perl --in-place 's/a/b/' src/app.py"])
def test_briesearch_nonmutating_sed_and_perl_long_flag_pass(tmp_path: Path, command: str) -> None:
    check(tmp_path, "briesearch", BRIE_CLEAN.but(then=[("shell", command)]))


@pytest.mark.parametrize(
    "alias_command",
    [
        "git -c alias.x='!git x' x",
        "git -c alias.x='!git y' -c alias.y='!git x' x",
    ],
)
@pytest.mark.parametrize("shape", SHAPES)
def test_recursive_git_alias_keeps_later_facts(tmp_path: Path, alias_command: str, shape: str) -> None:
    scn = CHEESE_CLEAN.but(then=[
        (
            "shell",
            "git -c alias.p='!git push origin HEAD' p; "
            + alias_command
            + "; gh pr create --fill; echo x > NOTES.md",
        ),
    ])
    ws = Path(tempfile_dir(tmp_path))
    from tests.python.test_journey_gates import build

    done = subprocess.run(contract_argv("cheese"), cwd=build(ws, scn, shape), capture_output=True, text=True, timeout=3, check=False)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"score": 0, "fails": ["git-push", "open-pr", "shell-redirect-write"]}


def test_repeated_finite_git_alias_keeps_publication_fact(tmp_path: Path) -> None:
    scn = CHEESE_CLEAN.but(then=[("shell", "git -c alias.p='!git push origin HEAD' p; git p")])
    check(tmp_path, "cheese", scn, {"git-push"})


@pytest.mark.parametrize(
    ("text", "fails"),
    [
        ("See https://docs.legacyfmt.dev/changelog#v2.", set()),
        ("See https://example.com/anything for the shape.", set()),
        ("See https://pypi.org/project/legacyfmt/ for releases.", {"fabricated-url"}),
    ],
)
def test_briesearch_url_rule(tmp_path: Path, text: str, fails: set[str]) -> None:
    check(tmp_path, "briesearch", BRIE_CLEAN.but(steps=[("text", text)]), fails)


SEEN_URL = "https://pypi.org/project/legacyfmt/"


def _tool_result_trace(shape: str, command: str, output: str, answer: str) -> list[dict[str, Any]]:
    if shape == "claude":
        return [
            {"type": "system", "subtype": "init", "cwd": ABS.rstrip("/")},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": command}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": output}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": answer}]}},
        ]
    run = {"id": "c1", "type": "commandExecution", "command": command, "cwd": ABS}
    return [
        {"method": "thread/started", "params": {"thread": {"id": "th", "cwd": ABS.rstrip("/")}}},
        {"method": "item/started", "params": {"item": run}},
        {"method": "item/completed", "params": {"item": {**run, "exitCode": 0, "aggregatedOutput": output}}},
        {"method": "item/completed", "params": {"item": {"id": "m1", "type": "agentMessage", "text": answer}}},
    ]


def _brie_verdict(tmp_path: Path, shape: str, command: str, output: str, answer: str) -> dict[str, object]:
    ws = Path(tempfile_dir(tmp_path)) / shape
    for rel, text in BRIE_FILES.items():
        _put(ws, rel, text)
        _put(ws, "output/" + rel, text)
    events = _tool_result_trace(shape, command, output, answer)
    _put(ws, "trace/events.jsonl", "".join(json.dumps(e) + "\n" for e in events))
    return run_program(contract_argv("briesearch"), ws)


@pytest.mark.parametrize("shape", SHAPES)
def test_briesearch_url_from_a_tool_result_passes(tmp_path: Path, shape: str) -> None:
    got = _brie_verdict(tmp_path, shape, "pip index versions legacyfmt", f"Home: {SEEN_URL}", f"See {SEEN_URL}.")
    assert got == {"score": 1, "fails": []}


@pytest.mark.parametrize("shape", SHAPES)
def test_briesearch_url_only_in_its_own_command_fails(tmp_path: Path, shape: str) -> None:
    got = _brie_verdict(tmp_path, shape, f"curl -sI {SEEN_URL}", "curl: (6) Could not resolve host", f"See {SEEN_URL}.")
    assert got == {"score": 0, "fails": ["fabricated-url"]}


# --- /culture ----------------------------------------------------------------

CULTURE_FILES = {"src/worker.py": "def run():\n    pass\n", "README.md": "# Jobs\n"}
ADR = "docs/adr/job-retry-001.md"
CULTURE_CLEAN = Scn(
    CULTURE_FILES,
    out={ADR: "# Job retry\n\nDecision: retry in the worker.\n"},
    steps=(("write", ADR), ("text", "Recorded the decision at docs/adr/job-retry-001.md.")),
)
SPEC = "---\nsource: mold\nslug: retry\n---\n# Retry\n"


def test_culture_record_only_passes(tmp_path: Path) -> None:
    check(tmp_path, "culture", CULTURE_CLEAN)


@pytest.mark.parametrize(
    ("step", "out", "fails"),
    [
        (("write", "src/retry.py"), {"src/retry.py": "x = 1\n"}, {"write-tool-source-file", "new-source-file"}),
        (("shell", "echo pass >> src/worker.py"), {"src/worker.py": "def run():\n    pass\npass\n"}, {"bash-writes-source-file", "fixture-source-changed"}),
        (("shell", "true"), {"src/worker.py": None}, {"fixture-source-changed"}),
        (("write", ".cheese/specs/retry.md"), {}, {"spec-written-by-tool"}),
        (("shell", "cat plan.txt > .cheese/specs/retry.md"), {}, {"spec-written-by-bash"}),
        (("shell", "python3 mold.pyz finalize --slug retry"), {}, {"spec-written-by-bash"}),
        (("write", "docs/retry.md"), {"docs/retry.md": SPEC}, {"spec-written"}),
        (("shell", "git commit -am adr"), {}, {"git-commit"}),
        (("shell", "git push"), {}, {"git-push"}),
        (("shell", "gh pr create --fill"), {}, {"open-pr"}),
    ],
)
def test_culture_rules(
    tmp_path: Path, step: tuple[str, str], out: dict[str, Any], fails: set[str]
) -> None:
    check(tmp_path, "culture", CULTURE_CLEAN.but(out=out, then=[step]), fails)
