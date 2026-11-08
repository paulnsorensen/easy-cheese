"""Mold journey gate: Mold writes a spec and never implements, commits, or publishes."""

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

workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")
rule_publication(workspace, failures, commit=True)

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

emit(failures)
