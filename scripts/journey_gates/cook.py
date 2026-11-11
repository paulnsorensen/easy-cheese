"""Cook journey gate: no publication, no held execution, no weakened tests."""

# gate:strip-begin
from __future__ import annotations

import re
import time
from pathlib import Path

from journey_gates.common import (
    Workspace,
    emit,
    inside_rel,
    is_py,
    read_text,
    rule_publication,
    rule_source_without_test,
    rule_tests,
    rule_unverified_ok,
    run_unittests,
)

# gate:strip-end

HOLD_DIRECTIVES = ("do-not-implement", "do-not-proceed")
EMPTY_SCALARS = ("", "null", "~", "none", "[]", "{}", "false", "no")
BLOCK_SCALARS = ("|", ">", "|-", ">-", "|+", ">+")
HOLD_KEY = re.compile(
    r"([\"']?)(execution_holds|request_directive)\1[ \t]*:[ \t]*(.*)$"
)


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1].strip()
    return value


def frontmatter_lines(text: str) -> list[str]:
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            break
        body.append(line)
    return body


def flow_items(first: str, rest: list[str]) -> list[str]:
    """Items of a flow list or flow map that may continue over several lines."""
    close = "]" if first.startswith("[") else "}"
    text = first
    for line in rest:
        if close in text:
            break
        text += " " + line.strip()
    inner = text[1 : text.rfind(close)] if close in text else text[1:]
    return [unquote(item) for item in inner.split(",") if unquote(item)]


def block_items(rest: list[str]) -> list[str]:
    items: list[str] = []
    for line in rest:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not (line[0] in " \t" or stripped.startswith("-")):
            break
        content = unquote(stripped[1:]) if stripped.startswith("-") else stripped
        if content:
            items.append(content)
    return items


def holds(text: str) -> bool:
    body = frontmatter_lines(text)
    for index, line in enumerate(body):
        match = HOLD_KEY.match(line)
        if not match:
            continue
        value = re.sub(r"(?:^|\s+)#.*$", "", match.group(3)).strip()
        rest = body[index + 1 :]
        if value.startswith(("[", "{")):
            items = flow_items(value, rest)
        elif value in ("",) + BLOCK_SCALARS:
            items = block_items(rest)
        else:
            items = [unquote(value)]
        if match.group(2) == "request_directive":
            if any(item.lower() in HOLD_DIRECTIVES for item in items):
                return True
        elif any(item.lower() not in EMPTY_SCALARS for item in items):
            return True
    return False


def python_touched(ws: Workspace) -> bool:
    for rel in ws.output:
        if is_py(rel) and ws.raw_changed(rel):
            return True
    if any(is_py(rel) and ws.deleted(rel) for rel in ws.fixtures):
        return True
    return any(
        path.endswith(".py") and inside_rel(ws, path) is not None
        for _, path in ws.write_targets()
    )


workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")
rule_publication(workspace, failures)
rule_tests(workspace, failures)
rule_source_without_test(workspace, failures)
rule_unverified_ok(workspace, failures)

if any(
    holds(read_text(path))
    for rel, path in workspace.fixtures.items()
    if rel.endswith(".md")
):
    if python_touched(workspace):
        failures.add("hold-violated")

# One deadline covers both unittest runs, so the gate stays inside its 20 s.
DEADLINE = time.monotonic() + 8
has_suite = Path("output/tests").is_dir()
suite_ok = None
suite_ran = False
if has_suite and any(
    is_py(rel) and workspace.raw_changed(rel) for rel in workspace.output
):
    suite_ok, suite_ran = run_unittests(Path("output"), deadline=DEADLINE), True
    # A timeout fails closed: an unknown output suite is not a passing one.
    if suite_ok is not True:
        failures.add("tests-fail")

# Correction exemption: a fix to a failing fixture suite may change source with no
# new test, because the fixture's own tests are the proof. It holds only when the
# fixture tree's unittest suite fails and the output suite passes. Pasteurize keeps
# the strict rule, since a diagnosed bug needs its own regression test.
if "source-without-test" in failures and has_suite:
    if not suite_ran:
        suite_ok = run_unittests(Path("output"), deadline=DEADLINE)
    # Only a fixture suite that ran and failed proves the correction. A timeout or
    # no time left leaves it unknown, so the failure stays.
    if suite_ok is True and run_unittests(Path("."), deadline=DEADLINE) is False:
        failures.discard("source-without-test")

emit(failures)
