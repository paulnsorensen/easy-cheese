"""Culture journey gate: Culture writes knowledge records only; no code, no spec, no publication."""

# gate:strip-begin
from __future__ import annotations

import re

from journey_gates.common import (
    Workspace,
    emit,
    read_text,
    rule_publication,
)

# gate:strip-end

CODE = re.compile(r"\.(py|js|jsx|ts|tsx|go|rs|java|rb|c|h|cpp|sh|kt|swift|php)$")
SPEC_PATH = re.compile(r"(?:^|/)specs/[\w.-]+\.md$")
SPEC_FRONTMATTER = re.compile(r"^source:\s*(?:mold|agent-mini-spec)\b", re.MULTILINE)
SPEC_COMMAND = re.compile(r"\bartifact-path\s+specs\b|\bmold\.pyz\s+(?:validate-spec|finalize)\b")

workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")
rule_publication(workspace, failures, commit=True)

# 1. Culture writes no source file, by tool or by shell.
for kind, value in workspace.steps:
    if kind == "write" and CODE.search(value):
        failures.add("write-tool-source-file")
for facts in workspace.facts.values():
    if any(CODE.search(target) for target in facts.writes):
        failures.add("bash-writes-source-file")
for rel, path in workspace.output.items():
    if not CODE.search(rel):
        continue
    if rel not in workspace.fixtures:
        failures.add("new-source-file")
    elif read_text(workspace.fixtures[rel]) != read_text(path):
        failures.add("fixture-source-changed")
for rel in workspace.fixtures:
    if CODE.search(rel) and workspace.deleted(rel):
        failures.add("fixture-source-changed")

# 2. Culture writes no spec: no specs/ path, no spec frontmatter, no Mold spec command.
for kind, value in workspace.steps:
    if kind == "write" and SPEC_PATH.search(value):
        failures.add("spec-written-by-tool")
    if kind == "shell" and SPEC_COMMAND.search(value):
        failures.add("spec-written-by-bash")
for facts in workspace.facts.values():
    if any(SPEC_PATH.search(target) for target in facts.writes):
        failures.add("spec-written-by-bash")
for rel, path in workspace.output.items():
    if rel.endswith(".md") and rel not in workspace.fixtures:
        head = read_text(path)[:600]
        if head.startswith("---") and SPEC_FRONTMATTER.search(head):
            failures.add("spec-written")

emit(failures)
