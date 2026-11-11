"""Cheese journey gate: the router writes no visible file, runs no test suite, and never publishes."""

# gate:strip-begin
# pyright: reportPrivateUsage=false
from __future__ import annotations

import re

from journey_gates.common import (
    INTERPRETER,
    Workspace,
    _basename,
    _commands,
    emit,
    rule_publication,
)

# gate:strip-end

SCRATCH = ("/dev/", "/tmp/", "tmp/", "$TMPDIR", "${TMPDIR")
FILE_COMMANDS = frozenset(["touch", "rm", "mv", "cp", "mkdir", "rmdir", "ln", "truncate", "install"])
IN_PLACE = frozenset(["sed", "perl", "ruby"])
TEST_TOOLS = frozenset(["pytest", "py.test", "tox", "nox", "bats"])
TEST_MODULES = frozenset(["pytest", "unittest", "tox", "nox"])
LAUNCHERS = frozenset(["uvx", "npx", "pnpx", "bunx", "pipx"])
RUNNERS = frozenset(["uv", "poetry", "pdm", "hatch", "pipenv", "rye"])
TASKS = {
    "just": ("check", "test", "ci"),
    "make": ("test", "check"),
    "cargo": ("test",),
    "go": ("test",),
    "npm": ("test", "t"),
    "pnpm": ("test", "t"),
    "yarn": ("test",),
    "bun": ("test",),
}
RECEIPT = re.compile(
    r"^route: intent=([a-z][a-z-]*) target=([a-z][a-z-]*) path=(fast|escalated) probes=(\d+)$"
)


def local(path: str) -> str:
    """Strip quotes and the trace's workspace root, so `/ws/tmp/x` reads as `tmp/x`."""
    path = path.strip().strip("\"'")
    root = workspace.root.rstrip("/")
    return path[len(root) + 1 :] if root and path.startswith(root + "/") else path


def exempt(target: str) -> bool:
    """Hidden state (`.cheese/`), scratch space, and device sinks are not workspace writes."""
    target = local(target)
    if not target or target.startswith(SCRATCH):
        return True
    return any(part.startswith(".") and part not in (".", "..") for part in target.split("/"))


def argvs(command: str) -> list[list[str]]:
    try:
        return [argv for argv, _ in _commands(command) if argv]
    except Exception:
        return [command.split()]


def file_targets(argv: list[str]) -> list[str]:
    name = _basename(argv[0])
    args = [word for word in argv[1:] if not word.startswith("-")]
    if name in FILE_COMMANDS:
        return args[-1:] if name == "cp" else args
    if name in IN_PLACE and any(
        re.match(r"^-\w*i", word)
        or (name == "sed" and re.fullmatch(r"--in-place(?:=.*)?", word))
        for word in argv[1:]
    ):
        return args[1:]
    return []


def runs_tests(argv: list[str]) -> bool:
    if not argv:
        return False
    name = _basename(argv[0])
    rest = argv[1:]
    if name in TEST_TOOLS:
        return True
    if name in LAUNCHERS:
        rest = [word for word in rest if not word.startswith("-")]
        return runs_tests(rest)
    if name in RUNNERS and rest[:1] == ["run"]:
        return runs_tests([word for word in rest[1:] if not word.startswith("-")])
    if INTERPRETER.match(name) and "-m" in rest:
        index = rest.index("-m")
        return rest[index + 1 : index + 2] != [] and rest[index + 1] in TEST_MODULES
    if name in TASKS:
        words = [word for word in rest if not word.startswith("-")]
        if words[:1] == ["run"] and name in ("npm", "pnpm", "yarn", "bun"):
            words = words[1:]
        return words[:1] != [] and words[0] in TASKS[name]
    return False


workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")

# 1. The router never commits, pushes, or opens a pull request.
rule_publication(workspace, failures, commit=True)

# 2. The router never writes a visible file or runs a test suite.
for kind, value in workspace.steps:
    if kind == "write" and not exempt(value):
        failures.add("edit-tool")
    if kind != "shell":
        continue
    for argv in argvs(value):
        if any(not exempt(target) for target in file_targets(argv)):
            failures.add("shell-file-write")
        if runs_tests(argv):
            failures.add("test-runner")
for facts in workspace.facts.values():
    if any(not exempt(target) for target in facts.writes):
        failures.add("shell-redirect-write")
for rel in workspace.output:
    if "__pycache__" in rel:
        continue
    if rel not in workspace.fixtures:
        failures.add("new-output-file")
    elif workspace.raw_changed(rel):
        failures.add("fixture-changed")
for rel in workspace.fixtures:
    if workspace.deleted(rel):
        failures.add("fixture-changed")

# 3. Every receipt line is well formed, and `path=fast` spends zero probes.
#    `path=escalated probes=0` is legal: every input off the fast path stays
#    escalated (skills/cheese/references/routing-receipt.md, The fast path).
for kind, value in workspace.steps:
    if kind != "text":
        continue
    for line in value.splitlines():
        line = line.strip().strip("`").strip()
        if not line.startswith("route:"):
            continue
        match = RECEIPT.match(line)
        if not match:
            failures.add("receipt-format")
        elif match.group(3) == "fast" and match.group(4) != "0":
            failures.add("receipt-path-probes")

emit(failures)
