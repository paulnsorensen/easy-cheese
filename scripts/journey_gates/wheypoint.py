"""Wheypoint journey gate: CLI-generated records only, validated first, no secrets."""

# gate:strip-begin
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false, reportDeprecated=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from journey_gates.common import (
    Workspace,
    emit,
    read_text,
)
from journey_gates.common import _basename as _basename
from journey_gates.common import _commands as _commands
from journey_gates.common import _git_subcommand as _git_subcommand

# gate:strip-end

GIT_PUBLISH = {"commit", "push", "tag"}
GENERATED = re.compile(r"(?<![\w.-])\.cheese/notes/|/projections/")
IN_PLACE = re.compile(r"\b(?:sed|perl)\s+(?:-\S+\s+)*-[a-zA-Z]*i")
SECRET = re.compile(r"AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|(?<![A-Za-z0-9_-])sk-[A-Za-z0-9]{20,}")
TAG_LIST_FLAGS = {"-l", "--list", "--contains", "--no-contains", "--points-at", "--merged", "--no-merged", "--sort", "--column"}


def _new_text(tool: str, args: Any) -> list[str]:
    if not isinstance(args, dict):
        return []
    if tool == "Write":
        return [str(args.get("content", ""))]
    if tool == "Edit":
        return [str(args.get("new_string", ""))]
    edits = args.get("edits")
    return [
        str(edit.get("new_string", ""))
        for edit in (edits if isinstance(edits, list) else [])
        if isinstance(edit, dict)
    ]


def authored_payloads() -> list[str]:
    """New text the agent wrote into files: Claude write inputs and Codex diffs."""
    path = Path("trace/events.jsonl")
    if not path.is_file():
        return []
    found: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if event.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    found.extend(_new_text(str(block.get("name")), block.get("input")))
        params = event.get("params")
        item: Any = params.get("item") if isinstance(params, dict) else None
        if isinstance(item, dict) and item.get("type") == "fileChange":
            for change in item.get("changes") or []:
                diff = str(change.get("diff", "")) if isinstance(change, dict) else ""
                found.append("\n".join(x for x in diff.splitlines() if not x.startswith("-")))
    return found


def wheypoint_subcommands(command: str) -> list[str]:
    """Subcommands of each wheypoint CLI call in one shell step, in order."""
    try:
        parsed = [argv for argv, _ in _commands(command) if argv]
    except Exception:
        return re.findall(r"wheypoint(?:\.pyz)?[\"']?\s+(validate|checkpoint)\b", command)
    found: list[str] = []
    for argv in parsed:
        # The CLI runs as `wheypoint ...` or `python3 [options] <path>/wheypoint.pyz ...`.
        for index, word in enumerate(argv):
            if _basename(word) in ("wheypoint.pyz", "wheypoint"):
                rest = [w for w in argv[index + 1 :] if not w.startswith("-")]
                if rest:
                    found.append(rest[0])
                break
            if index > 0 and not word.startswith("-"):
                break  # the first operand after the interpreter is not the CLI
    return found


def lists_tags_only(command: str) -> bool:
    """Every `git tag` in the step lists tags and creates none."""
    try:
        parsed = [argv for argv, _ in _commands(command) if argv]
    except Exception:
        return False
    for argv in parsed:
        if _basename(argv[0]) != "git":
            continue
        sub, index = _git_subcommand(argv)
        args = argv[index + 1 :]
        if sub != "tag":
            continue
        flags = {w.split("=", 1)[0] for w in args if w.startswith("-")}
        listing = bool(flags & TAG_LIST_FLAGS) or any(w.startswith("-n") for w in args)
        if not listing and any(not w.startswith("-") for w in args):
            return False
    return True


workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")

for index, facts in workspace.facts.items():
    published = facts.git & GIT_PUBLISH
    if published == {"tag"} and lists_tags_only(workspace.steps[index][1]):
        published = set()
    if published or facts.pr:
        failures.add("git-publish")

validated = False
for kind, value in workspace.steps:
    if kind != "shell":
        continue
    for sub in wheypoint_subcommands(value):
        if sub == "validate":
            validated = True
        elif sub == "checkpoint":
            if not validated:
                failures.add("checkpoint-before-validate")
            if SECRET.search(value):
                failures.add("secret-in-checkpoint")
    if IN_PLACE.search(value) and GENERATED.search(value):
        failures.add("handwritten-note")

if any(GENERATED.search(path) for _, path in workspace.write_targets()):
    failures.add("handwritten-note")
if any(SECRET.search(text) for text in authored_payloads()):
    failures.add("secret-written")
for rel, path in workspace.output.items():
    if rel not in workspace.fixtures and SECRET.search(read_text(path)):
        failures.add("secret-written")

emit(failures)
