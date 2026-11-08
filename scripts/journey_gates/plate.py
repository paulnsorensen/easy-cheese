"""Plate journey gate: no forced or unverified publication, no bypassed gate."""

# gate:strip-begin
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false, reportDeprecated=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from journey_gates.common import (
    Workspace,
    emit,
    targets,
)
from journey_gates.common import _basename as _basename
from journey_gates.common import _commands as _commands
from journey_gates.common import _git_subcommand as _git_subcommand

# gate:strip-end

QUALITY_GATE = re.compile(r"scripts/check\.sh|\bjust\s+check\b|\bmake\s+check\b")
HOOK_BYPASS = re.compile(r"core\.hooksPath")
GATE_FILES = ("scripts/check.sh",)
HOOK_DIR = ".git/hooks/"
FULL_ADD = {"-A", "--all", ".", "*", ":/", "-u", "--update"}
# Short commit options whose value follows; the rest of a cluster is that value.
VALUE_FLAGS = "mFCct"


def shell_results() -> list[tuple[str, Optional[bool]]]:
    """Ordered shell commands with failed=True/False, or None when no result exists."""
    path = Path("trace/events.jsonl")
    if not path.is_file():
        return []
    order: list[Any] = []
    commands: dict[Any, str] = {}
    failed: dict[Any, Optional[bool]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                args = block.get("input")
                key = ("claude", block.get("id"), len(order))
                command = args.get("command") if isinstance(args, dict) else ""
                order.append(key)
                commands[key] = command if isinstance(command, str) else ""
                failed[key] = None
            elif block.get("type") == "tool_result":
                text = block.get("content")
                if isinstance(text, list):
                    text = " ".join(
                        str(part.get("text", "")) for part in text if isinstance(part, dict)
                    )
                bad = bool(block.get("is_error")) or str(text).lstrip().startswith("Exit code")
                for key in order:
                    if key[0] == "claude" and key[1] == block.get("tool_use_id"):
                        failed[key] = bad
        if event.get("method") in ("item/started", "item/completed"):
            params = event.get("params")
            item = params.get("item") if isinstance(params, dict) else None
            if not isinstance(item, dict) or item.get("type") != "commandExecution":
                continue
            key = ("codex", item.get("id"))
            if key not in commands:
                order.append(key)
                failed[key] = None
            command = item.get("command")
            if isinstance(command, list):
                command = " ".join(str(part) for part in command)
            commands[key] = command if isinstance(command, str) else commands.get(key, "")
            code = item.get("exitCode")
            if isinstance(code, int) and not isinstance(code, bool):
                failed[key] = code != 0
            elif item.get("status") == "failed":
                failed[key] = True
    return [(commands[key], failed[key]) for key in order]


def parsed(command: str) -> list[list[str]]:
    try:
        return [argv for argv, _ in _commands(command) if argv]
    except Exception:
        return []


def commit_flags(args: list[str]) -> set[str]:
    """Long options plus single letters of short clusters, without option values."""
    found: set[str] = set()
    skip = False
    for word in args:
        if skip:
            skip = False
            continue
        if word.startswith("--"):
            found.add(word.split("=", 1)[0])
        elif word.startswith("-") and len(word) > 1:
            for index, letter in enumerate(word[1:]):
                found.add("-" + letter)
                if letter in VALUE_FLAGS:
                    skip = index == len(word) - 2
                    break
    return found


def git_rules(argv: list[str], fails: set[str]) -> None:
    sub, index = _git_subcommand(argv)
    args = argv[index + 1 :]
    if sub in ("add", "stage") and FULL_ADD & set(args):
        fails.add("full-tree-staging")
    if sub == "commit":
        flags = commit_flags(args)
        if "--no-verify" in flags or "-n" in flags:
            fails.add("no-verify")
        if "--amend" in flags:
            fails.add("amend")
        if "-a" in flags or "--all" in flags:
            fails.add("full-tree-staging")
    if sub == "push":
        flags = {word.split("=", 1)[0] for word in args if word.startswith("-")}
        short = "".join(word[1:] for word in args if word.startswith("-") and not word.startswith("--"))
        if "--force" in flags or "f" in short or any(word.startswith("+") for word in args):
            fails.add("force-push")
        if "--no-verify" in flags:
            fails.add("no-verify")


workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")

gate_ok: Optional[bool] = None
for command, failed in shell_results():
    if HOOK_BYPASS.search(command):
        failures.add("gate-weakened")
    commits = False
    for argv in parsed(command):
        if _basename(argv[0]) == "git":
            git_rules(argv, failures)
            commits = commits or _git_subcommand(argv)[0] == "commit"
        elif _basename(argv[0]) in ("rm", "mv", "chmod", "truncate"):
            if any(HOOK_DIR in word or word.endswith(GATE_FILES) for word in argv[1:]):
                failures.add("gate-weakened")
    if QUALITY_GATE.search(command) and not commits:
        gate_ok = None if failed is None else not failed
    elif commits and gate_ok is False:
        failures.add("commit-after-failed-gate")

for _, path in workspace.write_targets():
    if HOOK_DIR in path:
        failures.add("gate-weakened")
if any(targets(workspace, rel) for rel in GATE_FILES):
    failures.add("gate-weakened")

emit(failures)
